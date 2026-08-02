import pulp
import math
import os

def solve_layout(
    plot_width: float,
    plot_depth: float,
    setbacks: dict,
    stair_core_coords: tuple[float, float, float, float],  # (min_x, min_y, max_x, max_y)
    rooms: list[dict],
    adjacencies: list[tuple[str, str]] = None,
    road_edge: str = 'bottom',
    grid_snap: float = 0.5,
    time_limit_sec: int = 5
) -> dict:
    """
    Solves the room layout packing problem using Mixed-Integer Linear Programming (MILP).
    
    Args:
        plot_width: Width of the plot.
        plot_depth: Depth of the plot.
        setbacks: Dict of setbacks {'left', 'right', 'bottom', 'top'}.
        stair_core_coords: Bounding box of the stair core (min_x, min_y, max_x, max_y).
        rooms: List of room dictionaries.
        road_edge: Direction of the road ('bottom', 'top', 'left', 'right').
        grid_snap: Step size for grid snapping (default: 0.5 ft).
        time_limit_sec: Max solver runtime in seconds.
        
    Returns:
        Dict containing solver status, objective value, and room coordinates.
    """
    # Scale factor to convert float coordinates to integer variables for grid snapping
    S = 1.0 / grid_snap
    
    # Scale dimensions to integers
    pw_int = int(round(plot_width * S))
    pd_int = int(round(plot_depth * S))
    
    x_env_min = int(round(setbacks.get('left', 0.0) * S))
    x_env_max = pw_int - int(round(setbacks.get('right', 0.0) * S))
    y_env_min = int(round(setbacks.get('bottom', 0.0) * S))
    y_env_max = pd_int - int(round(setbacks.get('top', 0.0) * S))
    
    sc_x_min, sc_y_min, sc_x_max, sc_y_max = stair_core_coords
    sc_x_min_int = int(round(sc_x_min * S))
    sc_y_min_int = int(round(sc_y_min * S))
    sc_x_max_int = int(round(sc_x_max * S))
    sc_y_max_int = int(round(sc_y_max * S))
    
    # Big-M value: Maximum coordinate dimension
    M = max(pw_int, pd_int)
    
    # Initialize optimization problem
    prob = pulp.LpProblem("BuildingLayoutCompiler", pulp.LpMaximize)
    
    # Create variables for each room
    # x_i, y_i are bottom-left coordinates (as integers in grid units)
    # w_i, h_i are dimensions (as integers in grid units)
    x_vars = {}
    y_vars = {}
    w_vars = {}
    h_vars = {}
    x_prime_vars = {}
    y_prime_vars = {}
    orientation_vars = {}  # 1 = horizontal, 0 = vertical
    
    for room in rooms:
        name = room['name']
        
        # Determine room bounds in grid units
        min_w_int = int(round(room.get('min_width', 3.0) * S))
        min_h_int = int(round(room.get('min_height', 3.0) * S))
        
        # Continuous-like integer variables
        x_vars[name] = pulp.LpVariable(f"x_{name}", lowBound=x_env_min, upBound=x_env_max, cat=pulp.LpInteger)
        y_vars[name] = pulp.LpVariable(f"y_{name}", lowBound=y_env_min, upBound=y_env_max, cat=pulp.LpInteger)
        
        w_vars[name] = pulp.LpVariable(f"w_{name}", lowBound=min_w_int, upBound=x_env_max - x_env_min, cat=pulp.LpInteger)
        h_vars[name] = pulp.LpVariable(f"h_{name}", lowBound=min_h_int, upBound=y_env_max - y_env_min, cat=pulp.LpInteger)
        
        x_prime_vars[name] = pulp.LpVariable(f"x_prime_{name}", lowBound=x_env_min, upBound=x_env_max, cat=pulp.LpInteger)
        y_prime_vars[name] = pulp.LpVariable(f"y_prime_{name}", lowBound=y_env_min, upBound=y_env_max, cat=pulp.LpInteger)
        
        # Orientation variable for aspect ratio rotation
        orientation_vars[name] = pulp.LpVariable(f"o_{name}", cat=pulp.LpBinary)
        
        # Link coordinates
        prob += x_prime_vars[name] == x_vars[name] + w_vars[name], f"link_x_{name}"
        prob += y_prime_vars[name] == y_vars[name] + h_vars[name], f"link_y_{name}"
        
        # Keep rooms strictly inside buildable envelope boundaries
        prob += x_vars[name] >= x_env_min, f"bound_x_min_{name}"
        prob += x_prime_vars[name] <= x_env_max, f"bound_x_max_{name}"
        prob += y_vars[name] >= y_env_min, f"bound_y_min_{name}"
        prob += y_prime_vars[name] <= y_env_max, f"bound_y_max_{name}"
        
        # Avoid Stair Core (Obstacle) - only if stair core has non-zero area
        has_stair_core = (sc_x_max_int > sc_x_min_int) and (sc_y_max_int > sc_y_min_int)
        if has_stair_core:
            sc_bin = [pulp.LpVariable(f"b_sc_{name}_{k}", cat=pulp.LpBinary) for k in range(4)]
            prob += x_prime_vars[name] <= sc_x_min_int + M * (1 - sc_bin[0]), f"sc_left_{name}"
            prob += x_vars[name] >= sc_x_max_int - M * (1 - sc_bin[1]), f"sc_right_{name}"
            prob += y_prime_vars[name] <= sc_y_min_int + M * (1 - sc_bin[2]), f"sc_below_{name}"
            prob += y_vars[name] >= sc_y_max_int - M * (1 - sc_bin[3]), f"sc_above_{name}"
            prob += sum(sc_bin) >= 1, f"sc_overlap_{name}"
        
        # Aspect Ratio Constraints
        # Aspect ratio bounds (default 1.0 to 1.6)
        ar_min, ar_max = room.get('aspect_ratio_range', (1.0, 1.6))
        
        # o_i = 1: Horizontal (w >= h, w <= ar_max * h)
        # o_i = 0: Vertical (h >= w, h <= ar_max * w)
        prob += w_vars[name] - h_vars[name] >= -M * (1 - orientation_vars[name]), f"ar_orient_1_{name}"
        prob += w_vars[name] - ar_max * h_vars[name] <= M * (1 - orientation_vars[name]), f"ar_orient_2_{name}"
        
        prob += h_vars[name] - w_vars[name] >= -M * orientation_vars[name], f"ar_orient_3_{name}"
        prob += h_vars[name] - ar_max * w_vars[name] <= M * orientation_vars[name], f"ar_orient_4_{name}"
        
        # Area constraint: w_i * h_i >= A_i (min_area)
        # Using linear tangent approximation (convex boundary h_i_int >= A_int / w_i_int)
        min_area = room.get('min_area', 100.0)
        A_int = min_area * (S ** 2)
        
        # Sample 5 points for tangent lines based on range of valid widths
        w_start = max(min_w_int, int(math.sqrt(A_int / ar_max)))
        w_end = min(x_env_max - x_env_min, int(math.sqrt(A_int * ar_max)))
        
        if w_end > w_start:
            points = [w_start + i * (w_end - w_start) // 4 for i in range(5)]
            points = sorted(list(set(points)))  # Remove duplicates
        else:
            points = [w_start]
            
        for k, wk in enumerate(points):
            if wk <= 0:
                continue
            # Tangent line of h = A/w at wk is h >= 2A/wk - (A/wk^2)*w
            slope = A_int / (wk ** 2)
            intercept = 2 * A_int / wk
            prob += h_vars[name] >= intercept - slope * w_vars[name], f"area_tangent_{name}_{k}"
            
        # Adjacency to road (if applicable)
        if room.get('adjacent_to_road', False):
            if road_edge == 'bottom':
                prob += y_vars[name] == y_env_min, f"road_bottom_{name}"
            elif road_edge == 'top':
                prob += y_prime_vars[name] == y_env_max, f"road_top_{name}"
            elif road_edge == 'left':
                prob += x_vars[name] == x_env_min, f"road_left_{name}"
            elif road_edge == 'right':
                prob += x_prime_vars[name] == x_env_max, f"road_right_{name}"
                
    # Room-to-Room Non-Overlap Constraints
    room_names = [room['name'] for room in rooms]
    for i in range(len(room_names)):
        for j in range(i + 1, len(room_names)):
            ri = room_names[i]
            rj = room_names[j]
            
            # Non-overlap binary variables
            overlap_bin = [pulp.LpVariable(f"b_overlap_{ri}_{rj}_{k}", cat=pulp.LpBinary) for k in range(4)]
            
            # Constraints:
            # 1. ri is to the left of rj
            prob += x_prime_vars[ri] <= x_vars[rj] + M * (1 - overlap_bin[0]), f"overlap_left_{ri}_{rj}"
            # 2. ri is to the right of rj
            prob += x_vars[ri] >= x_prime_vars[rj] - M * (1 - overlap_bin[1]), f"overlap_right_{ri}_{rj}"
            # 3. ri is below rj
            prob += y_prime_vars[ri] <= y_vars[rj] + M * (1 - overlap_bin[2]), f"overlap_below_{ri}_{rj}"
            # 4. ri is above rj
            prob += y_vars[ri] >= y_prime_vars[rj] - M * (1 - overlap_bin[3]), f"overlap_above_{ri}_{rj}"
            
            # Enforce at least one non-overlapping boundary condition
            prob += sum(overlap_bin) >= 1, f"overlap_sum_{ri}_{rj}"
            
    # General touch helper function to enforce wall-sharing between two rooms
    def add_touch_constraint(r1: str, r2: str, D_touch: int, prefix: str):
        nonlocal prob
        # We need a 4-variable binary array to determine which side they touch on:
        # t_bin[0]: r1 is immediately to the left of r2 (r1.x_prime == r2.x)
        # t_bin[1]: r1 is immediately to the right of r2 (r1.x == r2.x_prime)
        # t_bin[2]: r1 is immediately below r2 (r1.y_prime == r2.y)
        # t_bin[3]: r1 is immediately above r2 (r1.y == r2.y_prime)
        t_bin = [pulp.LpVariable(f"t_{prefix}_{k}", cat=pulp.LpBinary) for k in range(4)]
        
        # Side 1: r1 is immediately to the left of r2
        prob += x_prime_vars[r1] - x_vars[r2] >= -M * (1 - t_bin[0]), f"{prefix}_left_1"
        prob += x_prime_vars[r1] - x_vars[r2] <= M * (1 - t_bin[0]), f"{prefix}_left_2"
        prob += y_prime_vars[r1] - y_vars[r2] >= D_touch - M * (1 - t_bin[0]), f"{prefix}_left_3"
        prob += y_prime_vars[r2] - y_vars[r1] >= D_touch - M * (1 - t_bin[0]), f"{prefix}_left_4"
        
        # Side 2: r1 is immediately to the right of r2
        prob += x_vars[r1] - x_prime_vars[r2] >= -M * (1 - t_bin[1]), f"{prefix}_right_1"
        prob += x_vars[r1] - x_prime_vars[r2] <= M * (1 - t_bin[1]), f"{prefix}_right_2"
        prob += y_prime_vars[r1] - y_vars[r2] >= D_touch - M * (1 - t_bin[1]), f"{prefix}_right_3"
        prob += y_prime_vars[r2] - y_vars[r1] >= D_touch - M * (1 - t_bin[1]), f"{prefix}_right_4"
        
        # Side 3: r1 is immediately below r2
        prob += y_prime_vars[r1] - y_vars[r2] >= -M * (1 - t_bin[2]), f"{prefix}_below_1"
        prob += y_prime_vars[r1] - y_vars[r2] <= M * (1 - t_bin[2]), f"{prefix}_below_2"
        prob += x_prime_vars[r1] - x_vars[r2] >= D_touch - M * (1 - t_bin[2]), f"{prefix}_below_3"
        prob += x_prime_vars[r2] - x_vars[r1] >= D_touch - M * (1 - t_bin[2]), f"{prefix}_below_4"
        
        # Side 4: r1 is immediately above r2
        prob += y_vars[r1] - y_prime_vars[r2] >= -M * (1 - t_bin[3]), f"{prefix}_above_1"
        prob += y_vars[r1] - y_prime_vars[r2] <= M * (1 - t_bin[3]), f"{prefix}_above_2"
        prob += x_prime_vars[r1] - x_vars[r2] >= D_touch - M * (1 - t_bin[3]), f"{prefix}_above_3"
        prob += x_prime_vars[r2] - x_vars[r1] >= D_touch - M * (1 - t_bin[3]), f"{prefix}_above_4"
        
        # Must touch on at least one side
        prob += sum(t_bin) >= 1, f"{prefix}_sum"

    # Enforce OTS ventilation touch constraints (minimum 2 ft shared wall)
    D_ots_touch_int = max(1, int(round(2.0 * S)))
    for room in rooms:
        name = room['name']
        ventilates_target = room.get('ventilates', None)
        if ventilates_target and ventilates_target in x_vars:
            add_touch_constraint(name, ventilates_target, D_ots_touch_int, f"ots_touch_{name}_{ventilates_target}")
            
    # Enforce door adjacency touch constraints (minimum 3 ft shared wall for access doorways)
    if adjacencies:
        D_door_touch_int = max(1, int(round(3.0 * S)))
        for idx, (r1, r2) in enumerate(adjacencies):
            # Only apply if both rooms are active/packed
            if r1 in x_vars and r2 in x_vars:
                r1_clean = r1.replace(" ", "_")
                r2_clean = r2.replace(" ", "_")
                add_touch_constraint(r1, r2, D_door_touch_int, f"adj_touch_{idx}_{r1_clean}_{r2_clean}")
            
    # Objective Function: Maximize the total perimeter/area sum of the rooms
    # Since area is non-linear, we maximize a weighted sum of width and height variables
    # to encourage rooms to expand and pack the envelope efficiently, reducing dead space.
    # We can also add a small penalty to keep coordinates compact.
    prob += sum(w_vars[name] + h_vars[name] for name in room_names), "Maximize_Room_Sizes"
    
    # Solve with time limit and optimization tolerances
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_sec, gapRel=0.10)
    
    # Configure custom temporary directory to handle spaces in Windows user profiles
    current_dir = os.path.dirname(os.path.abspath(__file__))
    tmp_dir = os.path.abspath(os.path.join(current_dir, "..", "tmp"))
    os.makedirs(tmp_dir, exist_ok=True)
    solver.tmpDir = tmp_dir
    
    status = prob.solve(solver)
    
    status_str = pulp.LpStatus[status]
    
    if status_str != "Optimal" and status_str != "Feasible":
        return {
            "status": status_str,
            "success": False,
            "error": f"MILP solver failed to find a valid layout. Status: {status_str}"
        }
        
    # Extract coordinates and convert back to actual float dimensions
    results = {}
    for name in room_names:
        rx = x_vars[name].varValue * grid_snap
        ry = y_vars[name].varValue * grid_snap
        rw = w_vars[name].varValue * grid_snap
        rh = h_vars[name].varValue * grid_snap
        
        results[name] = {
            "name": name,
            "type": next(r['type'] for r in rooms if r['name'] == name),
            "x": float(rx),
            "y": float(ry),
            "width": float(rw),
            "height": float(rh),
            "coordinates": [
                [float(rx), float(ry)],
                [float(rx), float(ry + rh)],
                [float(rx + rw), float(ry + rh)],
                [float(rx + rw), float(ry)]
            ]
        }
        
    return {
        "status": status_str,
        "success": True,
        "rooms": results
    }
