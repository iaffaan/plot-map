from app.schemas.intent import CompilerIntent, RoomCategory


def verify_feasibility(intent: CompilerIntent, setbacks: dict) -> tuple[bool, str]:
    """
    Checks if the user's intent is physically and legally feasible before running the solver.
    Returns:
        A tuple of (is_feasible: bool, reason: str)
    """
    plot_width = intent.plot_width
    plot_depth = intent.plot_depth
    floors = intent.floors
    
    # 1. Calculate plot area
    plot_area = plot_width * plot_depth
    if plot_area <= 0:
        return False, f"Plot area ({plot_area:.1f} sqft) is invalid."
        
    # 2. Calculate setbacks
    sb_left = float(setbacks.get('left', 0.0))
    sb_right = float(setbacks.get('right', 0.0))
    sb_bottom = float(setbacks.get('bottom', 0.0))
    sb_top = float(setbacks.get('top', 0.0))
    
    # 3. Calculate legal envelope
    buildable_width = plot_width - sb_left - sb_right
    buildable_depth = plot_depth - sb_bottom - sb_top
    
    if buildable_width <= 0 or buildable_depth <= 0:
        return False, f"Plot dimensions after setbacks are infeasible: width={buildable_width:.1f} ft, depth={buildable_depth:.1f} ft."
        
    envelope_footprint = buildable_width * buildable_depth
    
    # 4. Standard legal constraints (FAR & Ground Coverage)
    max_coverage_pct = 0.75  # Max 75% coverage
    max_far = 2.5            # Max 2.5 FAR
    
    max_legal_coverage_area = plot_area * max_coverage_pct
    max_ground_footprint = min(max_legal_coverage_area, envelope_footprint)
    max_legal_buildable_area = min(plot_area * max_far, floors * max_ground_footprint)
    
    # Determine stair core area
    stair_width = 8.0 if buildable_width < 30.0 else 10.0
    stair_height = 8.0 if buildable_depth < 30.0 else 10.0
    
    if envelope_footprint < 400.0:
        stair_width = min(6.0, buildable_width * 0.25)
        stair_height = min(6.0, buildable_depth * 0.25)
        
    stair_area = stair_width * stair_height
    
    # 5. Calculate requested area (rooms + stair core)
    # Note: Entrance lobby is always added as a default of 9 sqft minimum
    total_min_room_area = 9.0  # entrance lobby default min
    
    # Check if living room is requested, otherwise add a default of 80 sqft
    has_living = any(r.room_type == RoomCategory.LIVING for r in intent.rooms)
    if not has_living:
        total_min_room_area += 80.0
        
    for r in intent.rooms:
        total_min_room_area += float(r.min_area_sqft or 50.0)
        
    total_requested_area = total_min_room_area + stair_area
    
    # 6. Compare requested area against buildable limits
    if floors == 1 and total_requested_area > max_ground_footprint:
        return False, (
            f"Requested area exceeds ground footprint: "
            f"Required={total_requested_area:.1f} sqft (including {stair_area:.1f} sqft stair core), "
            f"Max allowable footprint={max_ground_footprint:.1f} sqft."
        )
        
    if total_requested_area > max_legal_buildable_area:
        return False, (
            f"Requested area exceeds total legal buildable area (FAR/Coverage): "
            f"Required={total_requested_area:.1f} sqft, "
            f"Max legal area={max_legal_buildable_area:.1f} sqft."
        )
        
    # 7. Check individual room fits
    for r in intent.rooms:
        min_dim = 3.0  # standard absolute minimum dimension
        if r.room_type == RoomCategory.BEDROOM or r.room_type == RoomCategory.LIVING:
            min_dim = 8.0
        elif r.room_type == RoomCategory.KITCHEN:
            min_dim = 5.0
        elif r.room_type == RoomCategory.BATHROOM:
            min_dim = 3.5
            
        if min_dim > buildable_width or min_dim > buildable_depth:
            return False, f"Room '{r.room_type.value}' minimum dimension ({min_dim:.1f} ft) does not fit within buildable envelope ({buildable_width:.1f}x{buildable_depth:.1f} ft)."
            
    return True, "Request is feasible."
