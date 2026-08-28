from app.schemas.architectural_analysis import (
    AnalysisSeverity,
    ConflictStatus,
    DecisionDimension,
    DecisionStatus,
    UncertaintyMateriality,
)
from app.schemas.design_problem import (
    Constraint,
    DesignProblem,
    Objective,
    Preference,
    Requirement,
    RequirementKind,
    RequirementRelation,
    RequirementStrength,
    RelationshipType,
    SiteDefinition,
    SpaceRequirement,
    UserGroup,
)
from app.schemas.intent import RoomCategory, RoomIntent
from app.services.analysis.architectural_analyzer import analyze_design_problem


def _problem(**kwargs) -> DesignProblem:
    return DesignProblem(
        id=kwargs.pop("id", "problem-test"),
        version=kwargs.pop("version", 1),
        site=kwargs.pop("site", SiteDefinition(plot_width=30, plot_depth=40, floors=2)),
        **kwargs,
    )


def test_simple_house_identifies_fixed_program_and_flexible_strategy():
    problem = _problem(
        spaces=[
            SpaceRequirement(
                id="bedrooms",
                room=RoomIntent(room_type=RoomCategory.BEDROOM, min_area_sqft=100),
                quantity=2,
            )
        ]
    )

    analysis = analyze_design_problem(problem)

    assert analysis.fixed_decisions[0].dimension is DecisionDimension.SITE_RESPONSE
    room_decision = next(item for item in analysis.fixed_decisions if item.id == "space-bedrooms")
    assert room_decision.value["quantity"] == 2
    assert any(item.dimension is DecisionDimension.FLOOR_ALLOCATION for item in analysis.flexible_decisions)
    assert DecisionDimension.ORIENTATION in analysis.decision_dimensions


def test_explicit_hard_requirements_remain_hard_and_preserve_source_ids():
    requirement = Requirement(
        id="independent-access",
        kind=RequirementKind.CIRCULATION,
        subject="user-groups",
        value={"independent": True},
        strength=RequirementStrength.HARD,
    )

    analysis = analyze_design_problem(_problem(requirements=[requirement]))

    assert analysis.hard_constraints == [requirement]
    decision = next(item for item in analysis.fixed_decisions if item.source_ids == ["independent-access"])
    assert decision.status is DecisionStatus.FIXED
    assert decision.dimension is DecisionDimension.CIRCULATION


def test_multiple_user_groups_without_relationship_report_uncertainty():
    problem = _problem(
        user_groups=[UserGroup(id="group-a"), UserGroup(id="group-b")],
    )

    analysis = analyze_design_problem(problem)

    uncertainty = next(item for item in analysis.uncertainties if item.id == "uncertainty-group-circulation")
    assert uncertainty.materiality is UncertaintyMateriality.MATERIAL
    assert DecisionDimension.ENTRANCE_STRATEGY in uncertainty.affected_dimensions


def test_declared_conflict_is_represented_without_inventing_other_conflicts():
    first = Requirement(
        id="shared-entry",
        kind=RequirementKind.CIRCULATION,
        subject="entrance",
        value="shared",
        conflicts_with=["independent-entry"],
    )
    second = Requirement(
        id="independent-entry",
        kind=RequirementKind.CIRCULATION,
        subject="entrance",
        value="independent",
    )

    analysis = analyze_design_problem(_problem(requirements=[first, second]))

    assert len(analysis.conflicts) == 1
    assert analysis.conflicts[0].status is ConflictStatus.REQUIRES_CLARIFICATION
    assert analysis.conflicts[0].severity is AnalysisSeverity.BLOCKING


def test_soft_preference_and_objective_are_not_collapsed_into_constraints():
    preference = Preference(
        id="prefer-one-core",
        description="Prefer fewer circulation cores",
        target={"core_count": 1},
        priority=60,
        weight=2,
    )
    objective = Objective(
        id="maximize-area",
        metric="usable_area",
        direction="maximize",
    )

    analysis = analyze_design_problem(_problem(preferences=[preference], objectives=[objective]))

    assert analysis.soft_preferences == [preference]
    assert analysis.objectives == [objective]
    assert analysis.hard_constraints == []


def test_dependencies_and_area_feasibility_concern_are_deterministic():
    problem = _problem(
        site=SiteDefinition(
            plot_width=10,
            plot_depth=10,
            floors=1,
            setbacks={"left": 2, "right": 2, "bottom": 2, "top": 2},
        ),
        user_groups=[UserGroup(id="group-a"), UserGroup(id="group-b")],
        spaces=[
            SpaceRequirement(
                id="large-space",
                room=RoomIntent(room_type=RoomCategory.LIVING, min_area_sqft=100),
            )
        ],
    )

    first = analyze_design_problem(problem)
    second = analyze_design_problem(problem)

    assert first.model_dump() == second.model_dump()
    assert first.feasibility_concerns[0].severity is AnalysisSeverity.BLOCKING
    assert any(
        dependency.source_dimension is DecisionDimension.VERTICAL_CIRCULATION
        for dependency in first.dependencies
    )


def test_existing_relationships_are_only_used_as_declared_input():
    space = SpaceRequirement(
        id="group-a-space",
        owner_id="group-a",
        room=RoomIntent(room_type=RoomCategory.LIVING),
        relationships=[
            RequirementRelation(
                relation=RelationshipType.SHARED,
                target_id="group-b",
            )
        ],
    )
    problem = _problem(
        user_groups=[UserGroup(id="group-a"), UserGroup(id="group-b")],
        spaces=[space],
    )

    analysis = analyze_design_problem(problem)

    assert not any(item.id == "uncertainty-group-circulation" for item in analysis.uncertainties)