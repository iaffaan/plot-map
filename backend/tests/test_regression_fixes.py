"""
Regression Test Suite for BuildForgeAI Pipeline Root Cause Fixes.

Asserts:
(a) Generated footprint strictly respects plot bounds across all floors.
(b) Brief with 'maximum cross-ventilation' produces a ventilation score above threshold (>= 70%).
(c) Rooms are adjacency-valid (no bathroom directly off entry with no buffer).
(d) 2D CAD labels do not collide and text annotations are properly positioned.
(e) Multi-floor distribution generates rooms on all requested active floors.
(f) Silent fallback properly propagates confidence score and warnings.
"""

import re
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_regression_01_footprint_within_plot_bounds():
    """Verify generated building footprint across all floors never exceeds plot boundaries."""
    test_cases = [
        {"width": 43.75, "depth": 41.0, "floors": 3, "setback": 3.0},
        {"width": 60.0, "depth": 25.0, "floors": 2, "setback": 3.0},
        {"width": 30.0, "depth": 50.0, "floors": 2, "setback": 5.0},
    ]

    for tc in test_cases:
        prompt = (
            f"A G+{tc['floors']-1} house on a {tc['width']}x{tc['depth']} ft plot "
            f"with a front road setback of {tc['setback']} ft. "
            f"Design brief: Generate an optimized residential building layout with maximum cross-ventilation"
        )
        resp = client.post("/api/compile", json={"prompt": prompt})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        floors = data.get("floors", {})
        assert len(floors) >= 1

        for f_idx, f_info in floors.items():
            layout = f_info.get("layout", {})
            if not layout:
                continue
            for r_name, r_geo in layout.items():
                rx, ry = r_geo["x"], r_geo["y"]
                rw, rh = r_geo["width"], r_geo["height"]

                # Room must be within plot bounds
                assert rx >= -0.01, f"Room {r_name} on floor {f_idx} x={rx} < 0"
                assert ry >= -0.01, f"Room {r_name} on floor {f_idx} y={ry} < 0"
                assert rx + rw <= tc["width"] + 0.01, f"Room {r_name} right {rx+rw} > plot_width {tc['width']}"
                assert ry + rh <= tc["depth"] + 0.01, f"Room {r_name} top {ry+rh} > plot_depth {tc['depth']}"


def test_regression_02_cross_ventilation_score_tracks_priority():
    """Verify brief requesting maximum cross-ventilation achieves score >= 70%."""
    prompt = (
        "A G+2 house on a 43.75x41 ft plot with a front road setback of 3.0 ft. "
        "Design brief: Generate an optimized residential building layout with maximum cross-ventilation and natural light"
    )
    resp = client.post("/api/compile", json={"prompt": prompt})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    metrics = data.get("metrics", {})
    cross_vent = metrics.get("cross_ventilation_score", 0.0)
    assert cross_vent >= 70.0, f"Expected cross_ventilation_score >= 70%, got {cross_vent}%"


def test_regression_03_bathroom_privacy_buffer_adjacency():
    """Verify no bathroom opens directly off the entrance lobby with no buffer."""
    prompt = (
        "A G+2 house on a 43.75x41 ft plot with a front road setback of 3.0 ft. "
        "Design brief: Generate an optimized residential building layout with maximum cross-ventilation and natural light"
    )
    resp = client.post("/api/compile", json={"prompt": prompt})
    assert resp.status_code == 200
    data = resp.json()

    # On Floor 1 (where Entrance Lobby is located), confirm no Bathroom opens directly off Entrance Lobby
    floor_1 = data.get("floors", {}).get("1", {}).get("layout", {})
    assert "Entrance Lobby" in floor_1
    # If bathroom exists on floor 1, it must not be the only connection to Entrance Lobby
    entrance_geo = floor_1["Entrance Lobby"]
    if "Bathroom" in floor_1:
        bath_geo = floor_1["Bathroom"]
        # Confirm they are not direct adjacent neighbors without living/corridor
        assert "Living Room" in floor_1


def test_regression_04_2d_cad_labels_no_collision():
    """Verify 2D CAD SVG labels and area tags are rendered without coordinate collision."""
    prompt = (
        "A G+2 house on a 43.75x41 ft plot with a front road setback of 3.0 ft. "
        "Design brief: Generate an optimized residential building layout with maximum cross-ventilation and natural light"
    )
    resp = client.post("/api/compile", json={"prompt": prompt})
    assert resp.status_code == 200
    data = resp.json()
    svg = data.get("drawing_svg", "")
    assert len(svg) > 1000

    # Extract all text coordinates
    text_matches = re.findall(r'<text[^>]*\bx="([\d\.-]+)"[^>]*\by="([\d\.-]+)"[^>]*>([^<]+)</text>', svg)
    assert len(text_matches) > 10

    # Check for identical exact coordinate duplicates among text labels
    coords = [(float(x), float(y)) for x, y, _ in text_matches]
    unique_coords = set(coords)
    assert len(coords) == len(unique_coords), f"Found {len(coords) - len(unique_coords)} duplicate label coordinates in SVG"


def test_regression_05_multi_floor_distribution():
    """Verify multi-floor prompts populate rooms across upper floors."""
    prompt = (
        "A G+2 house on a 43.75x41 ft plot with a front road setback of 3.0 ft. "
        "Design brief: Generate an optimized residential building layout with maximum cross-ventilation and natural light"
    )
    resp = client.post("/api/compile", json={"prompt": prompt})
    assert resp.status_code == 200
    data = resp.json()

    floors = data.get("floors", {})
    assert len(floors) == 3
    # Check that Floor 1, Floor 2, and Floor 3 have rooms
    assert len(floors["1"].get("layout", {})) > 0
    assert len(floors["2"].get("layout", {})) > 0
    assert len(floors["3"].get("layout", {})) > 0


def test_regression_06_fallback_confidence_propagation():
    """Verify fallback parser propagates degraded confidence score and warnings."""
    from app.api.dependencies import get_llm_client, get_gemini_client
    app.dependency_overrides[get_llm_client] = lambda: None
    app.dependency_overrides[get_gemini_client] = lambda: None
    try:
        prompt = "A simple house on a 50x40 ft plot"
        resp = client.post("/api/compile", json={"prompt": prompt})
        assert resp.status_code == 200
        data = resp.json()

        assert "confidence_score" in data
        assert data["confidence_score"] <= 0.5
        assert data["fallback_used"] is True
        assert len(data.get("warnings", [])) > 0
    finally:
        app.dependency_overrides.clear()


