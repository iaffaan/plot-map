from dataclasses import dataclass, field
from typing import List

@dataclass
class Junction:
    id: str
    x: float
    y: float
    floor_id: str
    connected_wall_ids: List[str] = field(default_factory=list)
