import pytest
from shapely.geometry import Polygon
from engine.geometry import create_plot, calculate_buildable_area
from engine.topology import build_room_graph, validate_privacy, calculate_ventilation_and_ots
from engine.orchestrator import compile_blueprint

def test_phase_1_geometry_validation():
    """
    Validation Check from roadmap:
    Feed the engine a 40x40 ft plot with a 5 ft setback on all sides and a 10x10 ft core.
    The resulting Buildable_Area must be exactly 800 sq ft.
    """
    plot = create_plot(40.0, 40.0)
    setbacks = {'left': 5.0, 'right': 5.0, 'bottom': 5.0, 'top': 5.0}
    stair_core_cfg = {'width': 10.0, 'height': 10.0, 'edge': 'bottom-left'}
    
    envelope, core, buildable_area = calculate_buildable_area(plot, setbacks, stair_core_cfg)
    
    assert envelope.area == 900.0, f"Envelope area should be 900.0, got {envelope.area}"
    assert core.area == 100.0, f"Stair core area should be 100.0, got {core.area}"
    assert buildable_area.area == 800.0, f"Buildable area should be exactly 800.0, got {buildable_area.area}"

def test_phase_2_privacy_failure():
    """Verify that routing flows that force users to walk through private areas (Bedroom) fail."""
    rooms = [
        {'name': 'Main Door', 'type': 'Entrance', 'requires_ventilation': False, 'adjacent_to_road': True},
        {'name': 'Bedroom', 'type': 'Bedroom', 'requires_ventilation': True, 'adjacent_to_road': False},
        {'name': 'Kitchen', 'type': 'Kitchen', 'requires_ventilation': True, 'adjacent_to_road': False}
    ]
    # Path: Main Door -> Bedroom -> Kitchen (violates privacy)
    adjacencies = [('Main Door', 'Bedroom'), ('Bedroom', 'Kitchen')]
    
    G = build_room_graph(rooms, adjacencies)
    passed, msg = validate_privacy(G, main_door='Main Door')
    assert not passed
    assert "privacy violation" in msg.lower()

def test_phase_2_ventilation_and_ots():
    """Verify that landlocked rooms trigger procedural Open-To-Sky (OTS) shaft generation."""
    rooms = [
        {'name': 'Main Door', 'type': 'Entrance', 'requires_ventilation': False, 'adjacent_to_road': True},
        {'name': 'Living Room', 'type': 'Living Room', 'requires_ventilation': True, 'adjacent_to_road': True},
        {'name': 'Bedroom 1', 'type': 'Bedroom', 'requires_ventilation': True, 'adjacent_to_road': False}
    ]
    adjacencies = [('Main Door', 'Living Room'), ('Living Room', 'Bedroom 1')]
    
    G = build_room_graph(rooms, adjacencies)
    new_G, ots_shafts = calculate_ventilation_and_ots(G)
    
    # Bedroom 1 requires ventilation but is not adjacent to road, so OTS is generated.
    assert len(ots_shafts) == 1
    assert ots_shafts[0]['name'] == 'OTS_Bedroom 1'
    assert 'OTS_Bedroom 1' in new_G

def test_complete_compiler_pipeline():
    """Verify the entire pipeline end-to-end with the solver."""
    payload = {
        'plot': {'width': 40.0, 'depth': 40.0},
        'setbacks': {'left': 5.0, 'right': 5.0, 'bottom': 5.0, 'top': 5.0},
        'stair_core': {'width': 10.0, 'height': 10.0, 'edge': 'bottom-left'},
        'road_edge': 'bottom',
        'rooms': [
            {'name': 'Main Door', 'type': 'Entrance', 'min_width': 3.0, 'min_height': 3.0, 'min_area': 9.0, 'requires_ventilation': False, 'adjacent_to_road': True},
            {'name': 'Living Room', 'type': 'Living Room', 'min_width': 10.0, 'min_height': 10.0, 'min_area': 100.0, 'requires_ventilation': True, 'adjacent_to_road': True},
            {'name': 'Kitchen', 'type': 'Kitchen', 'min_width': 8.0, 'min_height': 8.0, 'min_area': 64.0, 'requires_ventilation': True, 'adjacent_to_road': False},
            {'name': 'Bedroom', 'type': 'Bedroom', 'min_width': 10.0, 'min_height': 10.0, 'min_area': 100.0, 'requires_ventilation': True, 'adjacent_to_road': False}
        ],
        'adjacencies': [
            ('Main Door', 'Living Room'),
            ('Living Room', 'Kitchen'),
            ('Living Room', 'Bedroom')
        ]
    }
    
    res = compile_blueprint(payload)
    assert res['success'], f"Compilation failed: {res.get('error')}"
    
    layout = res['layout']
    assert 'Living Room' in layout
    assert 'Kitchen' in layout
    assert 'Bedroom' in layout
    
    # Verify that OTS shafts were created for the landlocked Kitchen and Bedroom
    assert 'OTS_Kitchen' in layout
    assert 'OTS_Bedroom' in layout
    
    # Assert coordinates bounds are valid
    for room_name, room in layout.items():
        assert room['x'] >= 5.0
        assert room['x'] + room['width'] <= 35.0
        assert room['y'] >= 5.0
        assert room['y'] + room['height'] <= 35.0

def test_api_endpoint():
    """Verify that the FastAPI endpoint compiles successfully with Pydantic request object."""
    from main import compile_layout_endpoint, CompileRequest, PlotConfig, Setbacks, StairCoreConfig, RoomConfig
    
    req = CompileRequest(
        plot=PlotConfig(width=40.0, depth=40.0),
        setbacks=Setbacks(left=5.0, right=5.0, bottom=5.0, top=5.0),
        stair_core=StairCoreConfig(width=10.0, height=10.0, edge='bottom-left'),
        rooms=[
            RoomConfig(name='Main Door', type='Entrance', min_area=9.0, min_width=3.0, min_height=3.0, requires_ventilation=False, adjacent_to_road=True),
            RoomConfig(name='Living Room', type='Living Room', min_area=100.0, min_width=10.0, min_height=10.0, requires_ventilation=True, adjacent_to_road=True),
            RoomConfig(name='Kitchen', type='Kitchen', min_area=64.0, min_width=8.0, min_height=8.0, requires_ventilation=True, adjacent_to_road=False),
            RoomConfig(name='Bedroom', type='Bedroom', min_area=100.0, min_width=10.0, min_height=10.0, requires_ventilation=True, adjacent_to_road=False)
        ],
        adjacencies=[
            ('Main Door', 'Living Room'),
            ('Living Room', 'Kitchen'),
            ('Living Room', 'Bedroom')
        ]
    )
    res = compile_layout_endpoint(req)
    assert res['success']
    assert len(res['layout']) == 6  # Main Door, Living Room, Kitchen, Bedroom, OTS_Kitchen, OTS_Bedroom

