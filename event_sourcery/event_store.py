from functools import singledispatchmethod
from typing import Callable, Iterator, Sequence, Type, TypeVar, cast

from event_sourcery.after_commit_subscriber import AfterCommit
from event_sourcery.dto import RawEvent
from event_sourcery.event_registry import EventRegistry
from event_sourcery.exceptions import Misconfiguration, NoEventsToAppend
from event_sourcery.interfaces.base_event import Event
from event_sourcery.interfaces.event import Metadata, TEvent
from event_sourcery.interfaces.outbox_storage_strategy import OutboxStorageStrategy
from event_sourcery.interfaces.serde import Serde
from event_sourcery.interfaces.storage_strategy import StorageStrategy
from event_sourcery.interfaces.subscriber import Subscriber
from event_sourcery.types.stream_id import StreamId
from event_sourcery.versioning import NO_VERSIONING, ExplicitVersioning, Versioning

TAggregate = TypeVar("TAggregate")


class EventStore:
    def __init__(
        self,
        serde: Serde,
        storage_strategy: StorageStrategy,
        outbox_storage_strategy: OutboxStorageStrategy,
        event_base_class: Type[Event] | None = None,
        event_registry: EventRegistry | None = None,
        subscriptions: dict[Type[TEvent], list[Subscriber]] | None = None,
        outbox_filterer: Callable[[Event], bool] = lambda _: True,
    ) -> None:
        if event_base_class is not None and event_registry is not None:
            raise Misconfiguration(
                "You can specify only one of `event_base_class` or `event_registry`"
            )

        if subscriptions is None:
            subscriptions = {}

        if event_base_class is not None:
            self._event_registry = event_base_class.__registry__
        elif event_registry is not None:
            self._event_registry = event_registry
        else:  # not possible
            pass

        self._serde = serde
        self._storage_strategy = storage_strategy
        self._outbox_storage_strategy = outbox_storage_strategy
        self._subscriptions = subscriptions
        self._outbox_filterer = outbox_filterer

    def load_stream(
        self, stream_id: StreamId, start: int | None = None, stop: int | None = None
    ) -> Sequence[Metadata]:
        events = self._storage_strategy.fetch_events(stream_id, start=start, stop=stop)
        return self._deserialize_events(events)

    @singledispatchmethod
    def append(
        self,
        *events: Metadata,
        stream_id: StreamId,
        expected_version: int | Versioning = 0,
    ) -> None:
        self._append(
            stream_id=stream_id, events=events, expected_version=expected_version
        )

    @append.register
    def _append_events(
        self,
        *events: Event,
        stream_id: StreamId,
        expected_version: int | Versioning = 0,
    ) -> None:
        wrapped_events = self._wrap_events(expected_version, events)
        self.append(
            *wrapped_events, stream_id=stream_id, expected_version=expected_version
        )

    @singledispatchmethod
    def _wrap_events(
        self,
        expected_version: int,
        events: Sequence[Event],
    ) -> Sequence[Metadata]:
        return [
            Metadata.wrap(event=event, version=version)
            for version, event in enumerate(events, start=expected_version + 1)
        ]

    @_wrap_events.register
    def _wrap_events_versioning(
        self, expected_version: Versioning, events: Sequence[Event]
    ) -> Sequence[Metadata]:
        return [Metadata.wrap(event=event, version=None) for event in events]

    @singledispatchmethod
    def publish(
        self,
        *events: Metadata,
        stream_id: StreamId,
        expected_version: int | Versioning = 0,
    ) -> None:
        serialized_events = self._append(
            stream_id=stream_id, events=events, expected_version=expected_version
        )

        self._notify(events)
        events_to_put_into_outbox = [
            serialized_event
            for serialized_event, event in zip(serialized_events, events)
            if self._outbox_filterer(event.event)
        ]
        self._outbox_storage_strategy.put_into_outbox(events_to_put_into_outbox)

    def _notify(self, events: Sequence[Metadata]) -> None:
        for event in events:
            for subscriber in self._subscriptions.get(type(event.event), []):
                if isinstance(subscriber, AfterCommit):
                    self._storage_strategy.run_after_commit(lambda: subscriber(event))
                else:
                    subscriber(event)

            catch_all_subscribers = self._subscriptions.get(Event, [])  # type: ignore
            for catch_all_subscriber in catch_all_subscribers:
                catch_all_subscriber(event)

    @publish.register
    def _publish_events(
        self,
        *events: Event,
        stream_id: StreamId,
        expected_version: int | Versioning = 0,
    ) -> None:
        wrapped_events = self._wrap_events(expected_version, events)
        self.publish(
            *wrapped_events, stream_id=stream_id, expected_version=expected_version
        )

    def _append(
        self,
        stream_id: StreamId,
        events: Sequence[Metadata],
        expected_version: int | Versioning,
    ) -> list[RawEvent]:
        if not events:
            raise NoEventsToAppend

        new_version = events[-1].version
        versioning: Versioning
        if expected_version is not NO_VERSIONING:
            versioning = ExplicitVersioning(
                expected_version=cast(int, expected_version),
                initial_version=cast(int, new_version),
            )
        else:
            versioning = NO_VERSIONING

        self._storage_strategy.ensure_stream(
            stream_id=stream_id,
            versioning=versioning,
        )
        serialized_events = self._serialize_events(events, stream_id)
        self._storage_strategy.insert_events(serialized_events)
        return serialized_events

    def iter(self, *streams_ids: StreamId) -> Iterator[Metadata]:
        events_iterator = self._storage_strategy.iter(*streams_ids)
        for event in events_iterator:
            yield self._serde.deserialize(
                event, self._event_registry.type_for_name(event["name"])
            )

    def delete_stream(self, stream_id: StreamId) -> None:
        self._storage_strategy.delete_stream(stream_id)

    def save_snapshot(self, stream_id: StreamId, snapshot: Metadata) -> None:
        serialized = self._serde.serialize(
            event=snapshot,
            stream_id=stream_id,
            name=self._event_registry.name_for_type(type(snapshot.event)),
        )
        self._storage_strategy.save_snapshot(serialized)

    def _deserialize_events(self, events: list[RawEvent]) -> list[Metadata]:
        return [
            self._serde.deserialize(
                event=event,
                event_type=self._event_registry.type_for_name(event["name"]),
            )
            for event in events
        ]

    def _serialize_events(
        self,
        events: Sequence[Metadata],
        stream_id: StreamId,
    ) -> list[RawEvent]:
        return [
            self._serde.serialize(
                event=event,
                stream_id=stream_id,
                name=self._event_registry.name_for_type(type(event.event)),
            )
            for event in events
        ]
