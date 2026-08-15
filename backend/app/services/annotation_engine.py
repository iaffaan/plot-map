from app.core.tbm import Building
from app.drawing import Drawing, Text, Line, Polyline
from app.drawing.symbols import generate_north_arrow
from app.services.geometry_resolver import ResolvedGeometry

def generate_annotations(building: Building, geom: ResolvedGeometry, drawing: Drawing) -> None:
    """
    Generates professional CAD labels, annotations, room schedules,
    and a title block sheet layout.
    """
    # 1. Centered Room Labels
    for r_id, room in building.rooms.items():
        room_poly = geom.room_boundaries.get(r_id)
        if room_poly:
            xs = [v[0] for v in room_poly.vertices]
            ys = [v[1] for v in room_poly.vertices]
            if xs and ys:
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                cx = (min_x + max_x) / 2.0
                cy = (min_y + max_y) / 2.0
                
                # Room Name Label
                drawing.add(Text(
                    layer="Annotations",
                    color="#1f2937",  # charcoal
                    font_size=12.0,
                    x=cx, y=cy + 0.5,
                    content=room.name.upper(),
                    anchor="middle"
                ))
                
                # Room Area Label
                w = max_x - min_x
                h = max_y - min_y
                area = w * h
                area_text = f"{w:.1f}' x {h:.1f}' ({area:.1f} sqft)"
                drawing.add(Text(
                    layer="Annotations",
                    color="#4b5563",  # dark grey
                    font_size=8.0,
                    x=cx, y=cy - 0.5,
                    content=area_text,
                    anchor="middle"
                ))
                
    # 2. Door and Window tags
    # Loop over openings and add tags like "D1", "W1"
    door_count = 0
    window_count = 0
    for op_id, op in building.openings.items():
        box = geom.opening_boxes.get(op_id)
        if box:
            xs = [v[0] for v in box.vertices]
            ys = [v[1] for v in box.vertices]
            if xs and ys:
                cx = (min(xs) + max(xs)) / 2.0
                cy = (min(ys) + max(ys)) / 2.0
                
                if op.type == "Door":
                    door_count += 1
                    label = f"D{door_count}"
                else:
                    window_count += 1
                    label = f"W{window_count}"
                    
                drawing.add(Text(
                    layer="Annotations",
                    color="#2563eb",  # dark blue
                    font_size=8.0,
                    x=cx, y=cy,
                    content=label,
                    anchor="middle"
                ))

    # Calculate building bounds to place Sheet Border and Title Block
    all_xs = []
    all_ys = []
    for w_id, panels in geom.wall_panels.items():
        for p in panels:
            all_xs.extend([v[0] for v in p.vertices])
            all_ys.extend([v[1] for v in p.vertices])
            
    if not all_xs or not all_ys:
        return
        
    b_min_x, b_max_x = min(all_xs), max(all_xs)
    b_min_y, b_max_y = min(all_ys), max(all_ys)
    
    # 3. North Arrow (top-right of building footprint)
    generate_north_arrow(b_max_x + 5.0, b_max_y, radius=1.5)
    for p in generate_north_arrow(b_max_x + 5.0, b_max_y, radius=1.5):
        drawing.add(p)

    # 4. Sheet Border (10 ft margin around building)
    margin = 8.0
    sh_min_x, sh_max_x = b_min_x - margin, b_max_x + margin + 6.0  # extra room on right for title block
    sh_min_y, sh_max_y = b_min_y - margin, b_max_y + margin
    
    drawing.add(Polyline(
        layer="Grid",
        color="#9ca3af",  # grey border
        stroke_width=2.0,
        points=[
            (sh_min_x, sh_min_y),
            (sh_max_x, sh_min_y),
            (sh_max_x, sh_max_y),
            (sh_min_x, sh_max_y)
        ],
        is_closed=True
    ))
    
    # 5. CAD Title Block (placed at bottom right of the sheet border)
    # Width of title box = 8 ft, height = 5 ft
    tb_w = 12.0
    tb_h = 5.0
    
    tbx1 = sh_max_x - tb_w
    tby1 = sh_min_y
    tbx2 = sh_max_x
    tby2 = sh_min_y + tb_h
    
    drawing.add(Polyline(
        layer="Grid",
        color="#000000",
        stroke_width=1.5,
        points=[(tbx1, tby1), (tbx2, tby1), (tbx2, tby2), (tbx1, tby2)],
        is_closed=True
    ))
    
    # Divide title block into segments
    # Horizontal line inside
    drawing.add(Line(
        layer="Grid", color="#000000", stroke_width=1.0,
        x1=tbx1, y1=tby1 + 2.5, x2=tbx2, y2=tby1 + 2.5
    ))
    # Vertical line inside
    drawing.add(Line(
        layer="Grid", color="#000000", stroke_width=1.0,
        x1=tbx1 + 6.0, y1=tby1, x2=tbx1 + 6.0, y2=tby2
    ))
    
    # Add title block texts
    # Project Name
    drawing.add(Text(
        layer="Annotations", color="#000000", font_size=10.0,
        x=tbx1 + 3.0, y=tby1 + 3.75, content=building.name.upper(),
        anchor="middle"
    ))
    # Designer
    drawing.add(Text(
        layer="Annotations", color="#4b5563", font_size=7.0,
        x=tbx1 + 3.0, y=tby1 + 1.25, content="PLOT-MAP CAD ENGINE",
        anchor="middle"
    ))
    # Scale
    drawing.add(Text(
        layer="Annotations", color="#000000", font_size=8.0,
        x=tbx1 + 9.0, y=tby1 + 3.75, content="SCALE: 1/4\" = 1'-0\"",
        anchor="middle"
    ))
    # Sheet index
    drawing.add(Text(
        layer="Annotations", color="#000000", font_size=8.0,
        x=tbx1 + 9.0, y=tby1 + 1.25, content="SHEET: A-101",
        anchor="middle"
    ))
