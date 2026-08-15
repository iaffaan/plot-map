from dataclasses import dataclass, field
from typing import List

@dataclass
class Wall:
    id: str
    floor_id: str
    thickness: float = 0.75  # default 9 inches in feet
    height: float = 10.0  # in feet
    start_junction_id: str = ""
    end_junction_id: str = ""
    room_a_id: str = ""
    room_b_id: str = ""
    hosted_opening_ids: List[str] = field(default_factory=list)
    is_load_bearing: bool = True
