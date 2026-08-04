from shapely.geometry import Polygon


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
