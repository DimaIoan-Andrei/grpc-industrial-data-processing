from typing import Any, Dict

from pydantic import BaseModel, Field


class NormalizedRecord(BaseModel):
    source_id: str
    source_type: str
    protocol_hint: str
    event_time: str
    quality: str
    event_type: str
    sequence_no: int
    measurements: Dict[str, float]
    attributes: Dict[str, Any] = Field(default_factory=dict)
