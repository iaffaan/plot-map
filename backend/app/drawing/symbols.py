import math
from typing import List, Tuple
from app.drawing.primitives import CADPrimitive, Line, Arc, Text, Polyline, Circle, Symbol
from app.core.cad_kernel.geometry_service import GeometryService

def generate_door_symbol(
    x1: float, y1: float, x2: float, y2: float, swing_left: bool = True, swing_out: bool = True
) -> List[CADPrimitive]:
    """
    Generates a professional 2D CAD door symbol consisting of:
    - Door frame lines
    - Open door leaf (90 degrees)
    - Swing path quarter-circle arc
    """
    primitives: List[CADPrimitive] = []
    
    # Calculate wall angle and length
    dx = x2 - x1
    dy = y2 - y1
    width = (dx**2 + dy**2)**0.5
    if width < 0.1:
        return []
        
    ux, uy = dx / width, dy / width
    # Perpendicular vector
    px, py = -uy, ux
    
    # Hinge is at (x1, y1)
    hinge_x, hinge_y = x1, y1
    
    # Swing direction multiplier
    swing_mult = 1.0 if swing_left else -1.0
    out_mult = 1.0 if swing_out else -1.0
    
    # Leaf end point: rotate hinge+width vector by 90 degrees in swing direction
    # Closed leaf is along (ux, uy). Rotate it.
    leaf_angle = 90.0 * swing_mult * out_mult
    leaf_end_x, leaf_end_y = GeometryService.rotate_point(
        x1 + width * ux, y1 + width * uy, leaf_angle, hinge_x, hinge_y
    )
    
    # 1. Door Leaf Line
    primitives.append(Line(
        layer="Doors",
        color="#3b82f6",  # blue for doors
        stroke_width=1.5,
        x1=hinge_x, y1=hinge_y,
        x2=leaf_end_x, y2=leaf_end_y
    ))
    
    # 2. Swing Arc
    # Arc starts from closed door end point (x2, y2) and sweeps 90 degrees to leaf end point
    start_angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
    end_angle = start_angle + leaf_angle
    
    # Ensure angles are sorted for standard arc sweeping
    a1 = min(start_angle, end_angle)
    a2 = max(start_angle, end_angle)
    
    primitives.append(Arc(
        layer="Doors",
        color="#3b82f6",
        stroke_width=1.0,
        cx=hinge_x, cy=hinge_y,
        radius=width,
        start_angle=a1,
        end_angle=a2
    ))
    
    # 3. Small door stop jamb lines at endpoints
    jamb_w = 0.2
    primitives.append(Line(
        layer="Doors",
        color="#000000",
        stroke_width=1.0,
        x1=x1, y1=y1,
        x2=x1 + jamb_w * px * out_mult, y2=y1 + jamb_w * py * out_mult
    ))
    primitives.append(Line(
        layer="Doors",
        color="#000000",
        stroke_width=1.0,
        x1=x2, y1=y2,
        x2=x2 + jamb_w * px * out_mult, y2=y2 + jamb_w * py * out_mult
    ))
    
    return primitives

def generate_window_symbol(x1: float, y1: float, x2: float, y2: float, thickness: float = 0.75) -> List[CADPrimitive]:
    """
    Generates a 2D CAD sliding/fixed window symbol:
    - Double frame lines matching wall thickness
    - Central glass pane line
    """
    primitives: List[CADPrimitive] = []
    
    dx = x2 - x1
    dy = y2 - y1
    width = (dx**2 + dy**2)**0.5
    if width < 0.1:
        return []
        
    ux, uy = dx / width, dy / width
    px, py = -uy, ux  # perpendicular normal
    
    h_t = thickness / 2.0
    
    # 1. Outer frame boundary lines (offset outward by half-thickness)
    primitives.append(Line(
        layer="Windows",
        color="#10b981",  # green for windows
        stroke_width=1.5,
        x1=x1 + h_t * px, y1=y1 + h_t * py,
        x2=x2 + h_t * px, y2=y2 + h_t * py
    ))
    primitives.append(Line(
        layer="Windows",
        color="#10b981",
        stroke_width=1.5,
        x1=x1 - h_t * px, y1=y1 - h_t * py,
        x2=x2 - h_t * px, y2=y2 - h_t * py
    ))
    
    # 2. End cap lines
    primitives.append(Line(
        layer="Windows",
        color="#000000",
        stroke_width=1.5,
        x1=x1 - h_t * px, y1=y1 - h_t * py,
        x2=x1 + h_t * px, y2=y1 + h_t * py
    ))
    primitives.append(Line(
        layer="Windows",
        color="#000000",
        stroke_width=1.5,
        x1=x2 - h_t * px, y1=y2 - h_t * py,
        x2=x2 + h_t * px, y2=y2 + h_t * py
    ))
    
    # 3. Double central glass pane lines
    g_offset = 0.08  # glass pane gap
    primitives.append(Line(
        layer="Windows",
        color="#06b6d4",  # cyan glass
        stroke_width=1.0,
        x1=x1 + g_offset * px, y1=y1 + g_offset * py,
        x2=x2 + g_offset * px, y2=y2 + g_offset * py
    ))
    primitives.append(Line(
        layer="Windows",
        color="#06b6d4",
        stroke_width=1.0,
        x1=x1 - g_offset * px, y1=y1 - g_offset * py,
        x2=x2 - g_offset * px, y2=y2 - g_offset * py
    ))
    
    return primitives

def generate_stair_symbol(
    x: float, y: float, length: float, width: float, rotation: float = 0.0, steps: int = 10
) -> List[CADPrimitive]:
    """
    Generates a stair plan symbol:
    - Step risers
    - Center walk line with direction arrowhead
    - 'UP' / 'DN' annotation
    """
    primitives: List[CADPrimitive] = []
    
    # Calculate flight bounds
    # For a simple straight flight stair starting at (x,y) extending by length
    # Let's rotate points based on angle
    ux, uy = math.cos(math.radians(rotation)), math.sin(math.radians(rotation))
    px, py = -uy, ux
    
    # Draw boundary box
    p1 = (x, y)
    p2 = (x + length * ux, y + length * uy)
    p3 = (x + length * ux + width * px, y + length * uy + width * py)
    p4 = (x + width * px, y + width * py)
    
    primitives.append(Polyline(
        layer="Structural",
        points=[p1, p2, p3, p4],
        is_closed=True,
        stroke_width=1.5
    ))
    
    # Draw steps risers
    step_l = length / steps
    for s in range(1, steps):
        dist = s * step_l
        rx1, ry1 = x + dist * ux, y + dist * uy
        rx2, ry2 = rx1 + width * px, ry1 + width * py
        primitives.append(Line(
            layer="Structural",
            color="#4b5563",
            stroke_width=1.0,
            x1=rx1, y1=ry1,
            x2=rx2, y2=ry2
        ))
        
    # Draw walking line (center)
    cx1, cy1 = x + (width / 2.0) * px, y + (width / 2.0) * py
    cx2, cy2 = x + length * ux + (width / 2.0) * px, y + length * uy + (width / 2.0) * py
    
    # Walking line from start to near end
    primitives.append(Line(
        layer="Annotations",
        color="#ef4444",  # red direction arrow
        stroke_width=1.2,
        x1=cx1 + step_l*0.5*ux, y1=cy1 + step_l*0.5*uy,
        x2=cx2 - step_l*0.5*ux, y2=cy2 - step_l*0.5*uy
    ))
    
    # Direction Arrowhead at end
    arrow_size = 0.5
    ax1, ay1 = GeometryService.rotate_point(cx2 - step_l*ux, cy2 - step_l*uy, 30.0, cx2 - step_l*0.5*ux, cy2 - step_l*0.5*uy)
    ax2, ay2 = GeometryService.rotate_point(cx2 - step_l*ux, cy2 - step_l*uy, -30.0, cx2 - step_l*0.5*ux, cy2 - step_l*0.5*uy)
    primitives.append(Polyline(
        layer="Annotations",
        points=[(ax1, ay1), (cx2 - step_l*0.5*ux, cy2 - step_l*0.5*uy), (ax2, ay2)],
        color="#ef4444",
        stroke_width=1.2
    ))
    
    # Label "UP" at the start
    primitives.append(Text(
        layer="Annotations",
        color="#000000",
        font_size=10.0,
        x=cx1 + 0.5*ux + 0.2*px, y=cy1 + 0.5*uy + 0.2*py,
        content="UP",
        anchor="start"
    ))
    
    return primitives

def generate_north_arrow(x: float, y: float, radius: float = 2.0) -> List[CADPrimitive]:
    """
    Generates a standard North Arrow drafting symbol.
    """
    primitives: List[CADPrimitive] = []
    
    # Outer circle
    primitives.append(Circle(
        layer="Grid",
        color="#000000",
        stroke_width=1.5,
        cx=x, cy=y,
        radius=radius
    ))
    
    # Central pointer arrow: triangle pointing UP (y-positive or y-negative depending on coordinate sys)
    # Assuming screen-standard coordinates where North is UP (y-positive)
    p_top = (x, y + radius * 0.9)
    p_left = (x - radius * 0.4, y - radius * 0.5)
    p_right = (x + radius * 0.4, y - radius * 0.5)
    
    primitives.append(Polyline(
        layer="Grid",
        color="#000000",
        points=[p_top, p_left, (x, y - radius*0.2), p_right],
        is_closed=True,
        stroke_width=1.2
    ))
    
    # Letter 'N' above the arrow
    primitives.append(Text(
        layer="Annotations",
        color="#000000",
        font_size=12.0,
        x=x, y=y + radius * 1.3,
        content="N",
        anchor="middle"
    ))
    
    return primitives
