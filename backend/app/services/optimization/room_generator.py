import math
from typing import Any

from app.schemas.intent import CompilerIntent, RoomCategory


def generate_layout_program(intent: CompilerIntent, setbacks: dict) -> dict[str, Any]:
    """
    Translates a structured CompilerIntent into a layout configuration payload for the solver.
    Equips each room with min area, preferred area, priority, aspect ratio, and floor assignment.
    """
    # 1. Calculate buildable area
    sb_left = float(setbacks.get('left', 0.0))
    sb_right = float(setbacks.get('right', 0.0))
    sb_bottom = float(setbacks.get('bottom', 0.0))
    sb_top = float(setbacks.get('top', 0.0))
    
    buildable_width = max(0.0, intent.plot_width - sb_left - sb_right)
    buildable_depth = max(0.0, intent.plot_depth - sb_bottom - sb_top)
    raw_buildable_area = buildable_width * buildable_depth
    
    # 2. Determine stair core size and position
    stair_width = 8.0 if buildable_width < 30.0 else 10.0
    stair_height = 8.0 if buildable_depth < 30.0 else 10.0
    
    if raw_buildable_area < 400.0:
        stair_width = min(6.0, buildable_width * 0.25)
        stair_height = min(6.0, buildable_depth * 0.25)
        
    stair_area = stair_width * stair_height
    net_buildable_area = max(50.0, raw_buildable_area - stair_area)
    
    stair_core = {
        "width": stair_width,
        "height": stair_height,
        "edge": "bottom-left"
    }
    
    # 3. Build rooms config from intent.rooms
    rooms_config = []
    adjacencies = []
    
    # Entrance Lobby (always required)
    entrance_name = "Entrance Lobby"
    entrance_min_area = min(24.0, max(9.0, net_buildable_area * 0.04))
    rooms_config.append({
        "name": entrance_name,
        "type": "Entrance",
        "min_area": entrance_min_area,
        "preferred_area": entrance_min_area * 1.2,
        "priority": 1,
        "aspect_ratio_range": (1.0, 1.5),
        "floor_assignment": 1,
        "min_width": 3.0,
        "min_height": 3.0,
        "requires_ventilation": False,
        "adjacent_to_road": True
    })
    
    # Check if a Living Room is explicitly in the intent, if not we add a default Living Room
    has_living = any(r.room_type == RoomCategory.LIVING for r in intent.rooms)
    living_name = "Living Room"
    if not has_living:
        living_area = min(240.0, max(80.0, net_buildable_area * 0.25))
        rooms_config.append({
            "name": living_name,
            "type": "Living Room",
            "min_area": living_area,
            "preferred_area": living_area * 1.5,
            "priority": 1,
            "aspect_ratio_range": (1.0, 1.6),
            "floor_assignment": 1,
            "min_width": max(8.0, min(10.0, buildable_width * 0.3)),
            "min_height": max(8.0, min(10.0, buildable_depth * 0.3)),
            "requires_ventilation": True,
            "adjacent_to_road": True
        })
        adjacencies.append((entrance_name, living_name))
        
    # Map other rooms from intent.rooms
    bedroom_idx = 1
    bathroom_idx = 1
    kitchen_idx = 1
    other_idx = 1
    
    # Track the main public area for connecting other rooms
    hub_name = living_name
    
    for r in intent.rooms:
        area = float(r.min_area_sqft or 100.0)
        
        # Enforce self-healing limit: if net buildable area is extremely small, scale down min area to avoid infeasibility
        if net_buildable_area < 500.0:
            area = min(area, net_buildable_area * 0.15)
        elif net_buildable_area < 800.0:
            area = min(area, net_buildable_area * 0.22)
            
        if r.room_type == RoomCategory.LIVING:
            rooms_config.append({
                "name": living_name,
                "type": "Living Room",
                "min_area": area,
                "preferred_area": area * 1.5,
                "priority": 1,
                "aspect_ratio_range": (1.0, 1.6),
                "floor_assignment": 1,
                "min_width": max(8.0, min(10.0, buildable_width * 0.3)),
                "min_height": max(8.0, min(10.0, buildable_depth * 0.3)),
                "requires_ventilation": True,
                "adjacent_to_road": True
            })
            adjacencies.append((entrance_name, living_name))
        elif r.room_type == RoomCategory.BEDROOM:
            name = f"Bedroom {bedroom_idx}" if bedroom_idx > 1 else "Master Bedroom"
            floor_ass = 2 if bedroom_idx in (1, 2) and intent.floors >= 2 else (3 if bedroom_idx == 3 and intent.floors >= 3 else 1)
            rooms_config.append({
                "name": name,
                "type": "Bedroom",
                "min_area": area,
                "preferred_area": area * 1.3,
                "priority": 2,
                "aspect_ratio_range": (1.0, 1.5),
                "floor_assignment": floor_ass,
                "min_width": 9.0 if area >= 81.0 else 8.0,
                "min_height": 9.0 if area >= 81.0 else 8.0,
                "requires_ventilation": True,
                "adjacent_to_road": False
            })
            adjacencies.append((hub_name, name))
            bedroom_idx += 1
        elif r.room_type == RoomCategory.KITCHEN:
            name = "Kitchen"
            rooms_config.append({
                "name": name,
                "type": "Kitchen",
                "min_area": area,
                "preferred_area": area * 1.3,
                "priority": 2,
                "aspect_ratio_range": (1.0, 1.5),
                "floor_assignment": 1,
                "min_width": 6.5 if area >= 42.0 else 5.0,
                "min_height": 6.5 if area >= 42.0 else 5.0,
                "requires_ventilation": True,
                "adjacent_to_road": False
            })
            adjacencies.append((hub_name, name))
            kitchen_idx += 1
        elif r.room_type == RoomCategory.BATHROOM:
            name = f"Bathroom {bathroom_idx}" if bathroom_idx > 1 else "Bathroom"
            floor_ass = 2 if bathroom_idx in (1, 2) and intent.floors >= 2 else (3 if bathroom_idx == 3 and intent.floors >= 3 else 1)
            rooms_config.append({
                "name": name,
                "type": "Bathroom",
                "min_area": area,
                "preferred_area": area * 1.2,
                "priority": 3,
                "aspect_ratio_range": (1.0, 1.4),
                "floor_assignment": floor_ass,
                "min_width": 4.5 if area >= 20.0 else 3.5,
                "min_height": 4.5 if area >= 20.0 else 3.5,
                "requires_ventilation": False,
                "adjacent_to_road": False
            })
            adjacencies.append((hub_name, name))
            bathroom_idx += 1
        else:
            name = f"{r.room_type.value.capitalize()} {other_idx}"
            floor_ass = 2 if other_idx % 2 == 0 and intent.floors >= 2 else 1
            rooms_config.append({
                "name": name,
                "type": r.room_type.value,
                "min_area": area,
                "preferred_area": area * 1.2,
                "priority": 3,
                "aspect_ratio_range": (1.0, 1.5),
                "floor_assignment": floor_ass,
                "min_width": 5.0,
                "min_height": 5.0,
                "requires_ventilation": False,
                "adjacent_to_road": False
            })
            adjacencies.append((hub_name, name))
            other_idx += 1

    # 4. Safety check: scale down rooms if total exceeds 40% of net buildable area
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
            r["min_width"] = max(3.0, r["min_width"] * scale_factor_dim)
            r["min_height"] = max(3.0, r["min_height"] * scale_factor_dim)
            r["preferred_area"] = r["min_area"] * 1.2
            
    return {
        "stair_core": stair_core,
        "rooms": rooms_config,
        "adjacencies": adjacencies
    }
