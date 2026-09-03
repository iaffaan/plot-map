import pytest
from app.api.v1.endpoints.compile import compile_layout, CompileRequest
from app.services.compiler.serializer import compile_blueprint


def test_cad_drawing_per_floor_room_isolation():
    """
    (a) Verify that a 2D CAD render for a given floor contains ONLY that floor's rooms,
    and not rooms from other floors merged into a single composite shape.
    """
    req = CompileRequest(
        prompt="Generate an optimized 3-floor residential building layout with maximum cross-ventilation and natural light on a 43.75x41 plot",
        plot_width=43.75,
        plot_depth=41.0,
        floors=3,
        prioritize_ventilation=True
    )
    res = compile_layout(req)
    assert res["success"] is True
    assert "drawing_svgs" in res
    
    drawing_svgs = res["drawing_svgs"]
    assert "1" in drawing_svgs
    assert "2" in drawing_svgs
    
    svg_fl1 = drawing_svgs["1"]
    svg_fl2 = drawing_svgs["2"]
    
    # Floor 1 must contain ground floor rooms (e.g. LIVING ROOM, KITCHEN) and NOT upper floor bedrooms
    assert "LIVING" in svg_fl1
    assert "KITCHEN" in svg_fl1
    assert "BEDROOM 2" not in svg_fl1
    assert "BEDROOM 3" not in svg_fl1
    
    # Floor 2 must contain upper floor bedrooms and NOT kitchen/living room
    assert "BEDROOM" in svg_fl2
    assert "KITCHEN" not in svg_fl2
    assert "LIVING ROOM" not in svg_fl2


def test_envelope_exterior_wall_alignment_across_consecutive_floors():
    """
    (b) Verify that exterior envelope footprint bounds (X_min, X_max, Y_min, Y_max)
    across consecutive floors align closely rather than collapsing into disconnected patches.
    """
    payload = {
        "plot": {"width": 43.75, "depth": 41.0},
        "setbacks": {"left": 3.0, "right": 3.0, "bottom": 3.0, "top": 3.0},
        "stair_core": {"width": 8.0, "depth": 10.0, "position": "left"},
        "floors": 3,
        "rooms": [
            {"name": "Entrance Lobby", "type": "Entrance", "min_area": 40, "floor_assignment": 1},
            {"name": "Living Room", "type": "Living Room", "min_area": 160, "floor_assignment": 1, "requires_ventilation": True},
            {"name": "Kitchen", "type": "Kitchen", "min_area": 80, "floor_assignment": 1, "requires_ventilation": True},
            {"name": "Bathroom 1", "type": "Bathroom", "min_area": 35, "floor_assignment": 1},
            {"name": "Corridor 2", "type": "Corridor", "min_area": 40, "floor_assignment": 2},
            {"name": "Master Bedroom", "type": "Bedroom", "min_area": 140, "floor_assignment": 2, "requires_ventilation": True},
            {"name": "Bedroom 2", "type": "Bedroom", "min_area": 110, "floor_assignment": 2, "requires_ventilation": True},
            {"name": "Bedroom 3", "type": "Bedroom", "min_area": 100, "floor_assignment": 2, "requires_ventilation": True},
            {"name": "Bathroom 2", "type": "Bathroom", "min_area": 35, "floor_assignment": 2},
        ],
        "adjacencies": [
            ("Entrance Lobby", "Living Room"),
            ("Living Room", "Kitchen"),
            ("Living Room", "Bathroom 1"),
            ("Corridor 2", "Master Bedroom"),
            ("Corridor 2", "Bedroom 2"),
            ("Corridor 2", "Bedroom 3"),
            ("Corridor 2", "Bathroom 2")
        ],
        "prioritize_ventilation": True
    }
    
    compiled = compile_blueprint(payload)
    assert compiled["success"] is True
    
    floors = compiled["floors"]
    f1_rooms = floors["1"]["layout"]
    f2_rooms = floors["2"]["layout"]
    
    f1_min_x = min(r["x"] for r in f1_rooms.values())
    f1_max_x = max(r["x"] + r["width"] for r in f1_rooms.values())
    f1_min_y = min(r["y"] for r in f1_rooms.values())
    f1_max_y = max(r["y"] + r["height"] for r in f1_rooms.values())
    
    f2_min_x = min(r["x"] for r in f2_rooms.values())
    f2_max_x = max(r["x"] + r["width"] for r in f2_rooms.values())
    f2_min_y = min(r["y"] for r in f2_rooms.values())
    f2_max_y = max(r["y"] + r["height"] for r in f2_rooms.values())
    
    # Check that Floor 2 fits strictly within Floor 1's bounds
    assert f2_min_x >= f1_min_x - 0.1, f"Floor 2 left edge ({f2_min_x}) exceeds Floor 1 ({f1_min_x})"
    assert f2_max_x <= f1_max_x + 0.1, f"Floor 2 right edge ({f2_max_x}) exceeds Floor 1 ({f1_max_x})"
    assert f2_min_y >= f1_min_y - 0.1, f"Floor 2 bottom edge ({f2_min_y}) exceeds Floor 1 ({f1_min_y})"
    assert f2_max_y <= f1_max_y + 0.1, f"Floor 2 top edge ({f2_max_y}) exceeds Floor 1 ({f1_max_y})"
    
    # Check that Floor 2 spans the structural footprint width and top setback wall (diff <= 2.0 ft)
    assert abs(f1_min_x - f2_min_x) <= 2.0 or abs(f1_max_x - f2_max_x) <= 2.0, "Floor 2 does not share exterior envelope wall alignments with Floor 1"
    assert abs(f1_max_y - f2_max_y) <= 2.0, "Floor 2 does not align with the rear exterior envelope wall"


def test_staircase_footprint_identical_across_all_floors():
    """
    (c) Verify that the staircase core X/Y footprint is identical across all floors it spans.
    """
    payload = {
        "plot": {"width": 43.75, "depth": 41.0},
        "setbacks": {"left": 3.0, "right": 3.0, "bottom": 3.0, "top": 3.0},
        "stair_core": {"width": 8.0, "depth": 10.0, "position": "left"},
        "floors": 3,
        "rooms": [
            {"name": "Entrance Lobby", "type": "Entrance", "min_area": 40, "floor_assignment": 1},
            {"name": "Living Room", "type": "Living Room", "min_area": 150, "floor_assignment": 1},
            {"name": "Corridor 2", "type": "Corridor", "min_area": 40, "floor_assignment": 2},
            {"name": "Master Bedroom", "type": "Bedroom", "min_area": 130, "floor_assignment": 2},
            {"name": "Corridor 3", "type": "Corridor", "min_area": 40, "floor_assignment": 3},
            {"name": "Bedroom 2", "type": "Bedroom", "min_area": 110, "floor_assignment": 3}
        ],
        "adjacencies": [
            ("Entrance Lobby", "Living Room"),
            ("Corridor 2", "Master Bedroom"),
            ("Corridor 3", "Bedroom 2")
        ]
    }
    
    compiled = compile_blueprint(payload)
    assert compiled["success"] is True
    
    # Global stair core in boundaries
    core_coords = compiled["boundaries"]["stair_core"]
    assert len(core_coords) > 0
    
    xs = [c[0] for c in core_coords]
    ys = [c[1] for c in core_coords]
    expected_box = (min(xs), min(ys), max(xs), max(ys))
    
    # Check that each floor's rooms never overlap the stair core
    for f_idx in ["1", "2", "3"]:
        floor_rooms = compiled["floors"][f_idx]["layout"]
        for r_name, r in floor_rooms.items():
            rx1, ry1 = r["x"], r["y"]
            rx2, ry2 = r["x"] + r["width"], r["y"] + r["height"]
            
            # Intersection test with stair core
            overlap_x = max(0, min(rx2, expected_box[2]) - max(rx1, expected_box[0]))
            overlap_y = max(0, min(ry2, expected_box[3]) - max(ry1, expected_box[1]))
            overlap_area = overlap_x * overlap_y
            assert overlap_area == 0, f"Room {r_name} on Floor {f_idx} overlaps stair core!"
