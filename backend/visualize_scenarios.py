import json
import os
from engine.orchestrator import compile_blueprint

def generate_svg(compile_result, width, depth, filename):
    """Generates an SVG file representing the compiled room layout."""
    if not compile_result.get("success"):
        print(f"[-] Cannot generate SVG for {filename}: compilation failed.")
        return
        
    scale = 15  # Scale factor: 1 foot = 15 pixels
    svg_w = width * scale
    svg_h = depth * scale
    
    # Modern dark theme colors matching Bharat real estate layout design
    colors = {
        "Entrance": "#89b4fa",       # Pastel Blue
        "Living Room": "#cba6f7",     # Pastel Purple
        "Kitchen": "#f9e2af",         # Pastel Yellow
        "Bedroom": "#a6e3a1",         # Pastel Green
        "Bathroom": "#f2cdcd",        # Pastel Pink
        "Corridor": "#94e2d5",        # Pastel Teal
        "OTS": "#74c7ec"              # Sky Blue (shafts)
    }
    
    svg = [
        f'<svg width="{svg_w + 80}" height="{svg_h + 80}" viewBox="-40 -40 {svg_w + 80} {svg_h + 80}" xmlns="http://www.w3.org/2000/svg" style="background-color: #1e1e2e; font-family: system-ui, sans-serif;">',
        # Draw background grid lines (every 5 ft)
    ]
    
    # 5ft grid
    for x in range(0, int(width) + 1, 5):
        x_px = x * scale
        svg.append(f'  <line x1="{x_px}" y1="0" x2="{x_px}" y2="{svg_h}" stroke="#313244" stroke-width="1" stroke-dasharray="2,2"/>')
        svg.append(f'  <text x="{x_px}" y="-10" fill="#a6adc8" font-size="10" text-anchor="middle">{x}ft</text>')
        
    for y in range(0, int(depth) + 1, 5):
        y_px = y * scale
        y_svg = svg_h - y_px  # Invert Y for SVG rendering
        svg.append(f'  <line x1="0" y1="{y_svg}" x2="{svg_w}" y2="{y_svg}" stroke="#313244" stroke-width="1" stroke-dasharray="2,2"/>')
        svg.append(f'  <text x="-10" y="{y_svg + 4}" fill="#a6adc8" font-size="10" text-anchor="end">{y}ft</text>')
        
    # Draw Master Plot boundary
    svg.append(f'  <rect x="0" y="0" width="{svg_w}" height="{svg_h}" fill="none" stroke="#f38ba8" stroke-width="3" rx="4" />')
    svg.append(f'  <text x="{svg_w/2}" y="{svg_h + 20}" fill="#f38ba8" font-size="12" font-weight="bold" text-anchor="middle">Master Plot: {width} x {depth} ft</text>')
    
    # Draw Buildable Envelope (after setbacks)
    envelope = compile_result["boundaries"]["envelope"]
    if envelope:
        points_str = " ".join([f"{c[0]*scale},{svg_h - c[1]*scale}" for c in envelope])
        svg.append(f'  <polygon points="{points_str}" fill="#181825" stroke="#a6e3a1" stroke-width="2" stroke-dasharray="5,5" />')
        
    # Draw Stair Core
    core = compile_result["boundaries"]["stair_core"]
    if core:
        points_str = " ".join([f"{c[0]*scale},{svg_h - c[1]*scale}" for c in core])
        svg.append(f'  <polygon points="{points_str}" fill="#f38ba8" fill-opacity="0.25" stroke="#f38ba8" stroke-width="2" />')
        
        # Center of stair core for label
        xs = [c[0] for c in core[:-1]]
        ys = [c[1] for c in core[:-1]]
        cx = (sum(xs) / len(xs)) * scale
        cy = svg_h - (sum(ys) / len(ys)) * scale
        svg.append(f'  <text x="{cx}" y="{cy}" fill="#f38ba8" font-size="11" font-weight="bold" text-anchor="middle" dominant-baseline="middle">Staircase</text>')
        
    # Draw Rooms
    layout = compile_result["layout"]
    for rname, rdata in layout.items():
        rx = rdata["x"] * scale
        rw = rdata["width"] * scale
        rh = rdata["height"] * scale
        ry = svg_h - (rdata["y"] + rdata["height"]) * scale
        
        rtype = rdata["type"]
        color = colors.get(rtype, "#cdd6f4")
        fill_opacity = 0.85 if rtype != "OTS" else 0.4
        stroke_color = "#11111b" if rtype != "OTS" else "#74c7ec"
        stroke_width = 2 if rtype != "OTS" else 1.5
        
        # Room box
        svg.append(f'  <rect x="{rx}" y="{ry}" width="{rw}" height="{rh}" fill="{color}" fill-opacity="{fill_opacity}" stroke="{stroke_color}" stroke-width="{stroke_width}" rx="4" />')
        
        # Text Label
        cx = rx + rw / 2
        cy = ry + rh / 2
        text_color = "#11111b" if rtype != "OTS" else "#74c7ec"
        svg.append(f'  <text x="{cx}" y="{cy - 5}" fill="{text_color}" font-size="11" font-weight="bold" text-anchor="middle" dominant-baseline="middle">{rname}</text>')
        svg.append(f'  <text x="{cx}" y="{cy + 8}" fill="{text_color}" fill-opacity="0.8" font-size="9" text-anchor="middle" dominant-baseline="middle">{rdata["width"]}x{rdata["height"]} ft</text>')
        
    svg.append('</svg>')
    
    with open(filename, "w") as f:
        f.write("\n".join(svg))
    print(f"[+] Successfully generated vector visualization: {filename}")

# ================= Scenarios definition =================

# 1. Standard Compliant Scenario (40x40 ft, setbacks on all sides, standard rooms)
scenario_standard = {
    'plot': {'width': 40.0, 'depth': 40.0},
    'setbacks': {'left': 5.0, 'right': 5.0, 'bottom': 5.0, 'top': 5.0},
    'stair_core': {'width': 10.0, 'height': 10.0, 'edge': 'bottom-left'},
    'road_edge': 'bottom',
    'rooms': [
        {'name': 'Entrance Lobby', 'type': 'Entrance', 'min_area': 16.0, 'min_width': 4.0, 'min_height': 4.0, 'requires_ventilation': False, 'adjacent_to_road': True},
        {'name': 'Living Room', 'type': 'Living Room', 'min_area': 120.0, 'min_width': 10.0, 'min_height': 10.0, 'requires_ventilation': True, 'adjacent_to_road': True},
        {'name': 'Kitchen', 'type': 'Kitchen', 'min_area': 70.0, 'min_width': 8.0, 'min_height': 8.0, 'requires_ventilation': True, 'adjacent_to_road': False},
        {'name': 'Master Bedroom', 'type': 'Bedroom', 'min_area': 120.0, 'min_width': 10.0, 'min_height': 10.0, 'requires_ventilation': True, 'adjacent_to_road': False}
    ],
    'adjacencies': [
        ('Entrance Lobby', 'Living Room'),
        ('Living Room', 'Kitchen'),
        ('Living Room', 'Master Bedroom')
    ],
    'time_limit_sec': 30
}

# 2. Rowhouse Scenario (Closed boundaries on left/right sides, 0ft setbacks on sides)
scenario_rowhouse = {
    'plot': {'width': 35.0, 'depth': 50.0},
    'setbacks': {'left': 0.0, 'right': 0.0, 'bottom': 6.0, 'top': 5.0},  # Front setback = 6ft (for road/car parking)
    'stair_core': {'width': 8.0, 'height': 10.0, 'edge': 'bottom-right'},
    'road_edge': 'bottom',
    'rooms': [
        {'name': 'Entrance', 'type': 'Entrance', 'min_area': 12.0, 'min_width': 3.0, 'min_height': 4.0, 'requires_ventilation': False, 'adjacent_to_road': True},
        {'name': 'Living Area', 'type': 'Living Room', 'min_area': 150.0, 'min_width': 10.0, 'min_height': 12.0, 'requires_ventilation': True, 'adjacent_to_road': True},
        {'name': 'Pantry Kitchen', 'type': 'Kitchen', 'min_area': 80.0, 'min_width': 8.0, 'min_height': 8.0, 'requires_ventilation': True, 'adjacent_to_road': False},
        {'name': 'Kids Bedroom', 'type': 'Bedroom', 'min_area': 100.0, 'min_width': 10.0, 'min_height': 10.0, 'requires_ventilation': True, 'adjacent_to_road': False}
    ],
    'adjacencies': [
        ('Entrance', 'Living Area'),
        ('Living Area', 'Pantry Kitchen'),
        ('Living Area', 'Kids Bedroom')
    ],
    'time_limit_sec': 60
}

# 3. Impossible Scenario (Plot size too small to house required rooms and setbacks)
scenario_impossible = {
    'plot': {'width': 30.0, 'depth': 30.0},
    'setbacks': {'left': 5.0, 'right': 5.0, 'bottom': 5.0, 'top': 5.0},  # Buildable area is 20x20 = 400 sq ft
    'stair_core': {'width': 10.0, 'height': 12.0, 'edge': 'bottom-left'}, # Core is 120 sq ft. Remaining is 280 sq ft
    'road_edge': 'bottom',
    'rooms': [
        {'name': 'Main Door', 'type': 'Entrance', 'min_area': 16.0, 'min_width': 4.0, 'min_height': 4.0, 'requires_ventilation': False, 'adjacent_to_road': True},
        {'name': 'Living Room', 'type': 'Living Room', 'min_area': 200.0, 'min_width': 10.0, 'min_height': 10.0, 'requires_ventilation': True, 'adjacent_to_road': True},
        {'name': 'Bedroom 1', 'type': 'Bedroom', 'min_area': 150.0, 'min_width': 10.0, 'min_height': 10.0, 'requires_ventilation': True, 'adjacent_to_road': False},
        {'name': 'Bedroom 2', 'type': 'Bedroom', 'min_area': 150.0, 'min_width': 10.0, 'min_height': 10.0, 'requires_ventilation': True, 'adjacent_to_road': False}
    ],
    'adjacencies': [
        ('Main Door', 'Living Room'),
        ('Living Room', 'Bedroom 1'),
        ('Living Room', 'Bedroom 2')
    ]
}

if __name__ == '__main__':
    print("--- SCENARIO 1: Standard Compliant Plot ---")
    res1 = compile_blueprint(scenario_standard)
    if res1['success']:
        generate_svg(res1, 40.0, 40.0, "layout_standard.svg")
    else:
        print(f"[-] Failed: {res1.get('error')}")
        
    print("\n--- SCENARIO 2: Landlocked Rowhouse (Narrow Plot) ---")
    res2 = compile_blueprint(scenario_rowhouse)
    if res2['success']:
        generate_svg(res2, 35.0, 50.0, "layout_rowhouse.svg")
    else:
        print(f"[-] Failed: {res2.get('error')}")
        
    print("\n--- SCENARIO 3: Impossible Constraints (Small Plot / Huge Rooms) ---")
    res3 = compile_blueprint(scenario_impossible)
    if res3['success']:
        print("[+] Success? Unexpected behavior.")
    else:
        print(f"[EXPECTED FAILURE]: {res3.get('error')}")
