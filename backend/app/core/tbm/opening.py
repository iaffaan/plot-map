from dataclasses import dataclass

@dataclass
class Opening:
    id: str
    type: str  # "Door", "Window", "Vent"
    wall_id: str
    width: float
    height: float
    sill_height: float = 0.0
    position_offset: float = 0.0  # distance from start junction
    connects_room_a_id: str = ""
    connects_room_b_id: str = ""
