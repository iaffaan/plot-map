import pytest
from pydantic import ValidationError

from app.schemas.design_problem import (
    Constraint,
    DesignProblem,
    Objective,
    Preference,
    Requirement,
    RequirementDelta,
    RequirementKind,
    RequirementRelation,
    RequirementStrength,
    RelationshipType,
    SiteDefinition,
    SpaceRequirement,
    UserGroup,
    ValidationResult,
)
from app.schemas.intent import RoomCategory, RoomIntent


def test_design_problem_models_general_circulation_requirements():
    problem = DesignProblem(
        id="problem-1",
        site=SiteDefinition(plot_width=44, plot_depth=42, floors=2),
        user_groups=[UserGroup(id="households")],
        requirements=[
            Requirement(
                id="shared-circulation",
                kind=RequirementKind.CIRCULATION,
                subject="building",
                value={"system": "staircase", "count": 1},
                strength=RequirementStrength.HARD,
                relationships=[
                    RequirementRelation(
                        relation=RelationshipType.SHARED,
                        target_id="all-user-groups",
                    )
                ],
            ),
            Requirement(
                id="private-entry-preference",
                kind=RequirementKind.PRIVACY,
                subject="user-group:household-a",
                value={"independent_entrance": True},
                strength=RequirementStrength.SOFT,
                priority=80,
                optional=True,
            ),
        ],
        constraints=[
            Constraint(
                id="no-overlap",
                expression="room footprints do not overlap",
            )
        ],
        preferences=[
            Preference(
                id="maximize-area",
                description="Prefer more usable area",
                target="usable_area",
                priority=70,
            )
        ],
        objectives=[
            Objective(
                id="area-objective",
                metric="usable_area",
                direction="maximize",
            )
        ],
    )

    assert problem.requirements[0].strength is RequirementStrength.HARD
    assert problem.requirements[1].optional is True
    assert problem.requirements[0].relationships[0].relation is RelationshipType.SHARED
    assert problem.model_dump()["site"]["plot_width"] == 44.0


def test_design_problem_reuses_room_intent_for_general_spaces():
    space = SpaceRequirement(
        id="kitchen-1",
        room=RoomIntent(room_type=RoomCategory.KITCHEN),
        owner_id="family-a",
    )
    problem = DesignProblem(
        id="problem-2",
        site=SiteDefinition(plot_width=30, plot_depth=40),
        spaces=[space],
    )

    assert problem.spaces[0].room.room_type is RoomCategory.KITCHEN
    assert problem.spaces[0].room.min_area_sqft == 60


def test_design_problem_supports_versioned_requirement_deltas():
    delta = RequirementDelta(
        id="delta-1",
        base_problem_id="problem-1",
        parent_version=1,
        operation="replace",
        target_id="shared-circulation",
        value={"system": "staircase", "count": "per-user-group"},
        source_text="Give every household its own staircase",
    )

    assert delta.operation == "replace"
    assert delta.parent_version == 1


def test_design_problem_rejects_duplicate_ids_within_collection():
    with pytest.raises(ValidationError, match="IDs must be unique"):
        DesignProblem(
            id="problem-3",
            site=SiteDefinition(plot_width=30, plot_depth=30),
            requirements=[
                Requirement(
                    id="same-id",
                    kind=RequirementKind.SITE,
                    subject="plot",
                    value="a",
                ),
                Requirement(
                    id="same-id",
                    kind=RequirementKind.SITE,
                    subject="plot",
                    value="b",
                ),
            ],
        )


def test_supporting_schemas_validate_ranges_and_results():
    with pytest.raises(ValidationError):
        Objective(
            id="invalid-objective",
            metric="area",
            direction="maximize",
            weight=-1,
        )

    result = ValidationResult(
        success=True,
        hard_constraints={"no-overlap": True},
        soft_constraints={"daylight": False},
        metrics={"usable_area": 900.0},
    )

    assert result.success is True
    assert result.metrics["usable_area"] == 900.0