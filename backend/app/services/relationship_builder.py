from typing import Any, Dict, List, Set, Tuple
from app.core.tbm import Plot, Room, Wall, Opening, Junction, Floor, Stair, Column, Beam, Building

def snap_coord(c: float, tolerance: float = 0.05) -> float:
    """Snaps a coordinate to clean grid alignment based on tolerance."""
    return round(c * 2) / 2  # default snap to 0.5 ft grid

def build_tbm_from_layout(payload: Dict[str, Any], compiled_result: Dict[str, Any]) -> Building:
    """
    Constructs a complete Topological Building Model (TBM) from the compiled MILP layout.
    """
    # 1. Parse and build Plot
    plot_cfg = payload.get("plot", {})
    width = float(plot_cfg.get("width", 40.0))
    depth = float(plot_cfg.get("depth", 40.0))
    setbacks = payload.get("setbacks", {"left": 0.0, "right": 0.0, "bottom": 0.0, "top": 0.0})
    
    boundary_coords = [(0.0, 0.0), (width, 0.0), (width, depth), (0.0, depth)]
    plot = Plot(
        id="plot_0",
        width=width,
        depth=depth,
        boundary_coords=boundary_coords,
        road_edge=payload.get("road_edge", "bottom"),
        setbacks=setbacks
    )
    
    building = Building(
        id="building_0",
        plot=plot,
        name=payload.get("project_name", "Uncharted CAD Drawing")
    )
    
    floors_data = compiled_result.get("floors", {})
    if not floors_data:
        floors_data = {"1": {
            "layout": compiled_result.get("layout", {}),
            "geometry": compiled_result.get("geometry", {})
        }}
        
    for floor_idx_str, floor_content in floors_data.items():
        floor_level = int(floor_idx_str)
        floor_id = f"floor_{floor_level}"
        
        # Instantiate Floor
        floor = Floor(
            id=floor_id,
            floor_level=floor_level,
            elevation=(floor_level - 1) * 10.0,
            height=10.0
        )
        
        # Populate rooms
        layout = floor_content.get("layout", {})
        rooms_map: Dict[str, Room] = {}
        
        for r_name, r_data in layout.items():
            r_id = f"{floor_id}_room_{r_name.lower().replace(' ', '_')}"
            room = Room(
                id=r_id,
                name=r_name,
                type=r_data.get("type", "Living Room"),
                floor_id=floor_id,
                min_area=r_data.get("width", 10.0) * r_data.get("height", 10.0),
                target_area=r_data.get("width", 10.0) * r_data.get("height", 10.0)
            )
            rooms_map[r_name] = room
            floor.room_ids.append(r_id)
            building.rooms[r_id] = room
            
        # Extract Junctions and Walls from packed room rectangles
        horizontal_edges: List[Tuple[float, float, float, str]] = []  # (y, x_start, x_end, room_name)
        vertical_edges: List[Tuple[float, float, float, str]] = []    # (x, y_start, y_end, room_name)
        corners: Set[Tuple[float, float]] = set()
        
        for r_name, r_data in layout.items():
            x = float(r_data.get("x", 0.0))
            y = float(r_data.get("y", 0.0))
            w = float(r_data.get("width", 10.0))
            h = float(r_data.get("height", 10.0))
            
            x1, x2 = snap_coord(x), snap_coord(x + w)
            y1, y2 = snap_coord(y), snap_coord(y + h)
            
            corners.add((x1, y1))
            corners.add((x2, y1))
            corners.add((x2, y2))
            corners.add((x1, y2))
            
            horizontal_edges.append((y1, x1, x2, r_name))
            horizontal_edges.append((y2, x1, x2, r_name))
            vertical_edges.append((x1, y1, y2, r_name))
            vertical_edges.append((x2, y1, y2, r_name))
            
        # Create unique Junctions
        junctions_list = sorted(list(corners))
        junction_coords_to_id: Dict[Tuple[float, float], str] = {}
        junctions_map: Dict[str, Junction] = {}
        
        for j_idx, (jx, jy) in enumerate(junctions_list):
            j_id = f"{floor_id}_j_{j_idx}"
            junction = Junction(id=j_id, x=jx, y=jy, floor_id=floor_id)
            junctions_map[j_id] = junction
            junction_coords_to_id[(jx, jy)] = j_id
            floor.junction_ids.append(j_id)
            building.junctions[j_id] = junction
            
        # Build Wall segments between adjacent junctions
        walls_map: Dict[str, Wall] = {}
        wall_counter = 0
        
        # Helper to find room adjacency along segment
        def find_separating_rooms(
            coord: float, start: float, end: float, is_horizontal: bool
        ) -> Tuple[str, str]:
            room_a, room_b = "", ""
            eps = 0.1
            for r_name, r_data in layout.items():
                rx = float(r_data.get("x", 0.0))
                ry = float(r_data.get("y", 0.0))
                rw = float(r_data.get("width", 10.0))
                rh = float(r_data.get("height", 10.0))
                
                rx1, rx2 = snap_coord(rx), snap_coord(rx + rw)
                ry1, ry2 = snap_coord(ry), snap_coord(ry + rh)
                
                if is_horizontal:
                    if abs(ry1 - coord) < eps and rx1 <= start + eps and rx2 >= end - eps:
                        room_a = r_name
                    if abs(ry2 - coord) < eps and rx1 <= start + eps and rx2 >= end - eps:
                        room_b = r_name
                else:
                    if abs(rx1 - coord) < eps and ry1 <= start + eps and ry2 >= end - eps:
                        room_a = r_name
                    if abs(rx2 - coord) < eps and ry1 <= start + eps and ry2 >= end - eps:
                        room_b = r_name
            return room_a, room_b

        # Process horizontal walls
        for y_val in sorted(list({y for y, _, _, _ in horizontal_edges})):
            line_junctions = sorted([j for j in junctions_list if j[1] == y_val], key=lambda j: j[0])
            for k in range(len(line_junctions) - 1):
                jx1, jy1 = line_junctions[k]
                jx2, jy2 = line_junctions[k+1]
                
                connected = False
                for y, x_start, x_end, _ in horizontal_edges:
                    if abs(y - y_val) < 0.05 and x_start <= jx1 + 0.05 and x_end >= jx2 - 0.05:
                        connected = True
                        break
                        
                if connected:
                    r_a, r_b = find_separating_rooms(y_val, jx1, jx2, is_horizontal=True)
                    w_id = f"{floor_id}_w_{wall_counter}"
                    wall_counter += 1
                    
                    wall = Wall(
                        id=w_id,
                        floor_id=floor_id,
                        thickness=0.75,
                        start_junction_id=junction_coords_to_id[(jx1, jy1)],
                        end_junction_id=junction_coords_to_id[(jx2, jy2)],
                        room_a_id=rooms_map[r_a].id if r_a else "",
                        room_b_id=rooms_map[r_b].id if r_b else ""
                    )
                    walls_map[w_id] = wall
                    floor.wall_ids.append(w_id)
                    building.walls[w_id] = wall
                    
                    junctions_map[wall.start_junction_id].connected_wall_ids.append(w_id)
                    junctions_map[wall.end_junction_id].connected_wall_ids.append(w_id)
                    
                    if r_a:
                        rooms_map[r_a].bounded_by_wall_ids.append(w_id)
                    if r_b:
                        rooms_map[r_b].bounded_by_wall_ids.append(w_id)

        # Process vertical walls
        for x_val in sorted(list({x for x, _, _, _ in vertical_edges})):
            line_junctions = sorted([j for j in junctions_list if j[0] == x_val], key=lambda j: j[1])
            for k in range(len(line_junctions) - 1):
                jx1, jy1 = line_junctions[k]
                jx2, jy2 = line_junctions[k+1]
                
                connected = False
                for x, y_start, y_end, _ in vertical_edges:
                    if abs(x - x_val) < 0.05 and y_start <= jy1 + 0.05 and y_end >= jy2 - 0.05:
                        connected = True
                        break
                        
                if connected:
                    r_a, r_b = find_separating_rooms(x_val, jy1, jy2, is_horizontal=False)
                    w_id = f"{floor_id}_w_{wall_counter}"
                    wall_counter += 1
                    
                    wall = Wall(
                        id=w_id,
                        floor_id=floor_id,
                        thickness=0.75,
                        start_junction_id=junction_coords_to_id[(jx1, jy1)],
                        end_junction_id=junction_coords_to_id[(jx2, jy2)],
                        room_a_id=rooms_map[r_a].id if r_a else "",
                        room_b_id=rooms_map[r_b].id if r_b else ""
                    )
                    walls_map[w_id] = wall
                    floor.wall_ids.append(w_id)
                    building.walls[w_id] = wall
                    
                    junctions_map[wall.start_junction_id].connected_wall_ids.append(w_id)
                    junctions_map[wall.end_junction_id].connected_wall_ids.append(w_id)
                    
                    if r_a:
                        rooms_map[r_a].bounded_by_wall_ids.append(w_id)
                    if r_b:
                        rooms_map[r_b].bounded_by_wall_ids.append(w_id)

        # Place Door and Window openings
        opening_counter = 0
        for w_id, wall in list(walls_map.items()):
            if wall.room_a_id and wall.room_b_id:
                o_id = f"{floor_id}_op_{opening_counter}"
                opening_counter += 1
                opening = Opening(
                    id=o_id,
                    type="Door",
                    wall_id=w_id,
                    width=3.0,
                    height=7.0,
                    position_offset=1.5,
                    connects_room_a_id=wall.room_a_id,
                    connects_room_b_id=wall.room_b_id
                )
                wall.hosted_opening_ids.append(o_id)
                floor.opening_ids.append(o_id)
                building.openings[o_id] = opening
            elif wall.room_a_id or wall.room_b_id:
                o_id = f"{floor_id}_op_{opening_counter}"
                opening_counter += 1
                opening = Opening(
                    id=o_id,
                    type="Window",
                    wall_id=w_id,
                    width=4.0,
                    height=4.0,
                    sill_height=3.0,
                    position_offset=2.0
                )
                wall.hosted_opening_ids.append(o_id)
                floor.opening_ids.append(o_id)
                building.openings[o_id] = opening
                
        # Register floor inside building
        building.floor_ids.append(floor_id)
        building.floors[floor_id] = floor
        
    return building
