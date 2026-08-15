import pytest
from app.services.relationship_builder import build_tbm_from_layout
from app.services.graph_builder import (
    build_graph_from_tbm,
    get_isolated_rooms,
    check_all_accessible_from
)
from app.core.tbm import Building
from app.services.geometry_resolver import resolve_geometry
from app.drawing import Drawing, Dimension, Text, Polyline, export_drawing_to_svg
from app.services.dimension_engine import generate_dimensions
from app.services.annotation_engine import generate_annotations

@pytest.fixture
def sample_building():
    payload = {
        "project_name": "Test Duplex",
        "plot": {"width": 30.0, "depth": 40.0},
        "setbacks": {"left": 2.0, "right": 2.0, "bottom": 3.0, "top": 3.0},
        "road_edge": "bottom"
    }
    
    compiled_result = {
        "floors": {
            "1": {
                "layout": {
                    "Living Room": {"x": 2.0, "y": 3.0, "width": 10.0, "height": 10.0, "type": "Living Room"},
                    "Kitchen": {"x": 12.0, "y": 3.0, "width": 8.0, "height": 10.0, "type": "Kitchen"}
                }
            }
        }
    }
    return build_tbm_from_layout(payload, compiled_result)

def test_tbm_relationship_builder(sample_building):
    assert isinstance(sample_building, Building)
    assert len(sample_building.rooms) == 2

def test_geometry_resolver(sample_building):
    geom = resolve_geometry(sample_building)
    assert len(geom.wall_panels) > 0

def test_dimension_engine(sample_building):
    geom = resolve_geometry(sample_building)
    drawing = Drawing()
    
    generate_dimensions(sample_building, geom, drawing)
    
    dims = [d for d in drawing.elements if isinstance(d, Dimension)]
    assert len(dims) >= 3
    assert all(d.layer == "Dimensions" for d in dims)

def test_annotation_engine(sample_building):
    geom = resolve_geometry(sample_building)
    drawing = Drawing()
    
    generate_annotations(sample_building, geom, drawing)
    
    texts = [t for t in drawing.elements if isinstance(t, Text)]
    assert len(texts) >= 4
    assert any("LIVING ROOM" in t.content for t in texts)
    assert any("KITCHEN" in t.content for t in texts)

def test_svg_exporter(sample_building):
    geom = resolve_geometry(sample_building)
    drawing = Drawing()
    
    # Add resolved wall panels to drawing
    for w_id, panels in geom.wall_panels.items():
        for p in panels:
            drawing.add(Polyline(
                layer="Walls",
                color="#000000",
                stroke_width=2.0,
                points=p.vertices,
                is_closed=True
            ))
            
    # Add dimensions
    generate_dimensions(sample_building, geom, drawing)
    # Add annotations
    generate_annotations(sample_building, geom, drawing)
    
    # Export
    svg_str = export_drawing_to_svg(drawing)
    
    # Assertions on SVG structure
    assert svg_str.startswith('<svg')
    assert svg_str.endswith('</svg>')
    assert 'viewBox="' in svg_str
    assert 'Outfit' in svg_str
    assert 'id="layer_walls"' in svg_str
    assert 'id="layer_dimensions"' in svg_str
    assert 'id="layer_annotations"' in svg_str
    assert 'LIVING ROOM' in svg_str
    assert 'SCALE: 1/4"' in svg_str
