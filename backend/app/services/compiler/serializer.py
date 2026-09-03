from app.services.geometry.compiler import compile_geometry
from app.services.geometry.metrics import calculate_layout_metrics
from app.services.geometry.renderer import generate_hierarchical_json
from app.services.geometry.setbacks import calculate_buildable_area, create_plot
from app.services.geometry.topology import (
    build_room_graph,
    calculate_ventilation_and_ots,
    validate_privacy,
)
from app.services.optimization.solver import solve_layout


def compile_blueprint(payload: dict) -> dict:
    """
    Orchestrates the entire Uncharted building compiler pipeline:
    
    1. Parse input payload.
    2. Build master plot polygon, apply setbacks, and place stair core (Geometry).
    3. Construct the room graph, validate privacy flow, compute ventilation,
       and procedurally generate OTS shafts if needed (Topology).
    4. Solve room packing via mixed-integer linear programming (Optimization).
    5. Construct the final spatial coordinate output or return error logs.
    """
    try:
        # --- 1. Parse Input Parameters ---
        plot_cfg = payload.get('plot', {})
        width = float(plot_cfg.get('width', 40.0))
        depth = float(plot_cfg.get('depth', 40.0))
        
        setbacks = payload.get('setbacks', {'left': 0.0, 'right': 0.0, 'bottom': 0.0, 'top': 0.0})
        stair_core_cfg = payload.get('stair_core', {'width': 0.0, 'height': 0.0, 'edge': 'bottom-left'})
        
        rooms = payload.get('rooms', [])
        adjacencies = payload.get('adjacencies', [])
        road_edge = payload.get('road_edge', 'bottom')
        grid_snap = float(payload.get('grid_snap', 0.5))
        time_limit_sec = int(payload.get('time_limit_sec', 5))
        floors = int(payload.get('floors', 1))
        ventilation_weight = payload.get('ventilation_weight')
        prioritize_ventilation = bool(payload.get('prioritize_ventilation', False))
        
        # --- 2. Geometric Layer ---
        plot = create_plot(width, depth)
        envelope, core, buildable_area = calculate_buildable_area(plot, setbacks, stair_core_cfg)
        
        if buildable_area.is_empty or not buildable_area.is_valid:
            return {
                "success": False,
                "error": "The buildable envelope is invalid or empty. Check that setbacks do not exceed plot boundaries."
            }
            
        core_bounds = core.bounds if not core.is_empty else (0.0, 0.0, 0.0, 0.0)
        output_envelope_coords = list(envelope.exterior.coords) if not envelope.is_empty else []
        output_core_coords = list(core.exterior.coords) if not core.is_empty else []

        # --- 3. Solve each floor sequentially ---
        floors_data = {}
        plumbing_cores = []
        total_ots_generated = 0
        previous_floor_footprint = None
        
        for floor_idx in range(1, floors + 1):
            # Filter rooms for current floor
            floor_rooms = [r for r in rooms if r.get('floor_assignment', 1) == floor_idx]
            
            # If no rooms are assigned to this floor, skip
            if not floor_rooms:
                floors_data[str(floor_idx)] = {
                    "layout": {},
                    "geometry": {"walls": [], "doors": [], "windows": []}
                }
                continue
                
            # Filter adjacencies for current floor
            floor_room_names = {r['name'] for r in floor_rooms}
            floor_adjacencies = [(u, v) for u, v in adjacencies if u in floor_room_names and v in floor_room_names]
            
            # Build Room Graph for this floor
            G = build_room_graph(floor_rooms, floor_adjacencies)
            
            # Validate privacy for this floor
            privacy_passed, privacy_msg = validate_privacy(G)
            if not privacy_passed:
                return {
                    "success": False,
                    "error": f"Topological Validation Error (Floor {floor_idx}): {privacy_msg}"
                }
                
            # Ventilation & OTS Shafts for this floor
            _G_with_ots, floor_ots_shafts = calculate_ventilation_and_ots(G, setbacks)
            total_ots_generated += len(floor_ots_shafts)
            
            # Merge OTS shafts
            rooms_to_pack = list(floor_rooms) + list(floor_ots_shafts)
            
            # Solve layout for this floor
            solver_res = solve_layout(
                plot_width=width,
                plot_depth=depth,
                setbacks=setbacks,
                stair_core_coords=core_bounds,
                rooms=rooms_to_pack,
                adjacencies=floor_adjacencies,
                road_edge=road_edge,
                grid_snap=grid_snap,
                time_limit_sec=time_limit_sec,
                plumbing_cores=plumbing_cores,
                ventilation_weight=ventilation_weight,
                prioritize_ventilation=prioritize_ventilation,
                lower_floor_footprint=previous_floor_footprint
            )
            
            if not solver_res.get('success', False):
                return {
                    "success": False,
                    "error": f"Optimization Constraint Solver Error (Floor {floor_idx}): {solver_res.get('error', 'Unsolvable constraints.')}"
                }
                
            # Extract bathroom coordinates for plumbing cores alignment on next floors
            floor_layout_rooms = solver_res.get('rooms', {})
            for room in floor_layout_rooms.values():
                if room['type'] == 'Bathroom':
                    rx, ry, rw, rh = room['x'], room['y'], room['width'], room['height']
                    plumbing_cores.append((rx, ry, rx + rw, ry + rh))
                    
            # Record current floor footprint to constrain upper floors
            if floor_layout_rooms:
                cf_min_x = min(r['x'] for r in floor_layout_rooms.values())
                cf_max_x = max(r['x'] + r['width'] for r in floor_layout_rooms.values())
                cf_min_y = min(r['y'] for r in floor_layout_rooms.values())
                cf_max_y = max(r['y'] + r['height'] for r in floor_layout_rooms.values())
                previous_floor_footprint = (cf_min_x, cf_min_y, cf_max_x, cf_max_y)
                    
            # Compile detailed geometry for this floor
            geometry_detail = compile_geometry(
                layout_rooms=solver_res.get('rooms', {}),
                envelope_coords=output_envelope_coords,
                stair_core_coords=output_core_coords,
                adjacencies=floor_adjacencies
            )
            
            floors_data[str(floor_idx)] = {
                "layout": solver_res.get('rooms', {}),
                "geometry": geometry_detail
            }
            
        # Ensure we have Ground Floor (Floor 1) data for backward compatibility
        g_floor_data = floors_data.get("1", {"layout": {}, "geometry": {"walls": [], "doors": [], "windows": []}})
        
        # Calculate performance and engineering metrics
        metrics = calculate_layout_metrics(
            plot_width=width,
            plot_depth=depth,
            floors_data=floors_data,
            stair_core_cfg=stair_core_cfg
        )
        
        raw_res = {
            "success": True,
            "metadata": {
                "plot_width": width,
                "plot_depth": depth,
                "buildable_area_sqft": buildable_area.area,
                "ots_generated_count": total_ots_generated,
                "floors_count": floors
            },
            "boundaries": {
                "envelope": output_envelope_coords,
                "stair_core": output_core_coords
            },
            "layout": g_floor_data["layout"],
            "geometry": g_floor_data["geometry"],
            "floors": floors_data,
            "metrics": metrics
        }
        
        # Generate the hierarchical Project render tree
        render_tree = generate_hierarchical_json(raw_res)
        raw_res["render_tree"] = render_tree
        
        return raw_res
        
    except Exception as e:  # noqa: BLE001
        return {
            "success": False,
            "error": f"Compilation failed due to internal exception: {e!s}"
        }
