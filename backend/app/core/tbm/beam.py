from dataclasses import dataclass

@dataclass
class Beam:
    id: str
    floor_id: str
    start_column_id: str
    end_column_id: str
    width: float = 0.75  # 9 inches
    depth: float = 1.0  # 12 inches
