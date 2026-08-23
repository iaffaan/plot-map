from app.schemas.design_problem import DesignProblem, SiteDefinition, SpaceRequirement
from app.schemas.intent import CompilerIntent


def to_design_problem(
    intent: CompilerIntent,
    problem_id: str = "compiler-intent-adapter",
) -> DesignProblem:
    """Convert the legacy CompilerIntent into the general Stage 1 model.

    This adapter is intentionally loss-aware. It maps only data represented by
    CompilerIntent and records fields that require future requirement semantics
    in provenance instead of inventing architectural meaning.
    """
    spaces = [
        SpaceRequirement(
            id=f"room-{index}",
            room=room,
        )
        for index, room in enumerate(intent.rooms, start=1)
    ]

    return DesignProblem(
        id=problem_id,
        site=SiteDefinition(
            plot_width=intent.plot_width,
            plot_depth=intent.plot_depth,
            floors=intent.floors,
            setbacks={"bottom": intent.front_road_setback},
        ),
        spaces=spaces,
        provenance={
            "source_type": "CompilerIntent",
            "confidence_score": intent.confidence_score,
            "mapped_fields": [
                "plot_width",
                "plot_depth",
                "floors",
                "front_road_setback",
                "rooms",
            ],
            "unmapped_fields": [
                "relationships",
                "constraints",
                "preferences",
                "objectives",
                "user_groups",
                "room_floor_assignments",
            ],
        },
    )