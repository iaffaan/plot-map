from dataclasses import dataclass

@dataclass
class Stair:
    id: str
    floor_id: str
    type: str = "U-shape"  # "Straight", "L-shape", "U-shape"
    width: float = 3.5  # flight width
    length: float = 10.0  # footprint length
    x: float = 0.0
    y: float = 0.0
    direction_rotation: float = 0.0
    treads: int = 18
    riser_height: float = 0.58  # ~7 inches in feet
    tread_depth: float = 0.83  # ~10 inches in feet
    connects_to_floor_id: str = ""
