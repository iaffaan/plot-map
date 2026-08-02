from shapely.geometry import Polygon

def create_plot(width: float, depth: float) -> Polygon:
    """Create a rectangular polygon representing the plot coordinates (0,0) to (width, depth)."""
    return Polygon([(0, 0), (width, 0), (width, depth), (0, depth)])

def apply_setbacks(plot: Polygon, left: float, right: float, bottom: float, top: float) -> Polygon:
    """Subtract municipal setbacks from the plot edges."""
    min_x, min_y, max_x, max_y = plot.bounds
    new_min_x = min_x + left
    new_max_x = max_x - right
    new_min_y = min_y + bottom
    new_max_y = max_y - top
    
    if new_min_x >= new_max_x or new_min_y >= new_max_y:
        # Returns empty polygon if setbacks overlap/exceed boundaries
        return Polygon()
    
    return Polygon([
        (new_min_x, new_min_y),
        (new_max_x, new_min_y),
        (new_max_x, new_max_y),
        (new_min_x, new_max_y)
    ])

def create_stair_core(buildable_envelope: Polygon, core_width: float, core_height: float, edge: str = 'bottom-left') -> Polygon:
    """Place a staircase/lift core of specified dimensions against the boundary of the buildable envelope."""
    min_x, min_y, max_x, max_y = buildable_envelope.bounds
    
    if edge == 'bottom-left':
        x0, y0 = min_x, min_y
    elif edge == 'bottom-right':
        x0, y0 = max_x - core_width, min_y
    elif edge == 'top-left':
        x0, y0 = min_x, max_y - core_height
    elif edge == 'top-right':
        x0, y0 = max_x - core_width, max_y - core_height
    elif edge == 'bottom-center':
        x0, y0 = min_x + (max_x - min_x - core_width) / 2, min_y
    elif edge == 'top-center':
        x0, y0 = min_x + (max_x - min_x - core_width) / 2, max_y - core_height
    elif edge == 'left-center':
        x0, y0 = min_x, min_y + (max_y - min_y - core_height) / 2
    elif edge == 'right-center':
        x0, y0 = max_x - core_width, min_y + (max_y - min_y - core_height) / 2
    else:
        # Default fallback
        x0, y0 = min_x, min_y
        
    return Polygon([
        (x0, y0),
        (x0 + core_width, y0),
        (x0 + core_width, y0 + core_height),
        (x0, y0 + core_height)
    ])

def calculate_buildable_area(plot: Polygon, setbacks: dict, stair_core_config: dict) -> tuple[Polygon, Polygon, Polygon]:
    """
    Enforces setbacks and subtracts the staircase/lift core from the plot to find the buildable area.
    
    Args:
        plot: Master plot Polygon.
        setbacks: Dict with keys 'left', 'right', 'bottom', 'top'.
        stair_core_config: Dict with keys 'width', 'height', 'edge'.
        
    Returns:
        A tuple of (envelope_polygon, core_polygon, buildable_area_polygon).
    """
    left = float(setbacks.get('left', 0.0))
    right = float(setbacks.get('right', 0.0))
    bottom = float(setbacks.get('bottom', 0.0))
    top = float(setbacks.get('top', 0.0))
    
    envelope = apply_setbacks(plot, left, right, bottom, top)
    if envelope.is_empty:
        return envelope, Polygon(), envelope
        
    core_w = float(stair_core_config.get('width', 0.0))
    core_h = float(stair_core_config.get('height', 0.0))
    core_edge = stair_core_config.get('edge', 'bottom-left')
    
    core = create_stair_core(envelope, core_w, core_h, core_edge)
    
    # Subtract core from the envelope
    buildable_area = envelope.difference(core)
    
    return envelope, core, buildable_area
