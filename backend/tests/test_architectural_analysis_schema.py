import pytest
from pydantic import ValidationError

from app.schemas.architectural_analysis import (
    AnalysisSeverity,
    ArchitecturalAnalysis,
    ConflictRecord,
    ConflictStatus,
    DecisionDimension,
    DecisionRecord,
    DecisionStatus,
    DependencyRecord,
    FeasibilityConcern,
    UncertaintyMateriality,
    UncertaintyRecord,
)
from app.schemas.design_problem import Constraint, Objective, Preference, Requirement, RequirementKind


def test_minimal_architectural_analysis_construction():
    analysis = ArchitecturalAnalysis(
        problem_id="problem-1",
        problem_version=1,
        summary="Architectural decisions identified.",
    )

    assert analysis.fixed_decisions == []
    assert analysis.decision_dimensions == []


def test_analysis_represents_fixed_flexible_and_partially_fixed_decisions():
    analysis = ArchitecturalAnalysis(
        problem_id="problem-2",
        problem_version=3,
        summary="Site is known; allocation remains open.",
        fixed_decisions=[
            DecisionRecord(
                id="site-size",
                dimension=DecisionDimension.SITE_RESPONSE,
                subject="plot",
                value={"width": 30, "depth": 40},
                status=DecisionStatus.FIXED,
                source_ids=["site-requirement"],
            )
        ],
        flexible_decisions=[
            DecisionRecord(
                id="floor-plan",
                dimension=DecisionDimension.FLOOR_ALLOCATION,
                subject="spaces",
                status=DecisionStatus.FLEXIBLE,
            ),
            DecisionRecord(
                id="known-floor-count",
                dimension=DecisionDimension.FLOOR_ALLOCATION,
                subject="floor-count",
                value=2,
                status=DecisionStatus.PARTIALLY_FIXED,
            ),
        ],
    )

    assert analysis.fixed_decisions[0].status is DecisionStatus.FIXED
    assert analysis.flexible_decisions[0].status is DecisionStatus.FLEXIBLE
    assert analysis.flexible_decisions[1].status is DecisionStatus.PARTIALLY_FIXED


def test_analysis_represents_conflict_uncertainty_dependency_and_feasibility():
    analysis = ArchitecturalAnalysis(
        problem_id="problem-3",
        problem_version=1,
        summary="Conflicting entrance requirements require clarification.",
        conflicts=[
            ConflictRecord(
                id="entrance-conflict",
                source_ids=["shared-entry", "private-entry"],
                type="direct_contradiction",
                severity=AnalysisSeverity.BLOCKING,
                status=ConflictStatus.REQUIRES_CLARIFICATION,
                explanation="The two entrance requirements cannot both be mandatory.",
                affected_dimensions=[DecisionDimension.ENTRANCE_STRATEGY],
                clarification_question="Should entrances be shared or independent?",
            )
        ],
        uncertainties=[
            UncertaintyRecord(
                id="orientation-unknown",
                topic="site orientation",
                description="The site orientation was not provided.",
                materiality=UncertaintyMateriality.MATERIAL,
                affected_dimensions=[DecisionDimension.ORIENTATION],
                required_for_strategy=True,
            )
        ],
        dependencies=[
            DependencyRecord(
                id="stair-impact",
                source_dimension=DecisionDimension.VERTICAL_CIRCULATION,
                affected_dimensions=[
                    DecisionDimension.CIRCULATION,
                    DecisionDimension.FLOOR_ALLOCATION,
                ],
                relationship="affects",
                explanation="Vertical circulation changes access and floor organization.",
            )
        ],
        feasibility_concerns=[
            FeasibilityConcern(
                id="core-capacity",
                dimension=DecisionDimension.SERVICE_CORE_STRATEGY,
                description="The requested core strategy may exceed the available site area.",
                severity=AnalysisSeverity.WARNING,
                source_ids=["site-size"],
            )
        ],
    )

    assert analysis.conflicts[0].status is ConflictStatus.REQUIRES_CLARIFICATION
    assert analysis.uncertainties[0].materiality is UncertaintyMateriality.MATERIAL
    assert analysis.dependencies[0].source_dimension is DecisionDimension.VERTICAL_CIRCULATION
    assert analysis.feasibility_concerns[0].severity is AnalysisSeverity.WARNING


def test_analysis_reuses_existing_design_problem_types():
    hard_requirement = Requirement(
        id="required-bedroom",
        kind=RequirementKind.SPACE,
        subject="bedroom",
        value={"quantity": 2},
    )
    hard_constraint = Constraint(id="inside-envelope", expression="spaces remain inside envelope")
    soft_preference = Preference(
        id="daylight-preference",
        description="Prefer daylight",
        target="daylight",
    )
    objective = Objective(id="area-objective", metric="usable_area", direction="maximize")

    analysis = ArchitecturalAnalysis(
        problem_id="problem-4",
        problem_version=1,
        summary="Existing semantic records are retained.",
        hard_constraints=[hard_requirement, hard_constraint],
        soft_preferences=[soft_preference],
        objectives=[objective],
    )

    assert analysis.hard_constraints == [hard_requirement, hard_constraint]
    assert analysis.soft_preferences == [soft_preference]
    assert analysis.objectives == [objective]


def test_analysis_serialization_and_deserialization():
    analysis = ArchitecturalAnalysis(
        problem_id="problem-5",
        problem_version=2,
        summary="Serializable analysis.",
        decision_dimensions=[DecisionDimension.PRIVACY],
        fixed_decisions=[
            DecisionRecord(
                id="privacy-fixed",
                dimension=DecisionDimension.PRIVACY,
                subject="bedrooms",
                value=True,
                status=DecisionStatus.DERIVED,
            )
        ],
    )

    restored = ArchitecturalAnalysis.model_validate(analysis.model_dump())

    assert restored == analysis
    assert restored.fixed_decisions[0].dimension is DecisionDimension.PRIVACY


def test_analysis_rejects_invalid_enum_values():
    with pytest.raises(ValidationError):
        DecisionRecord(
            id="invalid",
            dimension="staircase_count",
            subject="circulation",
            status="fixed",
        )

    with pytest.raises(ValidationError):
        ConflictRecord(
            id="invalid-conflict",
            type="contradiction",
            severity="warning",
            status="ask_user",
            explanation="Invalid status",
        )


def test_analysis_rejects_duplicate_ids_within_record_collections():
    with pytest.raises(ValidationError, match="IDs must be unique"):
        ArchitecturalAnalysis(
            problem_id="problem-6",
            problem_version=1,
            summary="Duplicate IDs are invalid.",
            conflicts=[
                ConflictRecord(
                    id="same-id",
                    type="tradeoff",
                    severity=AnalysisSeverity.WARNING,
                    status=ConflictStatus.DETECTED,
                    explanation="First conflict",
                ),
                ConflictRecord(
                    id="same-id",
                    type="tradeoff",
                    severity=AnalysisSeverity.WARNING,
                    status=ConflictStatus.DETECTED,
                    explanation="Second conflict",
                ),
            ],
        )