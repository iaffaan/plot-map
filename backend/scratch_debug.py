import pulp
import math
import os
import time
from engine.intent_parser import parse_intent_to_layout
from engine.geometry import create_plot, calculate_buildable_area
from engine.topology import build_room_graph, calculate_ventilation_and_ots

# 1. Setup payload
payload = {
    "plot": {"width": 43.75, "depth": 41.0},
    "setbacks": {"left": 1.5, "right": 1.5, "front": 3.0, "back": 2.0},
    "floors": 3,
    "description": "Generate an optimized residential building layout with maximum cross-ventilation and natural light",
    "time_limit_sec": 15
}

setbacks_data = payload.setdefault('setbacks', {})
if setbacks_data.get('front') is not None:
    setbacks_data['bottom'] = setbacks_data['front']
if setbacks_data.get('back') is not None:
    setbacks_data['top'] = setbacks_data['back']

net_buildable_area = (43.75 - 3.0) * (41.0 - 5.0) - 100.0

parsed = parse_intent_to_layout(
    description=payload['description'],
    plot_width=payload['plot']['width'],
    plot_depth=payload['plot']['depth'],
    setbacks=setbacks_data,
    floors=payload.get('floors', 1)
)

rooms = parsed['rooms']
adjacencies = parsed['adjacencies']
stair_core_cfg = parsed['stair_core']
width = payload['plot']['width']
depth = payload['plot']['depth']

grid_snap = 1.0

# 40% area target
total_requested_area = sum(r["min_area"] for r in rooms)
safety_target_area = 0.40 * net_buildable_area
scale_factor = safety_target_area / total_requested_area
scale_factor_dim = math.sqrt(scale_factor)

for r in rooms:
    r["min_area"] = max(20.0 if r["type"] == "Bathroom" else 50.0, r["min_area"] * scale_factor)
    r["min_width"] = max(3.0, r["min_width"] * scale_factor_dim)
    r["min_height"] = max(3.0, r["min_height"] * scale_factor_dim)

# 2. Geometry & Topology
plot = create_plot(width, depth)
envelope, core, buildable_area = calculate_buildable_area(plot, setbacks_data, stair_core_cfg)
core_bounds = core.bounds if not core.is_empty else (0.0, 0.0, 0.0, 0.0)

G = build_room_graph(rooms, adjacencies)
G_with_ots, ots_shafts = calculate_ventilation_and_ots(G)

all_rooms_to_pack = list(rooms)
for ots in ots_shafts:
    all_rooms_to_pack.append(ots)

# 3. Solver Setup
S = 1.0 / grid_snap
pw_int = int(round(width * S))
pd_int = int(round(depth * S))

x_env_min = int(round(setbacks_data.get('left', 0.0) * S))
x_env_max = pw_int - int(round(setbacks_data.get('right', 0.0) * S))
y_env_min = int(round(setbacks_data.get('bottom', 0.0) * S))
y_env_max = pd_int - int(round(setbacks_data.get('top', 0.0) * S))

sc_x_min, sc_y_min, sc_x_max, sc_y_max = core_bounds
sc_x_min_int = int(round(sc_x_min * S))
sc_y_min_int = int(round(sc_y_min * S))
sc_x_max_int = int(round(sc_x_max * S))
sc_y_max_int = int(round(sc_y_max * S))

M = 2 * max(pw_int, pd_int)

prob = pulp.LpProblem("BuildingLayoutCompiler", pulp.LpMaximize)

x_vars = {}
y_vars = {}
w_vars = {}
h_vars = {}
x_prime_vars = {}
y_prime_vars = {}
orientation_vars = {}

for room in all_rooms_to_pack:
    name = room['name']
    min_w_int = int(round(room.get('min_width', 3.0) * S))
    min_h_int = int(round(room.get('min_height', 3.0) * S))
    
    x_vars[name] = pulp.LpVariable(f"x_{name.replace(' ', '_')}", lowBound=x_env_min, upBound=x_env_max, cat=pulp.LpInteger)
    y_vars[name] = pulp.LpVariable(f"y_{name.replace(' ', '_')}", lowBound=y_env_min, upBound=y_env_max, cat=pulp.LpInteger)
    w_vars[name] = pulp.LpVariable(f"w_{name.replace(' ', '_')}", lowBound=min_w_int, upBound=x_env_max - x_env_min, cat=pulp.LpInteger)
    h_vars[name] = pulp.LpVariable(f"h_{name.replace(' ', '_')}", lowBound=min_h_int, upBound=y_env_max - y_env_min, cat=pulp.LpInteger)
    
    x_prime_vars[name] = pulp.LpVariable(f"x_prime_{name.replace(' ', '_')}", lowBound=x_env_min, upBound=x_env_max, cat=pulp.LpInteger)
    y_prime_vars[name] = pulp.LpVariable(f"y_prime_{name.replace(' ', '_')}", lowBound=y_env_min, upBound=y_env_max, cat=pulp.LpInteger)
    
    orientation_vars[name] = pulp.LpVariable(f"o_{name.replace(' ', '_')}", cat=pulp.LpBinary)
    
    prob += x_prime_vars[name] == x_vars[name] + w_vars[name]
    prob += y_prime_vars[name] == y_vars[name] + h_vars[name]
    
    prob += x_vars[name] >= x_env_min
    prob += x_prime_vars[name] <= x_env_max
    prob += y_vars[name] >= y_env_min
    prob += y_prime_vars[name] <= y_env_max
    
    # Stair Core Obstacle
    has_stair_core = (sc_x_max_int > sc_x_min_int) and (sc_y_max_int > sc_y_min_int)
    if has_stair_core:
        sc_bin = [pulp.LpVariable(f"b_sc_{name.replace(' ', '_')}_{k}", cat=pulp.LpBinary) for k in range(4)]
        prob += x_prime_vars[name] <= sc_x_min_int + M * (1 - sc_bin[0])
        prob += x_vars[name] >= sc_x_max_int - M * (1 - sc_bin[1])
        prob += y_prime_vars[name] <= sc_y_min_int + M * (1 - sc_bin[2])
        prob += y_vars[name] >= sc_y_max_int - M * (1 - sc_bin[3])
        prob += sum(sc_bin) >= 1

    # Aspect Ratio Constraints
    ar_min, ar_max = room.get('aspect_ratio_range', (1.0, 1.6))
    prob += w_vars[name] - h_vars[name] >= -M * (1 - orientation_vars[name])
    prob += w_vars[name] - ar_max * h_vars[name] <= M * (1 - orientation_vars[name])
    prob += h_vars[name] - w_vars[name] >= -M * orientation_vars[name]
    prob += h_vars[name] - ar_max * w_vars[name] <= M * orientation_vars[name]
    
    # Area Constraints (tangent approximation)
    min_area = room.get('min_area', 100.0)
    A_int = min_area * (S ** 2)
    w_start = max(min_w_int, int(math.sqrt(A_int / ar_max)))
    w_end = min(x_env_max - x_env_min, int(math.sqrt(A_int * ar_max)))
    
    if w_end > w_start:
        points = [w_start + i * (w_end - w_start) // 4 for i in range(5)]
        points = sorted(list(set(points)))
    else:
        points = [w_start]
        
    for k, wk in enumerate(points):
        if wk <= 0: continue
        slope = A_int / (wk ** 2)
        intercept = 2 * A_int / wk
        prob += h_vars[name] >= intercept - slope * w_vars[name]
        
    if room.get('adjacent_to_road', False):
        prob += y_vars[name] == y_env_min

# Room-to-Room Non-Overlap Constraints & Storage
overlap_vars_dict = {}
room_names = [r['name'] for r in all_rooms_to_pack]
for i in range(len(room_names)):
    for j in range(i + 1, len(room_names)):
        ri = room_names[i]
        rj = room_names[j]
        overlap_bin = [pulp.LpVariable(f"b_overlap_{ri.replace(' ', '_')}_{rj.replace(' ', '_')}_{k}", cat=pulp.LpBinary) for k in range(4)]
        prob += x_prime_vars[ri] <= x_vars[rj] + M * (1 - overlap_bin[0])
        prob += x_vars[ri] >= x_prime_vars[rj] - M * (1 - overlap_bin[1])
        prob += y_prime_vars[ri] <= y_vars[rj] + M * (1 - overlap_bin[2])
        prob += y_vars[ri] >= y_prime_vars[rj] - M * (1 - overlap_bin[3])
        prob += sum(overlap_bin) >= 1
        
        # Store for reuse in touch constraints
        key = tuple(sorted([ri, rj]))
        overlap_vars_dict[key] = (overlap_bin, ri, rj)

def add_optimized_touch_constraint(p, r1: str, r2: str, D_touch: int):
    # Lookup the overlap_bin variables for this pair
    key = tuple(sorted([r1, r2]))
    if key not in overlap_vars_dict:
        print(f"Error: {r1} and {r2} overlap vars not found!")
        return
    
    overlap_bin, u, v = overlap_vars_dict[key]
    # u and v are ordered. Determine if r1 is u or v
    is_r1_u = (r1 == u)
    
    # overlap_bin mapping:
    # 0: u is to the left of v (u.x_prime <= v.x)
    # 1: u is to the right of v (u.x >= v.x_prime)
    # 2: u is below v (u.y_prime <= v.y)
    # 3: u is above v (u.y >= v.y_prime)
    
    if is_r1_u:
        # Side 0: u (r1) is to the left of v (r2)
        p += x_prime_vars[r1] >= x_vars[r2] - M * (1 - overlap_bin[0])
        p += y_prime_vars[r1] - y_vars[r2] >= D_touch - M * (1 - overlap_bin[0])
        p += y_prime_vars[r2] - y_vars[r1] >= D_touch - M * (1 - overlap_bin[0])
        
        # Side 1: u (r1) is to the right of v (r2)
        p += x_vars[r1] <= x_prime_vars[r2] + M * (1 - overlap_bin[1])
        p += y_prime_vars[r1] - y_vars[r2] >= D_touch - M * (1 - overlap_bin[1])
        p += y_prime_vars[r2] - y_vars[r1] >= D_touch - M * (1 - overlap_bin[1])
        
        # Side 2: u (r1) is below v (r2)
        p += y_prime_vars[r1] >= y_vars[r2] - M * (1 - overlap_bin[2])
        p += x_prime_vars[r1] - x_vars[r2] >= D_touch - M * (1 - overlap_bin[2])
        p += x_prime_vars[r2] - x_vars[r1] >= D_touch - M * (1 - overlap_bin[2])
        
        # Side 3: u (r1) is above v (r2)
        p += y_vars[r1] <= y_prime_vars[r2] + M * (1 - overlap_bin[3])
        p += x_prime_vars[r1] - x_vars[r2] >= D_touch - M * (1 - overlap_bin[3])
        p += x_prime_vars[r2] - x_vars[r1] >= D_touch - M * (1 - overlap_bin[3])
    else:
        # Side 0: v (r1) is to the left of u (r2) -> u (r2) is to the right of v (r1) -> overlap_bin[1]
        p += x_prime_vars[r1] >= x_vars[r2] - M * (1 - overlap_bin[1])
        p += y_prime_vars[r1] - y_vars[r2] >= D_touch - M * (1 - overlap_bin[1])
        p += y_prime_vars[r2] - y_vars[r1] >= D_touch - M * (1 - overlap_bin[1])
        
        # Side 1: v (r1) is to the right of u (r2) -> u (r2) is to the left of v (r1) -> overlap_bin[0]
        p += x_vars[r1] <= x_prime_vars[r2] + M * (1 - overlap_bin[0])
        p += y_prime_vars[r1] - y_vars[r2] >= D_touch - M * (1 - overlap_bin[0])
        p += y_prime_vars[r2] - y_vars[r1] >= D_touch - M * (1 - overlap_bin[0])
        
        # Side 2: v (r1) is below u (r2) -> u (r2) is above v (r1) -> overlap_bin[3]
        p += y_prime_vars[r1] >= y_vars[r2] - M * (1 - overlap_bin[3])
        p += x_prime_vars[r1] - x_vars[r2] >= D_touch - M * (1 - overlap_bin[3])
        p += x_prime_vars[r2] - x_vars[r1] >= D_touch - M * (1 - overlap_bin[3])
        
        # Side 3: v (r1) is above u (r2) -> u (r2) is below v (r1) -> overlap_bin[2]
        p += y_vars[r1] <= y_prime_vars[r2] + M * (1 - overlap_bin[2])
        p += x_prime_vars[r1] - x_vars[r2] >= D_touch - M * (1 - overlap_bin[2])
        p += x_prime_vars[r2] - x_vars[r1] >= D_touch - M * (1 - overlap_bin[2])

# Enforce OTS touch
D_ots_touch_int = max(1, int(round(2.0 * S)))
for room in all_rooms_to_pack:
    name = room['name']
    vent_target = room.get('ventilates')
    if vent_target and vent_target in x_vars:
        add_optimized_touch_constraint(prob, name, vent_target, D_ots_touch_int)

# Enforce Adjacencies touch
D_door_touch_int = max(1, int(round(3.0 * S)))
for idx, (r1, r2) in enumerate(adjacencies):
    if r1 in x_vars and r2 in x_vars:
        add_optimized_touch_constraint(prob, r1, r2, D_door_touch_int)

# Objective
prob += sum(w_vars[name] + h_vars[name] for name in room_names)

# Solve with msg=True and custom tmpDir
solver = pulp.PULP_CBC_CMD(msg=True, timeLimit=15)
current_dir = os.path.dirname(os.path.abspath(__file__))
tmp_dir = os.path.abspath(os.path.join(current_dir, "tmp"))
os.makedirs(tmp_dir, exist_ok=True)
solver.tmpDir = tmp_dir

status = prob.solve(solver)

print(f"\nStatus: {pulp.LpStatus[status]}")
if pulp.LpStatus[status] == "Optimal":
    print("SOLVED SUCCESSFULLY!")
