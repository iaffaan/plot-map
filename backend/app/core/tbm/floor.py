from dataclasses import dataclass, field
from typing import List

@dataclass
class Floor:
    id: str
    floor_level: int
    elevation: float
    height: float = 10.0
    room_ids: List[str] = field(default_factory=list)
    wall_ids: List[str] = field(default_factory=list)
    junction_ids: List[str] = field(default_factory=list)
    column_ids: List[str] = field(default_factory=list)
    beam_ids: List[str] = field(default_factory=list)
    stair_ids: List[str] = field(default_factory=list)
    opening_ids: List[str] = field(default_factory=list)

