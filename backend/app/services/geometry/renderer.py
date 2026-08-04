from typing import Any


def generate_hierarchical_json(compiled_res: dict[str, Any]) -> dict[str, Any]:
    """
    Transforms the compiled flat coordinate output into a hierarchical tree format.
    Hierarchy: Project -> Floors -> Rooms -> (Walls, Doors, Windows, Furniture, Metadata)
    
    Args:
        compiled_res: The compiled result dict containing floors, boundaries, metrics, etc.
        
    Returns:
        Hierarchical JSON tree dictionary for rendering.
    """
    floors_input = compiled_res.get("floors", {})
    boundaries = compiled_res.get("boundaries", {})
    metrics = compiled_res.get("metrics", {})
    metadata = compiled_res.get("metadata", {})
    
    hierarchical_floors = []
    
    # Process each floor sequentially
    for floor_idx_str in sorted(floors_input.keys(), key=int):
        f_data = floors_input[floor_idx_str]
        layout = f_data.get("layout", {})
        geometry = f_data.get("geometry", {})
        
        walls = geometry.get("walls", [])
        doors = geometry.get("doors", [])
        windows = geometry.get("windows", [])
        
        rooms_list = []
        
        for room_name, room_coords in layout.items():
            # Find walls containing this room name
            room_walls = [
                {
                    "id": w["id"],
                    "start": w["start"],
                    "end": w["end"],
                    "type": w["type"],
                    "thickness": w["thickness"]
                }
                for w in walls if room_name in w.get("rooms", [])
            ]
            
            # Find doors containing this room name
            room_doors = [
                {
                    "id": d["id"],
                    "position": d["position"],
                    "direction": d["direction"],
                    "width": d["width"],
                    "type": d["type"]
                }
                for d in doors if room_name in d.get("rooms", [])
            ]
            
            # Find windows belonging to this room
            room_windows = [
                {
                    "id": win["id"],
                    "position": win["position"],
                    "direction": win["direction"],
                    "width": win["width"],
                    "type": win["type"]
                }
                for win in windows if win.get("room") == room_name
            ]
            
            # Construct room node
            rooms_list.append({
                "name": room_name,
                "type": room_coords.get("type"),
                "x": room_coords.get("x"),
                "y": room_coords.get("y"),
                "width": room_coords.get("width"),
                "height": room_coords.get("height"),
                "coordinates": room_coords.get("coordinates"),
                "walls": room_walls,
                "doors": room_doors,
                "windows": room_windows,
                "furniture": []  # Future expansion placeholder (Phase 8 requirement)
            })
            
        hierarchical_floors.append({
            "floor_level": int(floor_idx_str),
            "rooms": rooms_list
        })
        
    # Return complete hierarchical Project node
    return {
        "project": {
            "metadata": {
                "plot_width": metadata.get("plot_width"),
                "plot_depth": metadata.get("plot_depth"),
                "buildable_area_sqft": metadata.get("buildable_area_sqft"),
                "floors_count": metadata.get("floors_count"),
                "ots_generated_count": metadata.get("ots_generated_count")
            },
            "boundaries": {
                "envelope": boundaries.get("envelope", []),
                "stair_core": boundaries.get("stair_core", [])
            },
            "metrics": metrics,
            "floors": hierarchical_floors
        }
    }
