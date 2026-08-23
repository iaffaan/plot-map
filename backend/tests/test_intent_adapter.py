from app.schemas.intent import CompilerIntent, RoomCategory, RoomIntent
from app.services.compiler.intent_adapter import to_design_problem


def test_compiler_intent_adapts_to_design_problem_without_inventing_requirements():
    intent = CompilerIntent(
        plot_width=44,
        plot_depth=42,
        floors=3,
        front_road_setback=5,
        confidence_score=0.75,
        rooms=[
            RoomIntent(room_type=RoomCategory.BEDROOM, min_area_sqft=100),
            RoomIntent(room_type=RoomCategory.LIVING, min_area_sqft=150),
            RoomIntent(room_type=RoomCategory.BATHROOM, min_area_sqft=30),
        ],
    )

    problem = to_design_problem(intent, problem_id="problem-from-intent")

    assert problem.id == "problem-from-intent"
    assert problem.site.plot_width == intent.plot_width
    assert problem.site.plot_depth == intent.plot_depth
    assert problem.site.floors == intent.floors
    assert problem.site.setbacks == {"bottom": intent.front_road_setback}
    assert [space.room for space in problem.spaces] == intent.rooms
    assert [space.room.room_type for space in problem.spaces] == [
        RoomCategory.BEDROOM,
        RoomCategory.LIVING,
        RoomCategory.BATHROOM,
    ]
    assert problem.requirements == []
    assert problem.constraints == []
    assert problem.preferences == []
    assert problem.objectives == []
    assert problem.provenance["confidence_score"] == intent.confidence_score
    assert "relationships" in problem.provenance["unmapped_fields"]


def test_adapter_does_not_change_existing_compile_path():
    from app.services.compiler.serializer import compile_blueprint

    payload = {
        "plot": {"width": 40.0, "depth": 40.0},
        "setbacks": {"left": 3.0, "right": 3.0, "bottom": 5.0, "top": 3.0},
        "stair_core": {"width": 10.0, "height": 10.0, "edge": "bottom-left"},
        "floors": 1,
        "rooms": [
            {
                "name": "Entrance Lobby",
                "type": "Entrance",
                "min_area": 9.0,
                "min_width": 3.0,
                "min_height": 3.0,
                "floor_assignment": 1,
                "requires_ventilation": False,
                "adjacent_to_road": True,
            },
            {
                "name": "Living Room",
                "type": "Living Room",
                "min_area": 80.0,
                "min_width": 8.0,
                "min_height": 8.0,
                "floor_assignment": 1,
                "requires_ventilation": True,
                "adjacent_to_road": True,
            }
        ],
        "adjacencies": [("Entrance Lobby", "Living Room")],
        "road_edge": "bottom",
        "grid_snap": 0.5,
        "time_limit_sec": 5,
    }

    result = compile_blueprint(payload)

    assert result["success"] is True
    assert "Living Room" in result["layout"]
    assert "floors" in result