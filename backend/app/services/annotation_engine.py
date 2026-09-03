from app.core.tbm import Building
from app.drawing import Drawing, Text, Line, Polyline
from app.drawing.symbols import generate_north_arrow
from app.services.geometry_resolver import ResolvedGeometry

def generate_annotations(building: Building, geom: ResolvedGeometry, drawing: Drawing, floor_id: str | None = None) -> None:
    """
    Generates professional CAD labels, annotations, room schedules,
    and a title block sheet layout for a specific floor or the entire building.
    """
    # Spatial tracker to avoid overlapping annotations and label collisions
    placed_label_boxes = []

    def boxes_intersect(b1, b2, pad=0.3):
        return not (b1[2] + pad < b2[0] or b1[0] - pad > b2[2] or b1[3] + pad < b2[1] or b1[1] - pad > b2[3])

    def estimate_text_bbox(cx, cy, text, font_size):
        half_w = max(0.8, (len(text) * font_size * 0.032))
        half_h = max(0.5, (font_size * 0.055))
        return [cx - half_w, cy - half_h, cx + half_w, cy + half_h]

    target_room_ids = set(building.floors[floor_id].room_ids) if floor_id and floor_id in building.floors else set(building.rooms.keys())
    target_opening_ids = set(building.floors[floor_id].opening_ids) if floor_id and floor_id in building.floors else set(building.openings.keys())
    target_wall_ids = set(building.floors[floor_id].wall_ids) if floor_id and floor_id in building.floors else set(building.walls.keys())

    # 1. Centered Room Labels with Adaptive Sizing & Collision Avoidance
    for r_id in target_room_ids:
        room = building.rooms.get(r_id)
        if not room:
            continue
        room_poly = geom.room_boundaries.get(r_id)
        if room_poly:
            xs = [v[0] for v in room_poly.vertices]
            ys = [v[1] for v in room_poly.vertices]
            if xs and ys:
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                cx = (min_x + max_x) / 2.0
                cy = (min_y + max_y) / 2.0
                w = max_x - min_x
                h = max_y - min_y
                area = w * h

                # Adaptive font sizing based on room dimensions
                min_dim = min(w, h)
                name_font_size = min(11.0, max(7.0, min_dim * 1.0))
                area_font_size = min(8.0, max(5.5, min_dim * 0.7))

                # Vertical offset between room name and room area text
                v_offset = max(0.7, min_dim * 0.08)

                # Room Name Label
                name_text = room.name.upper()
                name_y = cy + v_offset
                name_bbox = estimate_text_bbox(cx, name_y, name_text, name_font_size)
                
                # Check collision with already placed labels and nudge if needed
                max_attempts = 10
                attempts = 0
                while attempts < max_attempts:
                    collision = False
                    for other_box in placed_label_boxes:
                        if boxes_intersect(name_bbox, other_box):
                            name_y += 1.2
                            name_bbox = estimate_text_bbox(cx, name_y, name_text, name_font_size)
                            collision = True
                            break
                    if not collision:
                        break
                    attempts += 1

                drawing.add(Text(
                    layer="Annotations",
                    color="#1f2937",  # charcoal
                    font_size=name_font_size,
                    x=cx, y=name_y,
                    content=name_text,
                    anchor="middle"
                ))
                placed_label_boxes.append(name_bbox)
                
                # Room Area Label
                area_text = f"{w:.1f}' x {h:.1f}' ({area:.1f} sqft)"
                area_y = cy - v_offset
                area_bbox = estimate_text_bbox(cx, area_y, area_text, area_font_size)
                
                attempts = 0
                while attempts < max_attempts:
                    collision = False
                    for other_box in placed_label_boxes:
                        if boxes_intersect(area_bbox, other_box):
                            area_y -= 1.0
                            area_bbox = estimate_text_bbox(cx, area_y, area_text, area_font_size)
                            collision = True
                            break
                    if not collision:
                        break
                    attempts += 1

                drawing.add(Text(
                    layer="Annotations",
                    color="#4b5563",  # dark grey
                    font_size=area_font_size,
                    x=cx, y=area_y,
                    content=area_text,
                    anchor="middle"
                ))
                placed_label_boxes.append(area_bbox)
                
    # 2. Door and Window tags with Collision Offset Handling
    door_count = 0
    window_count = 0
    seen_opening_coords = set()
    for op_id in target_opening_ids:
        op = building.openings.get(op_id)
        if not op:
            continue
        box = geom.opening_boxes.get(op_id)
        if box:
            xs = [v[0] for v in box.vertices]
            ys = [v[1] for v in box.vertices]
            if xs and ys:
                cx = (min(xs) + max(xs)) / 2.0
                cy = (min(ys) + max(ys)) / 2.0
                
                # Deduplicate identical openings stacked on multiple floors in 2D plan
                loc_key = (round(cx, 2), round(cy, 2), op.type)
                if loc_key in seen_opening_coords:
                    continue
                seen_opening_coords.add(loc_key)
                
                if op.type == "Door":
                    door_count += 1
                    label = f"D{door_count}"
                else:
                    window_count += 1
                    label = f"W{window_count}"

                tag_bbox = estimate_text_bbox(cx, cy, label, 7.0)
                
                attempts = 0
                while attempts < max_attempts:
                    collision = False
                    for other_box in placed_label_boxes:
                        if boxes_intersect(tag_bbox, other_box):
                            cy += 1.0
                            tag_bbox = estimate_text_bbox(cx, cy, label, 7.0)
                            collision = True
                            break
                    if not collision:
                        break
                    attempts += 1
                    
                drawing.add(Text(
                    layer="Annotations",
                    color="#2563eb",  # dark blue
                    font_size=7.0,
                    x=cx, y=cy,
                    content=label,
                    anchor="middle"
                ))
                placed_label_boxes.append(tag_bbox)

    # Calculate building bounds to place Sheet Border and Title Block
    all_xs = []
    all_ys = []
    for w_id in target_wall_ids:
        panels = geom.wall_panels.get(w_id, [])
        for p in panels:
            all_xs.extend([v[0] for v in p.vertices])
            all_ys.extend([v[1] for v in p.vertices])
            
    if not all_xs or not all_ys:
        for w_id, panels in geom.wall_panels.items():
            for p in panels:
                all_xs.extend([v[0] for v in p.vertices])
                all_ys.extend([v[1] for v in p.vertices])

    if not all_xs or not all_ys:
        return
        
    b_min_x, b_max_x = min(all_xs), max(all_xs)
    b_min_y, b_max_y = min(all_ys), max(all_ys)
    
    # 3. North Arrow (top-right of building footprint)
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
    # Sheet
    sheet_num = f"A-10{building.floors[floor_id].floor_level}" if floor_id and floor_id in building.floors else "A-101"
    floor_suffix = f" (FL {building.floors[floor_id].floor_level})" if floor_id and floor_id in building.floors else " (COMPOSITE)"
    drawing.add(Text(
        layer="Annotations", color="#000000", font_size=7.5,
        x=tbx1 + 9.0, y=tby1 + 1.25, content=f"SHEET: {sheet_num}{floor_suffix}",
        anchor="middle"
    ))
