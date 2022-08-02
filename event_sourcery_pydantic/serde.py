import json
from typing import Type, cast

from event_sourcery.dto.raw_event_dict import RawEventDict
from event_sourcery.interfaces.event import Event
from event_sourcery.interfaces.serde import Serde
from event_sourcery.types.stream_id import StreamId
from event_sourcery_pydantic.event import Event as PydanticEvent


class PydanticSerde(Serde):
    def deserialize(self, event: RawEventDict, event_type: Type[Event]) -> Event:
        event_as_dict = dict(event)
        data = event_as_dict.pop("data")
        return cast(Event, event_type(**event_as_dict, **data))

    def serialize(self, event: Event, stream_id: StreamId, name: str) -> RawEventDict:
        model = cast(PydanticEvent, event)
        as_dict = json.loads(  # json dumps and loads? It's moronic
            model.json(exclude={"uuid", "created_at"})
        )
        return RawEventDict(
            uuid=model.uuid,
            stream_id=stream_id,
            created_at=model.created_at,
            name=name,
            data=as_dict,
            metadata=as_dict.pop("metadata"),
        )
