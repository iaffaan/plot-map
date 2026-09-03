from app.schemas.design_problem import (
    DesignProblem,
    Objective,
    Preference,
    SiteDefinition,
    SpaceRequirement,
)
from app.schemas.intent import CompilerIntent


def to_design_problem(
    intent: CompilerIntent,
    problem_id: str = "compiler-intent-adapter",
) -> DesignProblem:
    """Convert CompilerIntent into the general Stage 1 DesignProblem model.

    Maps structural parameters, spaces, and qualitative objectives/preferences.
    """
    spaces = [
        SpaceRequirement(
            id=f"room-{index}",
            room=room,
        )
        for index, room in enumerate(intent.rooms, start=1)
    ]

    objectives = []
    preferences = []
    mapped_fields = [
        "plot_width",
        "plot_depth",
        "floors",
        "front_road_setback",
        "rooms",
    ]

    if getattr(intent, "prioritize_ventilation", False):
        objectives.append(
            Objective(
                id="obj-cross-ventilation",
                metric="cross_ventilation",
                direction="maximize",
                priority=90,
                weight=2.0,
            )
        )
        preferences.append(
            Preference(
                id="pref-cross-ventilation",
                description="Maximize natural cross-ventilation across habitable rooms",
                target="cross_ventilation",
                priority=90,
                weight=2.0,
            )
        )
        mapped_fields.append("prioritize_ventilation")

    if getattr(intent, "prioritize_daylight", False):
        objectives.append(
            Objective(
                id="obj-daylighting",
                metric="daylighting",
                direction="maximize",
                priority=85,
                weight=1.5,
            )
        )
        preferences.append(
            Preference(
                id="pref-daylighting",
                description="Maximize natural daylight and external window exposure",
                target="daylighting",
                priority=85,
                weight=1.5,
            )
        )
        mapped_fields.append("prioritize_daylight")

    return DesignProblem(
        id=problem_id,
        site=SiteDefinition(
            plot_width=intent.plot_width,
            plot_depth=intent.plot_depth,
            floors=intent.floors,
            setbacks={"bottom": intent.front_road_setback},
        ),
        spaces=spaces,
        objectives=objectives,
        preferences=preferences,
        provenance={
            "source_type": "CompilerIntent",
            "confidence_score": intent.confidence_score,
            "mapped_fields": mapped_fields,
            "unmapped_fields": [
                "relationships",
                "constraints",
                "user_groups",
                "room_floor_assignments",
            ],
        },
    )