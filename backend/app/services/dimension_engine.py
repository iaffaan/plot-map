from typing import List, Tuple
from app.core.tbm import Building
from app.drawing import Drawing, Dimension
from app.core.cad_kernel.spatial_index import SpatialIndex
from app.services.geometry_resolver import ResolvedGeometry

def generate_dimensions(building: Building, geom: ResolvedGeometry, drawing: Drawing) -> None:
    """
    Generates CAD dimension lines for the building.
    Uses a SpatialIndex candidate pipeline to place dimension lines without overlaps.
    """
    index = SpatialIndex()
    
    # 1. Insert existing geometry bounds into index to prevent placing dimensions inside walls
    for w_id, panels in geom.wall_panels.items():
        for p in panels:
            xs = [v[0] for v in p.vertices]
            ys = [v[1] for v in p.vertices]
            if xs and ys:
                index.insert(w_id, min(xs), min(ys), max(xs), max(ys))
                
    for op_id, box in geom.opening_boxes.items():
        xs = [v[0] for v in box.vertices]
        ys = [v[1] for v in box.vertices]
        if xs and ys:
            index.insert(op_id, min(xs), min(ys), max(xs), max(ys))
            
    # Calculate building bounding box
    all_xs: List[float] = []
    all_ys: List[float] = []
    for w_id, panels in geom.wall_panels.items():
        for p in panels:
            all_xs.extend([v[0] for v in p.vertices])
            all_ys.extend([v[1] for v in p.vertices])
            
    if not all_xs or not all_ys:
        return
        
    min_x, max_x = min(all_xs), max(all_xs)
    min_y, max_y = min(all_ys), max(all_ys)
    
    # 2. Overall Horizontal Dimension (Bottom side)
    # Target segment from (min_x, min_y) to (max_x, min_y)
    dim_y = min_y - 3.0  # start candidate 3 ft below
    dim_w = max_x - min_x
    
    # Candidate search loop
    while index.intersects(min_x, dim_y - 1.0, max_x, dim_y + 1.0):
        dim_y -= 2.0  # push further down if blocked
        
    dim_text = f"{dim_w:.1f}'"
    h_dim = Dimension(
        layer="Dimensions",
        color="#b45309",  # amber brown for dimensions
        stroke_width=1.0,
        x1=min_x, y1=min_y,
        x2=max_x, y2=min_y,
        dim_x=(min_x + max_x) / 2.0, dim_y=dim_y,
        text=dim_text
    )
    drawing.add(h_dim)
    index.insert("dim_overall_h", min_x, dim_y - 1.0, max_x, dim_y + 1.0)
    
    # 3. Overall Vertical Dimension (Left side)
    # Target segment from (min_x, min_y) to (min_x, max_y)
    dim_x = min_x - 3.0  # start candidate 3 ft to the left
    dim_h = max_y - min_y
    
    # Candidate search loop
    while index.intersects(dim_x - 1.0, min_y, dim_x + 1.0, max_y):
        dim_x -= 2.0  # push further left if blocked
        
    dim_text = f"{dim_h:.1f}'"
    v_dim = Dimension(
        layer="Dimensions",
        color="#b45309",
        stroke_width=1.0,
        x1=min_x, y1=min_y,
        x2=min_x, y2=max_y,
        dim_x=dim_x, dim_y=(min_y + max_y) / 2.0,
        text=dim_text
    )
    drawing.add(v_dim)
    index.insert("dim_overall_v", dim_x - 1.0, min_y, dim_x + 1.0, max_y)
    
    # 4. Room segment boundaries dimensions
    # For each room, add internal segment dimensions along its borders
    for r_id, room in building.rooms.items():
        room_poly = geom.room_boundaries.get(r_id)
        if room_poly:
            r_xs = [v[0] for v in room_poly.vertices]
            r_ys = [v[1] for v in room_poly.vertices]
            if r_xs and r_ys:
                r_min_x, r_max_x = min(r_xs), max(r_xs)
                r_min_y, r_max_y = min(r_ys), max(r_ys)
                
                # Internal horizontal center dimension
                center_y = (r_min_y + r_max_y) / 2.0
                r_w = r_max_x - r_min_x
                drawing.add(Dimension(
                    layer="Dimensions",
                    color="#d97706",
                    stroke_width=0.8,
                    x1=r_min_x, y1=center_y,
                    x2=r_max_x, y2=center_y,
                    dim_x=(r_min_x + r_max_x) / 2.0, dim_y=center_y,
                    text=f"{r_w:.1f}'"
                ))
