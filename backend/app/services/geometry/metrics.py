from typing import Any


def calculate_layout_metrics(
    plot_width: float,
    plot_depth: float,
    floors_data: dict[str, Any],
    stair_core_cfg: dict[str, Any]
) -> dict[str, Any]:
    """
    Computes zoning, performance, cost, and design score metrics for a compiled layout.
    
    Args:
        plot_width: Width of the plot.
        plot_depth: Depth of the plot.
        floors_data: Dict containing layout and geometry for each floor.
        stair_core_cfg: Config dictionary of the stair core (width, height, edge).
        
    Returns:
        Dict containing calculated metrics matching dashboard requirements.
    """
    plot_area = plot_width * plot_depth
    if plot_area <= 0:
        return {}
        
    stair_w = float(stair_core_cfg.get('width', 0.0))
    stair_h = float(stair_core_cfg.get('height', 0.0))
    stair_area = stair_w * stair_h
    
    total_floor_area = 0.0
    ground_floor_area = 0.0
    
    # Calculate areas per floor
    for floor_idx, f_data in floors_data.items():
        layout = f_data.get('layout', {})
        floor_rooms_area = sum(r['width'] * r['height'] for r in layout.values())
        
        # Include staircase core in floor built area
        floor_built_area = floor_rooms_area + stair_area
        total_floor_area += floor_built_area
        
        if floor_idx == "1":
            ground_floor_area = floor_built_area
            
    # 1. FAR / FSI (Floor Area Ratio)
    far = total_floor_area / plot_area
    
    # 2. Plot Coverage (Percentage of plot covered by ground floor)
    coverage_pct = (ground_floor_area / plot_area) * 100.0 if plot_area > 0 else 0.0
    
    # 3. Cost Estimate (INR, assuming base rate of 2000 INR/sqft)
    estimated_cost_inr = total_floor_area * 2000.0
    
    # 4. Carbon Score (Embodied carbon in kg CO2e, assuming 220 kg CO2e/sqft built-up)
    carbon_score_kg = total_floor_area * 220.0
    
    # 5. Daylighting Score (Percentage of ventilated rooms with window coverage)
    total_vent_rooms = 0
    lit_vent_rooms = 0
    
    # Check all floors
    for floor_idx, f_data in floors_data.items():
        layout = f_data.get('layout', {})
        geom = f_data.get('geometry', {})
        windows = geom.get('windows', [])
        
        # Group windows by room
        room_windows: dict[str, list[dict]] = {}
        for win in windows:
            r_name = win.get('room')
            if r_name:
                room_windows.setdefault(r_name, []).append(win)
                
        for r_name, room in layout.items():
            # Only count actual user rooms (exclude OTS/stair core if present in layout)
            if room.get('type') == 'OTS':
                continue
                
            total_vent_rooms += 1
            wins = room_windows.get(r_name, [])
            if wins:
                # Room has window(s)
                lit_vent_rooms += 1
                
    daylight_score = (lit_vent_rooms / total_vent_rooms * 100.0) if total_vent_rooms > 0 else 100.0
    
    # 6. Cross Ventilation Score
    habitable_types = {"Bedroom", "Living Room", "Kitchen", "Dining Room", "Pooja", "Living"}
    total_habitable_rooms = 0
    total_vent_points = 0.0

    for floor_idx, f_data in floors_data.items():
        layout = f_data.get('layout', {})
        if not layout:
            continue
        geom = f_data.get('geometry', {})
        windows = geom.get('windows', [])
        
        room_windows = {}
        for win in windows:
            r_name = win.get('room')
            if r_name:
                room_windows.setdefault(r_name, []).append(win)
                
        for r_name, room in layout.items():
            r_type = room.get('type', '')
            if r_type in habitable_types or any(ht.lower() in r_name.lower() for ht in ["bedroom", "living", "kitchen", "dining", "pooja"]):
                total_habitable_rooms += 1
                wins = room_windows.get(r_name, [])
                distinct_walls = {w.get("wall_edge", w.get("direction", "")) for w in wins}
                if len(distinct_walls) >= 2 or len(wins) >= 2:
                    total_vent_points += 1.0  # True dual-wall cross-ventilation
                elif len(wins) == 1:
                    total_vent_points += 0.75  # Single-sided exterior ventilation & natural airflow
                else:
                    total_vent_points += 0.0  # Unventilated

    if total_habitable_rooms > 0:
        cross_vent_score = round(min(100.0, (total_vent_points / total_habitable_rooms) * 100.0), 1)
    else:
        cross_vent_score = 100.0
    
    # 7. Buildability Score (dynamically calculated from Phase 11 validation engine)
    from app.services.geometry.validation import validate_layout
    validation_report = validate_layout(
        plot_width=plot_width,
        plot_depth=plot_depth,
        floors_data=floors_data,
        stair_core_cfg=stair_core_cfg
    )
    buildability_score = validation_report["buildability_score"]
        
    # 8. Privacy Score
    privacy_score = 100.0
    # Deduct privacy score if bedroom windows are too close to road boundary
    for floor_idx, f_data in floors_data.items():
        layout = f_data.get('layout', {})
        geom = f_data.get('geometry', {})
        windows = geom.get('windows', [])
        
        for win in windows:
            r_name = win.get('room')
            room = layout.get(r_name) if r_name else None
            if room and room.get('type') == 'Bedroom':
                # Check if window is close to front road setback edge (y_coord close to minimum buildable)
                wy = win['position'][1]
                if abs(wy - 5.0) < 0.1:  # Assuming bottom setback of 5.0 is the road front
                    privacy_score -= 10.0
                    
    privacy_score = max(50.0, privacy_score)
    
    # 9. Accessibility Score
    accessibility_score = 90.0
    # Standard accessibility deductions
    if len(floors_data) >= 3:
        accessibility_score -= 10.0  # Deduct if no lift core specified for high floors
        
    return {
        "far": round(far, 2),
        "fsi": round(far, 2),
        "plot_coverage_pct": round(coverage_pct, 1),
        "daylighting_score": round(daylight_score, 1),
        "cross_ventilation_score": round(cross_vent_score, 1),
        "estimated_cost_inr": round(estimated_cost_inr, 2),
        "carbon_score_kg_co2": round(carbon_score_kg, 2),
        "buildability_score": round(buildability_score, 1),
        "privacy_score": round(privacy_score, 1),
        "accessibility_score": round(accessibility_score, 1)
    }
