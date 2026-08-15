from dataclasses import dataclass, field
from typing import List

@dataclass
class Room:
    id: str
    name: str
    type: str  # e.g., "Living Room", "Bedroom", "Bathroom", "OTS"
    floor_id: str
    bounded_by_wall_ids: List[str] = field(default_factory=list)
    min_area: float = 0.0
    target_area: float = 0.0
    aspect_ratio_min: float = 0.5
    aspect_ratio_max: float = 2.0
