from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass(kw_only=True)
class CADPrimitive:
    layer: str = "default"
    color: str = "#000000"  # default black line
    stroke_width: float = 1.0  # stroke width in points

@dataclass(kw_only=True)
class Line(CADPrimitive):
    x1: float
    y1: float
    x2: float
    y2: float

@dataclass(kw_only=True)
class Polyline(CADPrimitive):
    points: List[Tuple[float, float]]
    is_closed: bool = False

@dataclass(kw_only=True)
class Arc(CADPrimitive):
    cx: float
    cy: float
    radius: float
    start_angle: float  # in degrees
    end_angle: float    # in degrees

@dataclass(kw_only=True)
class Circle(CADPrimitive):
    cx: float
    cy: float
    radius: float

@dataclass(kw_only=True)
class Text(CADPrimitive):
    x: float
    y: float
    content: str
    font_size: float = 12.0  # in sheet points/mm
    rotation: float = 0.0    # in degrees
    anchor: str = "middle"   # "start", "middle", "end"
    is_sheet_space: bool = True  # True if text height remains constant regardless of drawing scale

@dataclass(kw_only=True)
class Hatch(CADPrimitive):
    boundary_points: List[Tuple[float, float]]
    pattern: str = "solid"  # "solid", "ansi31" (diagonal lines), etc.
    fill_color: str = "#e0e0e0"

@dataclass(kw_only=True)
class Dimension(CADPrimitive):
    # Definition points
    x1: float
    y1: float
    x2: float
    y2: float
    # Dimension line placement point
    dim_x: float
    dim_y: float
    text: str = ""
    arrow_size: float = 2.0  # sheet scale points

@dataclass(kw_only=True)
class Leader(CADPrimitive):
    points: List[Tuple[float, float]]
    text: str
    arrow_size: float = 2.0

@dataclass(kw_only=True)
class Symbol(CADPrimitive):
    name: str  # e.g., "door_swing", "north_arrow"
    x: float
    y: float
    rotation: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    properties: dict = field(default_factory=dict)
