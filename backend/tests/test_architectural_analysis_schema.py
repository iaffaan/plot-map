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
    DimensionRelationship,
    FeasibilityConcern,
    IncompatibilityRule,
    RelationshipImpact,
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
    assert analysis.incompatibilities == []
    assert analysis.relationships == []


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
            dimension=DecisionDimension.VERTICAL_CIRCULATION,
            subject="circulation",
            status="invalid_decision_status",
        )

    with pytest.raises(ValidationError):
        ConflictRecord(
            id="invalid-conflict",
            type="contradiction",
            severity="warning",
            status="invalid_status",
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


# =====================================================================
# STAGE 3B.3A — DATA CONTRACT & GENERALITY TESTS
# =====================================================================


def test_3b3a_decision_record_with_string_alternatives():
    record = DecisionRecord(
        id="dec-ventilation",
        dimension="natural_ventilation_strategy",
        subject="building",
        alternatives=["courtyard", "cross_ventilation", "mechanical_assistance"],
        status=DecisionStatus.UNRESOLVED,
        rationale="Ventilation unconstrained by zoning code.",
    )
    assert record.dimension == "natural_ventilation_strategy"
    assert len(record.alternatives) == 3
    assert "courtyard" in record.alternatives


def test_3b3a_decision_record_with_numeric_alternatives():
    record = DecisionRecord(
        id="dec-floors",
        dimension="floor_count",
        subject="building",
        alternatives=[1, 2, 3, 4],
        status=DecisionStatus.FLEXIBLE,
    )
    assert record.alternatives == [1, 2, 3, 4]


def test_3b3a_decision_record_with_boolean_alternatives():
    record = DecisionRecord(
        id="dec-elevator",
        dimension="has_elevator",
        subject="circulation",
        alternatives=[True, False],
        status=DecisionStatus.FLEXIBLE,
    )
    assert record.alternatives == [True, False]


def test_3b3a_decision_record_with_structured_serializable_alternatives():
    record = DecisionRecord(
        id="dec-core",
        dimension="service_core_type",
        subject="service",
        alternatives=[
            {"type": "central", "min_width": 6.0},
            {"type": "distributed", "min_width": 4.0},
        ],
        status=DecisionStatus.FLEXIBLE,
    )
    assert len(record.alternatives) == 2
    assert record.alternatives[0]["type"] == "central"


def test_3b3a_empty_alternatives_and_decision_without_alternatives_valid():
    record1 = DecisionRecord(
        id="dec-1",
        dimension=DecisionDimension.CIRCULATION,
        subject="core",
        status=DecisionStatus.FIXED,
        value="shared",
    )
    record2 = DecisionRecord(
        id="dec-2",
        dimension=DecisionDimension.CIRCULATION,
        subject="core",
        alternatives=[],
        status=DecisionStatus.FIXED,
    )
    assert record1.alternatives == []
    assert record2.alternatives == []


def test_3b3a_incompatibility_rule_serialization_deserialization():
    rule = IncompatibilityRule(
        id="incompat-1",
        dimension_a="structural_system",
        value_a="load_bearing",
        dimension_b="spatial_layout",
        value_b="large_open_span",
        explanation="Load bearing masonry walls prohibit large column-free spans.",
        source_ids=["struct-code"],
    )
    dumped = rule.model_dump()
    restored = IncompatibilityRule.model_validate(dumped)

    assert restored == rule
    assert restored.value_a == "load_bearing"
    assert restored.source_ids == ["struct-code"]


def test_3b3a_dimension_relationship_serialization_deserialization():
    rel = DimensionRelationship(
        id="rel-1",
        source_dimension="natural_ventilation_strategy",
        source_value="courtyard",
        target="usable_area",
        impact=RelationshipImpact.REDUCES,
        explanation="Courtyard lightwell subtracts gross floor area.",
        severity=AnalysisSeverity.WARNING,
        source_ids=["req-vent"],
    )
    dumped = rel.model_dump()
    restored = DimensionRelationship.model_validate(dumped)

    assert restored == rel
    assert restored.impact is RelationshipImpact.REDUCES
    assert restored.severity is AnalysisSeverity.WARNING


def test_3b3a_relationship_impact_enum_validation():
    for impact in ["improves", "reduces", "constrains", "depends_on"]:
        rel = DimensionRelationship(
            id=f"rel-{impact}",
            source_dimension="dim",
            source_value="val",
            target="target",
            impact=impact,
            explanation="Valid impact.",
        )
        assert rel.impact.value == impact

    with pytest.raises(ValidationError):
        DimensionRelationship(
            id="rel-invalid",
            source_dimension="dim",
            source_value="val",
            target="target",
            impact="invalid_impact_enum",
            explanation="Invalid impact enum.",
        )


def test_3b3a_duplicate_ids_rejected_in_incompatibilities_and_relationships():
    rule1 = IncompatibilityRule(
        id="dup-id",
        dimension_a="d1",
        value_a="v1",
        dimension_b="d2",
        value_b="v2",
        explanation="e1",
    )
    rule2 = IncompatibilityRule(
        id="dup-id",
        dimension_a="d3",
        value_a="v3",
        dimension_b="d4",
        value_b="v4",
        explanation="e2",
    )

    with pytest.raises(ValidationError, match="IDs must be unique"):
        ArchitecturalAnalysis(
            problem_id="prob-dup",
            problem_version=1,
            summary="Duplicate incompatibilities",
            incompatibilities=[rule1, rule2],
        )

    rel1 = DimensionRelationship(
        id="dup-rel",
        source_dimension="d1",
        source_value="v1",
        target="t1",
        impact=RelationshipImpact.IMPROVES,
        explanation="e1",
    )
    rel2 = DimensionRelationship(
        id="dup-rel",
        source_dimension="d2",
        source_value="v2",
        target="t2",
        impact=RelationshipImpact.REDUCES,
        explanation="e2",
    )

    with pytest.raises(ValidationError, match="IDs must be unique"):
        ArchitecturalAnalysis(
            problem_id="prob-dup-rel",
            problem_version=1,
            summary="Duplicate relationships",
            relationships=[rel1, rel2],
        )


def test_3b3a_invalid_non_serializable_values_rejected():
    class DummyPythonObject:
        pass

    with pytest.raises(ValidationError, match="JSON-serializable"):
        DecisionRecord(
            id="dec-invalid-val",
            dimension="dim",
            subject="subj",
            value=DummyPythonObject(),
            status=DecisionStatus.FLEXIBLE,
        )

    with pytest.raises(ValidationError, match="JSON-serializable"):
        DecisionRecord(
            id="dec-invalid-alt",
            dimension="dim",
            subject="subj",
            alternatives=[DummyPythonObject()],
            status=DecisionStatus.FLEXIBLE,
        )


def test_3b3a_unseen_dimensions_accepted():
    unseen_dims = [
        "natural_ventilation_strategy",
        "structural_system",
        "daylight_strategy",
        "brand_new_custom_dimension",
    ]

    analysis = ArchitecturalAnalysis(
        problem_id="prob-unseen",
        problem_version=1,
        summary="Analysis with dynamic unseen decision dimensions.",
        decision_dimensions=unseen_dims,
        flexible_decisions=[
            DecisionRecord(
                id=f"dec-{dim}",
                dimension=dim,
                subject="building",
                alternatives=["opt1", "opt2"],
                status=DecisionStatus.UNRESOLVED,
            )
            for dim in unseen_dims
        ],
    )

    assert analysis.decision_dimensions == unseen_dims
    assert len(analysis.flexible_decisions) == 4
    assert analysis.flexible_decisions[0].dimension == "natural_ventilation_strategy"


def test_3b3a_json_serialization_round_trip():
    rule = IncompatibilityRule(
        id="inc-1",
        dimension_a="natural_ventilation_strategy",
        value_a="courtyard",
        dimension_b="structural_system",
        value_b="mass_timber",
        explanation="Courtyard detail constraint",
    )
    rel = DimensionRelationship(
        id="rel-1",
        source_dimension="daylight_strategy",
        source_value="atrium",
        target="spatial_efficiency",
        impact=RelationshipImpact.IMPROVES,
        explanation="Atrium brings light to inner core",
    )
    analysis = ArchitecturalAnalysis(
        problem_id="prob-full-json",
        problem_version=1,
        summary="JSON round-trip test.",
        incompatibilities=[rule],
        relationships=[rel],
        flexible_decisions=[
            DecisionRecord(
                id="dec-unseen",
                dimension="brand_new_dimension",
                subject="building",
                alternatives=["A", "B", "C"],
                status=DecisionStatus.UNRESOLVED,
            )
        ],
    )

    json_str = analysis.model_dump_json()
    restored = ArchitecturalAnalysis.model_validate_json(json_str)

    assert restored == analysis
    assert restored.incompatibilities[0].dimension_a == "natural_ventilation_strategy"
    assert restored.relationships[0].impact is RelationshipImpact.IMPROVES
    assert restored.flexible_decisions[0].alternatives == ["A", "B", "C"]