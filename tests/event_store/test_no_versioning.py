import pytest

from event_sourcery.event_store import NO_VERSIONING, Event, StreamId
from event_sourcery.event_store.exceptions import (
    ExpectedVersionUsedOnVersionlessStream,
    NoExpectedVersionGivenOnVersionedStream,
)
from tests.bdd import Given, Then, When


class AnEvent(Event):
    pass


@pytest.mark.not_implemented(storage=["django"])
def test_versionless_stream_is_supported(given: Given, when: When, then: Then) -> None:
    given.stream(stream_id := StreamId())
    when.store.append(
        first := AnEvent(),
        stream_id=stream_id,
        expected_version=NO_VERSIONING,
    )
    when.store.append(
        second := AnEvent(),
        stream_id=stream_id,
        expected_version=NO_VERSIONING,
    )
    then.stream(stream_id).loads([first, second])


@pytest.mark.not_implemented(storage=["django"])
@pytest.mark.skip_esdb(reason="ESDB is auto versioning")
def test_does_not_allow_for_mixing_versioning_with_no_versioning(
    given: Given,
    when: When,
) -> None:
    given.stream(stream_id := StreamId())
    given.store.append(AnEvent(), stream_id=stream_id, expected_version=0)

    with pytest.raises(NoExpectedVersionGivenOnVersionedStream):
        when.store.append(
            AnEvent(),
            stream_id=stream_id,
            expected_version=NO_VERSIONING,
        )


@pytest.mark.not_implemented(storage=["django"])
@pytest.mark.skip_esdb(reason="ESDB is auto versioning")
def test_does_not_allow_for_mixing_no_versioning_with_versioning(
    given: Given,
    when: When,
) -> None:
    given.stream(stream_id := StreamId())
    given.store.append(AnEvent(), stream_id=stream_id, expected_version=NO_VERSIONING)

    with pytest.raises(ExpectedVersionUsedOnVersionlessStream):
        when.store.append(
            AnEvent(),
            stream_id=stream_id,
            expected_version=1,
        )
