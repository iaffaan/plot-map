from typing import Any, Dict, List, Tuple
from app.core.tbm import Building, Wall, Opening, Junction
from app.core.cad_kernel.geometry_service import GeometryService, Polygon2D

class ResolvedGeometry:
    def __init__(self):
        self.wall_panels: Dict[str, List[Polygon2D]] = {}  # Wall ID -> list of panel polygons
        self.opening_boxes: Dict[str, Polygon2D] = {}     # Opening ID -> bounding polygon
        self.room_boundaries: Dict[str, Polygon2D] = {}   # Room ID -> boundary polygon
        self.merged_wall_boundary: List[Polygon2D] = []    # Unified boundary of all walls (for CAD hatching)

def resolve_geometry(building: Building) -> ResolvedGeometry:
    """
    Translates a semantic TBM Building model into resolved geometry.
    Computes constructive panel splits along wall centerlines to accommodate doors and windows.
    """
    geom = ResolvedGeometry()
    all_panels = []
    
    # 1. Resolve Wall Panel geometries constructively (avoiding CSG subtraction)
    for w_id, wall in building.walls.items():
        # Get start and end junctions
        j1 = building.junctions.get(wall.start_junction_id)
        j2 = building.junctions.get(wall.end_junction_id)
        if not j1 or not j2:
            continue
            
        dx = j2.x - j1.x
        dy = j2.y - j1.y
        L = (dx**2 + dy**2)**0.5
        if L < 0.01:
            continue
            
        ux, uy = dx / L, dy / L
        
        # Collect openings on this wall
        openings: List[Opening] = []
        for o_id in wall.hosted_opening_ids:
            op = building.openings.get(o_id)
            if op:
                openings.append(op)
                
        # Calculate solid intervals along centerline
        intervals: List[Tuple[float, float]] = []
        if not openings:
            intervals.append((0.0, L))
        else:
            # Each opening spans [center - width/2, center + width/2]
            spans = []
            for op in openings:
                center = op.position_offset
                h_w = op.width / 2.0
                start_span = max(0.0, center - h_w)
                end_span = min(L, center + h_w)
                spans.append((start_span, end_span, op.id))
                
            # Sort spans by start offset
            spans.sort(key=lambda s: s[0])
            
            # Generate solid centerline segments constructively
            curr = 0.0
            for s_start, s_end, op_id in spans:
                if s_start > curr + 0.01:
                    intervals.append((curr, s_start))
                # Resolve opening box geometry
                # Center of the opening in global coords
                cx = j1.x + (s_start + s_end) / 2.0 * ux
                cy = j1.y + (s_start + s_end) / 2.0 * uy
                op_width = s_end - s_start
                # Create a rectangular box for the opening
                op_poly = GeometryService.offset_segment(
                    cx - (op_width/2.0)*ux, cy - (op_width/2.0)*uy,
                    cx + (op_width/2.0)*ux, cy + (op_width/2.0)*uy,
                    wall.thickness
                )
                geom.opening_boxes[op_id] = op_poly
                curr = s_end
                
            if curr < L - 0.01:
                intervals.append((curr, L))
                
        # Generate wall panel polygons
        geom.wall_panels[w_id] = []
        for s1, s2 in intervals:
            px1, py1 = j1.x + s1 * ux, j1.y + s1 * uy
            px2, py2 = j1.x + s2 * ux, j1.y + s2 * uy
            panel_poly = GeometryService.offset_segment(px1, py1, px2, py2, wall.thickness)
            geom.wall_panels[w_id].append(panel_poly)
            all_panels.append(panel_poly)

    # 2. Compute unified boundary polygon for all walls (clean junction joins/hatching)
    geom.merged_wall_boundary = GeometryService.union_polygons(all_panels)
    
    # 3. Resolve Room boundary polygons (interior floor fills)
    for r_id, room in building.rooms.items():
        # Get coordinates of corners based on the rooms bounding walls
        # For simplicity in orthogonal MVP layouts, we calculate room bounds from its name/dimensions
        # or trace the wall centerlines. Let's find min/max coordinates from all wall centerlines bounding this room.
        x_coords: List[float] = []
        y_coords: List[float] = []
        
        for w_id in room.bounded_by_wall_ids:
            wall = building.walls.get(w_id)
            if wall:
                j1 = building.junctions.get(wall.start_junction_id)
                j2 = building.junctions.get(wall.end_junction_id)
                if j1 and j2:
                    x_coords.extend([j1.x, j2.x])
                    y_coords.extend([j1.y, j2.y])
                    
        if x_coords and y_coords:
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            # Create a simple clockwise rectangle polygon
            vertices = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y), (min_x, min_y)]
            geom.room_boundaries[r_id] = GeometryService.create_polygon(vertices)
            
    return geom
