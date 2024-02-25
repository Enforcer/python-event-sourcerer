from datetime import timedelta
from functools import partial
from typing import Callable, Iterator, Protocol, Type

from event_sourcery.event_store.event import (
    Event,
    Position,
    Recorded,
    RecordedRaw,
    Serde,
)
from event_sourcery.event_store.interfaces import Seconds, StorageStrategy
from event_sourcery.event_store.stream_id import Category


class Builder(Protocol):
    def build_iter(self, timelimit: Seconds | timedelta) -> Iterator[Recorded]:
        ...


class Subscriber(Builder):
    def __init__(
        self,
        start_from: Position,
        storage: StorageStrategy,
        serde: Serde,
    ) -> None:
        self._start_from = start_from
        self._storage = storage
        self._serde = serde
        self._build: Callable[[], Iterator[RecordedRaw]] = partial(
            self._storage.subscribe_to_all,
            start_from=self._start_from,
        )

    def to_category(self, category: Category) -> Builder:
        self._build = partial(
            self._storage.subscribe_to_category,
            start_from=self._start_from,
            category=category,
        )
        return self

    def to_events(self, events: list[Type[Event]]) -> Builder:
        self._build = partial(
            self._storage.subscribe_to_events,
            start_from=self._start_from,
            events=[self._serde.registry.name_for_type(event) for event in events],
        )
        return self

    def build_iter(self, timelimit: Seconds | timedelta) -> Iterator[Recorded]:
        seconds = timelimit.seconds if isinstance(timelimit, timedelta) else timelimit
        if seconds < 1:
            raise ValueError(
                f"Timebox must be at least 1 second. Received: {seconds:.02f}",
            )
        self._build = partial(self._build, timelimit=timelimit)
        return map(self._serde.deserialize_record, self._build())
