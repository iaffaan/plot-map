from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class Plot:
    id: str
    width: float
    depth: float
    boundary_coords: List[Tuple[float, float]] = field(default_factory=list)
    road_edge: str = "bottom"
    setbacks: dict = field(default_factory=lambda: {"left": 0.0, "right": 0.0, "bottom": 0.0, "top": 0.0})
