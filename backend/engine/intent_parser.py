import re
from typing import Dict, List, Tuple, Any

def parse_intent_to_layout(
    description: str,
    plot_width: float,
    plot_depth: float,
    setbacks: dict,
    floors: int = 1
) -> Dict[str, Any]:
    """
    Parses a natural language description and plot parameters into a structured room and stair core configuration.
    Dynamically scales room sizes based on the available buildable area to guarantee solver feasibility.
    """
    # 1. Calculate buildable area
    # Normalize setbacks keys (support both left/right/bottom/top and left/right/front/back)
    sb_left = float(setbacks.get('left', setbacks.get('left', 0.0)))
    sb_right = float(setbacks.get('right', setbacks.get('right', 0.0)))
    sb_bottom = float(setbacks.get('bottom', setbacks.get('front', 0.0)))
    sb_top = float(setbacks.get('top', setbacks.get('back', 0.0)))
    
    buildable_width = max(0.0, plot_width - sb_left - sb_right)
    buildable_depth = max(0.0, plot_depth - sb_bottom - sb_top)
    raw_buildable_area = buildable_width * buildable_depth
    
    # 2. Determine stair core size and position
    # Standard stair core is 8x10 or 10x10. If plot is very small, we can make it 8x8.
    stair_width = 8.0 if buildable_width < 30.0 else 10.0
    stair_height = 8.0 if buildable_depth < 30.0 else 10.0
    
    # If the buildable area is extremely small, scale down stair core further
    if raw_buildable_area < 400.0:
        stair_width = min(6.0, buildable_width * 0.25)
        stair_height = min(6.0, buildable_depth * 0.25)
        
    stair_area = stair_width * stair_height
    net_buildable_area = max(50.0, raw_buildable_area - stair_area)
    
    # Choose corner for stair core (default bottom-left)
    stair_edge = "bottom-left"
    if "right" in description.lower():
        stair_edge = "bottom-right"
    if "top" in description.lower():
        stair_edge = "top-left" if "left" in description.lower() else "top-right"
        
    stair_core = {
        "width": stair_width,
        "height": stair_height,
        "edge": stair_edge
    }
    
    # 3. Detect number of bedrooms requested
    num_bedrooms = 2  # Default
    
    # Check for direct number patterns
    bedroom_match = re.search(r'(\d+)\s*(?:bhk|bedroom|bed)', description, re.IGNORECASE)
    if bedroom_match:
        num_bedrooms = int(bedroom_match.group(1))
    else:
        # Check for word patterns
        desc_lower = description.lower()
        if "one bedroom" in desc_lower or "1 bedroom" in desc_lower or "1bhk" in desc_lower or "single bedroom" in desc_lower:
            num_bedrooms = 1
        elif "two bedroom" in desc_lower or "2 bedroom" in desc_lower or "2bhk" in desc_lower or "double bedroom" in desc_lower:
            num_bedrooms = 2
        elif "three bedroom" in desc_lower or "3 bedroom" in desc_lower or "3bhk" in desc_lower:
            num_bedrooms = 3
        elif "four bedroom" in desc_lower or "4 bedroom" in desc_lower or "4bhk" in desc_lower:
            num_bedrooms = 4
            
    # 4. Enforce self-healing limits based on net buildable area
    # 1 BHK needs at least ~250 sq ft
    # 2 BHK needs at least ~450 sq ft
    # 3 BHK needs at least ~700 sq ft
    if net_buildable_area < 380.0 and num_bedrooms > 1:
        num_bedrooms = 1
    elif net_buildable_area < 650.0 and num_bedrooms > 2:
        num_bedrooms = 2
    elif net_buildable_area < 900.0 and num_bedrooms > 3:
        num_bedrooms = 3
        
    # 5. Define base rooms and target proportions of net buildable area
    # Capped at generous maximums to leave plenty of packing space for the solver.
    rooms_config = []
    adjacencies = []
    
    # Entrance Lobby (all scenarios)
    rooms_config.append({
        "name": "Entrance Lobby",
        "type": "Entrance",
        "min_area": min(24.0, max(9.0, net_buildable_area * 0.04)),
        "min_width": 3.0,
        "min_height": 3.0,
        "requires_ventilation": False,
        "adjacent_to_road": True
    })
    
    # Living Room (all scenarios)
    living_area = min(240.0, max(80.0, net_buildable_area * 0.25))
    rooms_config.append({
        "name": "Living Room",
        "type": "Living Room",
        "min_area": living_area,
        "min_width": max(8.0, min(10.0, buildable_width * 0.3)),
        "min_height": max(8.0, min(10.0, buildable_depth * 0.3)),
        "requires_ventilation": True,
        "adjacent_to_road": True
    })
    adjacencies.append(("Entrance Lobby", "Living Room"))
    
    # Kitchen (all scenarios)
    kitchen_area = min(120.0, max(45.0, net_buildable_area * 0.15))
    rooms_config.append({
        "name": "Kitchen",
        "type": "Kitchen",
        "min_area": kitchen_area,
        "min_width": 6.5,
        "min_height": 6.5,
        "requires_ventilation": True,
        "adjacent_to_road": False
    })
    adjacencies.append(("Living Room", "Kitchen"))
    
    # Bedrooms & Bathrooms
    if num_bedrooms == 1:
        bed_area = min(180.0, max(90.0, net_buildable_area * 0.25))
        rooms_config.append({
            "name": "Master Bedroom",
            "type": "Bedroom",
            "min_area": bed_area,
            "min_width": 9.0,
            "min_height": 9.0,
            "requires_ventilation": True,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Master Bedroom"))
        
        bath_area = min(45.0, max(25.0, net_buildable_area * 0.08))
        rooms_config.append({
            "name": "Bathroom",
            "type": "Bathroom",
            "min_area": bath_area,
            "min_width": 4.5,
            "min_height": 4.5,
            "requires_ventilation": False,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Bathroom"))
        
    elif num_bedrooms == 2:
        mbed_area = min(180.0, max(90.0, net_buildable_area * 0.20))
        rooms_config.append({
            "name": "Master Bedroom",
            "type": "Bedroom",
            "min_area": mbed_area,
            "min_width": 9.0,
            "min_height": 9.0,
            "requires_ventilation": True,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Master Bedroom"))
        
        bed2_area = min(140.0, max(80.0, net_buildable_area * 0.16))
        rooms_config.append({
            "name": "Bedroom 2",
            "type": "Bedroom",
            "min_area": bed2_area,
            "min_width": 8.5,
            "min_height": 8.5,
            "requires_ventilation": True,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Bedroom 2"))
        
        # Two bathrooms for 2 BHK
        bath1_area = min(45.0, max(20.0, net_buildable_area * 0.05))
        rooms_config.append({
            "name": "Master Bath",
            "type": "Bathroom",
            "min_area": bath1_area,
            "min_width": 4.5,
            "min_height": 4.5,
            "requires_ventilation": False,
            "adjacent_to_road": False
        })
        adjacencies.append(("Master Bedroom", "Master Bath"))
        
        bath2_area = min(45.0, max(20.0, net_buildable_area * 0.05))
        rooms_config.append({
            "name": "Common Bath",
            "type": "Bathroom",
            "min_area": bath2_area,
            "min_width": 4.5,
            "min_height": 4.5,
            "requires_ventilation": False,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Common Bath"))
        
    else: # 3 or more BHK
        mbed_area = min(180.0, max(90.0, net_buildable_area * 0.16))
        rooms_config.append({
            "name": "Master Bedroom",
            "type": "Bedroom",
            "min_area": mbed_area,
            "min_width": 9.0,
            "min_height": 9.0,
            "requires_ventilation": True,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Master Bedroom"))
        
        bed2_area = min(140.0, max(80.0, net_buildable_area * 0.14))
        rooms_config.append({
            "name": "Bedroom 2",
            "type": "Bedroom",
            "min_area": bed2_area,
            "min_width": 8.5,
            "min_height": 8.5,
            "requires_ventilation": True,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Bedroom 2"))
        
        bed3_area = min(120.0, max(80.0, net_buildable_area * 0.12))
        rooms_config.append({
            "name": "Bedroom 3",
            "type": "Bedroom",
            "min_area": bed3_area,
            "min_width": 8.0,
            "min_height": 8.0,
            "requires_ventilation": True,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Bedroom 3"))
        
        bath1_area = min(40.0, max(20.0, net_buildable_area * 0.045))
        rooms_config.append({
            "name": "Master Bath",
            "type": "Bathroom",
            "min_area": bath1_area,
            "min_width": 4.0,
            "min_height": 4.5,
            "requires_ventilation": False,
            "adjacent_to_road": False
        })
        adjacencies.append(("Master Bedroom", "Master Bath"))
        
        bath2_area = min(40.0, max(20.0, net_buildable_area * 0.045))
        rooms_config.append({
            "name": "Common Bath",
            "type": "Bathroom",
            "min_area": bath2_area,
            "min_width": 4.0,
            "min_height": 4.5,
            "requires_ventilation": False,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Common Bath"))
        
    # 6. Safety check: scale down rooms if total exceeds 55% of net buildable area
    import math
    total_requested_area = sum(r["min_area"] for r in rooms_config)
    safety_target_area = 0.40 * net_buildable_area
    if total_requested_area > safety_target_area:
        scale_factor = safety_target_area / total_requested_area
        scale_factor_dim = math.sqrt(scale_factor)
        for r in rooms_config:
            scaled_area = r["min_area"] * scale_factor
            
            abs_min = 80.0
            if r["type"] == "Entrance":
                abs_min = 9.0
            elif r["type"] == "Kitchen":
                abs_min = 45.0
            elif r["type"] == "Bathroom":
                abs_min = 20.0
            elif r["type"] == "Living Room":
                abs_min = 80.0
                
            r["min_area"] = max(abs_min, scaled_area)
            # Scale down linear dimensions proportionally as well to avoid infeasible aspect ratio constraint locks
            r["min_width"] = max(3.0, r["min_width"] * scale_factor_dim)
            r["min_height"] = max(3.0, r["min_height"] * scale_factor_dim)
            
    return {
        "stair_core": stair_core,
        "rooms": rooms_config,
        "adjacencies": adjacencies
    }

