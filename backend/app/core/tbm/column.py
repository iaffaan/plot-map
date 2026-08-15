from dataclasses import dataclass

@dataclass
class Column:
    id: str
    floor_id: str
    x: float
    y: float
    width: float = 0.75  # 9 inches
    depth: float = 0.75  # 9 inches
    is_structural: bool = True
