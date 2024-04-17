__all__ = [
    "ESDBStoreFactory",
    "ESDBStorageStrategy",
]

from dataclasses import dataclass
from functools import partial
from typing import cast

from esdbclient import EventStoreDBClient
from typing_extensions import Self

from event_sourcery import event_store as es
from event_sourcery.event_store import (
    Engine,
    Event,
    EventRegistry,
    EventStore,
    EventStoreFactory,
)
from event_sourcery.event_store.event import Serde
from event_sourcery.event_store.factory import NoOutboxStorageStrategy, no_filter
from event_sourcery.event_store.interfaces import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
)
from event_sourcery.event_store.outbox import Outbox
from event_sourcery_esdb.event_store import ESDBStorageStrategy
from event_sourcery_esdb.outbox import ESDBOutboxStorageStrategy
from event_sourcery_esdb.subscription import ESDBSubscriptionStrategy


@dataclass(repr=False)
class ESDBStoreFactory(EventStoreFactory):
    esdb_client: EventStoreDBClient
    _serde: Serde = Serde(Event.__registry__)
    _outbox_strategy: OutboxStorageStrategy = NoOutboxStorageStrategy()

    def build(self) -> Engine:
        engine = Engine()
        engine.event_store = EventStore(
            storage_strategy=ESDBStorageStrategy(self.esdb_client),
            serde=self._serde,
        )
        engine.outbox = Outbox(self._outbox_strategy, self._serde)
        engine.subscriber = cast(
            es.subscription.Positioner,
            partial(
                es.subscription.Engine,
                strategy=ESDBSubscriptionStrategy(self.esdb_client),
                serde=self._serde,
            ),
        )
        engine.serde = self._serde
        return engine

    def with_event_registry(self, event_registry: EventRegistry) -> Self:
        self._serde = Serde(event_registry)
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        strategy = ESDBOutboxStorageStrategy(self.esdb_client, filterer)
        strategy.create_subscription()
        self._outbox_strategy = strategy
        return self

    def without_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self._outbox_strategy = NoOutboxStorageStrategy()
        return self
