from uuid import uuid4

from event_sourcery.event_store import EventStore
from tests.events import SomeEvent


def test_iterates_over_one_stream(event_store: EventStore) -> None:
    stream_id = uuid4()
    event = SomeEvent(first_name="Test")
    event_store.append(stream_id=stream_id, events=[event])

    read_events = list(event_store.iter(stream_id))

    versioned_event = event.copy(update={"version": 1})
    assert read_events == [versioned_event]


def test_iterates_over_two_streams(event_store: EventStore) -> None:
    stream_id = uuid4()
    event = SomeEvent(first_name="Test1")
    event_store.append(stream_id=stream_id, events=[event])
    another_stream_id = uuid4()
    another_event = SomeEvent(first_name="Test1")
    event_store.append(stream_id=another_stream_id, events=[another_event])

    read_events = list(event_store.iter(stream_id, another_stream_id))

    versioned_events = [
        event.copy(update={"version": 1}),
        another_event.copy(update={"version": 1}),
    ]
    assert read_events == versioned_events


def test_iterates_over_all_streams(event_store: EventStore) -> None:
    all_events = []
    for _ in range(5):
        stream_id = uuid4()
        event = SomeEvent(first_name="Test1")
        all_events.append(event)
        event_store.append(stream_id=stream_id, events=[event])

    read_events = list(event_store.iter())

    versioned_events = [event.copy(update={"version": 1}) for event in all_events]
    assert read_events == versioned_events
