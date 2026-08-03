from engine.geometry import create_plot, calculate_buildable_area
from engine.topology import build_room_graph, validate_privacy, calculate_ventilation_and_ots
from engine.solver import solve_layout
from shapely.geometry import Polygon

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
        
        # --- 2. Geometric Layer ---
        plot = create_plot(width, depth)
        envelope, core, buildable_area = calculate_buildable_area(plot, setbacks, stair_core_cfg)
        
        if buildable_area.is_empty or not buildable_area.is_valid:
            return {
                "success": False,
                "error": "The buildable envelope is invalid or empty. Check that setbacks do not exceed plot boundaries."
            }
            
        core_bounds = core.bounds if not core.is_empty else (0.0, 0.0, 0.0, 0.0)
        
        # --- 3. Topological Layer ---
        # Build DAG
        G = build_room_graph(rooms, adjacencies)
        
        # Privacy check
        privacy_passed, privacy_msg = validate_privacy(G)
        if not privacy_passed:
            return {
                "success": False,
                "error": f"Topological Validation Error: {privacy_msg}"
            }
            
        # Ventilation & Procedural OTS Shaft Generation
        G_with_ots, ots_shafts = calculate_ventilation_and_ots(G, setbacks)
        
        # Merge OTS shafts into rooms list for packing
        all_rooms_to_pack = list(rooms)
        for ots in ots_shafts:
            all_rooms_to_pack.append(ots)
            
        # --- 4. Optimization Layer (Solver) ---
        print("\n=== DEBUG SOLVE LAYOUT INPUTS ===")
        print(f"width: {width}, depth: {depth}")
        print(f"setbacks: {setbacks}")
        print(f"core_bounds: {core_bounds}")
        print(f"grid_snap: {grid_snap}, time_limit_sec: {time_limit_sec}")
        print("rooms:")
        for r in all_rooms_to_pack:
            print(f"  - {r.get('name')}: min_area={r.get('min_area')}, min_w={r.get('min_width')}, min_h={r.get('min_height')}, road={r.get('adjacent_to_road')}, vent={r.get('requires_ventilation')}")
        print(f"adjacencies: {adjacencies}")
        print("==================================\n")
        
        solver_res = solve_layout(
            plot_width=width,
            plot_depth=depth,
            setbacks=setbacks,
            stair_core_coords=core_bounds,
            rooms=all_rooms_to_pack,
            adjacencies=adjacencies,
            road_edge=road_edge,
            grid_snap=grid_snap,
            time_limit_sec=time_limit_sec
        )
        
        if not solver_res.get('success', False):
            return {
                "success": False,
                "error": f"Optimization Constraint Solver Error: {solver_res.get('error', 'Unsolvable constraints.')}"
            }
            
        # --- 5. Compile Output ---
        # Add metadata and original geometry layers
        output_envelope_coords = list(envelope.exterior.coords) if not envelope.is_empty else []
        output_core_coords = list(core.exterior.coords) if not core.is_empty else []
        
        return {
            "success": True,
            "metadata": {
                "plot_width": width,
                "plot_depth": depth,
                "buildable_area_sqft": buildable_area.area,
                "ots_generated_count": len(ots_shafts)
            },
            "boundaries": {
                "envelope": output_envelope_coords,
                "stair_core": output_core_coords
            },
            "layout": solver_res.get('rooms', {})
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Compilation failed due to internal exception: {str(e)}"
        }
