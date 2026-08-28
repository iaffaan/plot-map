import pytest
from pydantic import ValidationError

from app.schemas.architectural_analysis import (
    AnalysisSeverity,
    DecisionDimension,
    DecisionRecord,
    DecisionStatus,
    DependencyRecord,
)
from app.schemas.design_problem import Constraint, Objective, Preference, Requirement
from app.schemas.design_strategy import (
    DesignStrategy,
    FeasibilityExpectation,
    StrategyRisk,
    TradeOff,
)


def strategy(**kwargs) -> DesignStrategy:
    return DesignStrategy(
        id=kwargs.pop("id", "strategy-1"),
        source_problem_id=kwargs.pop("source_problem_id", "problem-1"),
        source_problem_version=kwargs.pop("source_problem_version", 1),
        source_analysis_id=kwargs.pop("source_analysis_id", "analysis-1"),
        name=kwargs.pop("name", "Conceptual strategy"),
        approach=kwargs.pop("approach", "Organize the building around a shared circulation concept."),
        rationale=kwargs.pop("rationale", "This strategy addresses the analyzed decision space."),
        **kwargs,
    )


def test_shared_circulation_strategy_is_conceptual():
    result = strategy(
        name="Shared circulation",
        decisions=[
            DecisionRecord(
                id="circulation-choice",
                dimension=DecisionDimension.VERTICAL_CIRCULATION,
                subject="building circulation",
                value="shared",
                source_ids=["shared-circulation"],
                status=DecisionStatus.DERIVED,
            )
        ],
        flexible_decisions=[DecisionDimension.FLOOR_ALLOCATION],
        requirements_satisfied=["shared-circulation"],
        feasibility_expectation=FeasibilityExpectation.CONDITIONALLY_FEASIBLE,
    )

    assert result.decisions[0].value == "shared"
    assert result.flexible_decisions == [DecisionDimension.FLOOR_ALLOCATION]
    assert "x" not in result.model_dump()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("Independent circulation", "independent"),
        ("Hybrid circulation", "hybrid"),
        ("Ground-floor organization", "ground_floor_only"),
        ("Distributed-floor organization", "distributed"),
    ],
)
def test_strategy_alternatives_use_generic_decisions(name: str, value: str):
    result = strategy(
        id=name.lower().replace(" ", "-"),
        name=name,
        decisions=[
            DecisionRecord(
                id="organization-choice",
                dimension=DecisionDimension.UNIT_ORGANIZATION,
                subject="building organization",
                value=value,
                status=DecisionStatus.DERIVED,
            )
        ],
    )

    assert result.name == name
    assert result.decisions[0].dimension is DecisionDimension.UNIT_ORGANIZATION


def test_privacy_and_area_efficiency_tradeoff_is_explicit():
    result = strategy(
        name="Privacy-oriented organization",
        trade_offs=[
            TradeOff(
                id="privacy-area-tradeoff",
                improved_dimension=DecisionDimension.PRIVACY,
                reduced_dimension=DecisionDimension.COST_STRATEGY,
                explanation="Additional separation may increase construction complexity.",
                source_ids=["privacy-preference", "area-objective"],
                severity=AnalysisSeverity.WARNING,
                accepted=True,
            )
        ],
        objectives_targeted=["area-objective"],
        preferences_supported=["privacy-preference"],
    )

    assert result.trade_offs[0].accepted is True
    assert result.trade_offs[0].source_ids == ["privacy-preference", "area-objective"]


def test_strategy_reuses_existing_records_and_preserves_provenance():
    requirement = Requirement(id="req-1", kind="privacy", subject="units", value="high")
    constraint = Constraint(id="constraint-1", expression="required access remains possible")
    preference = Preference(id="pref-1", description="Prefer daylight", target="daylight")
    objective = Objective(id="objective-1", metric="usable_area", direction="maximize")

    result = strategy(
        requirements_satisfied=[requirement.id],
        constraints_addressed=[constraint.id],
        preferences_supported=[preference.id],
        objectives_targeted=[objective.id],
        provenance={
            "source_requirement_ids": [requirement.id],
            "source_constraint_ids": [constraint.id],
            "source_preference_ids": [preference.id],
            "source_objective_ids": [objective.id],
        },
    )

    assert result.provenance["source_requirement_ids"] == ["req-1"]
    assert result.constraints_addressed == ["constraint-1"]


def test_strategy_supports_risks_dependencies_and_conditional_feasibility():
    result = strategy(
        feasibility_expectation=FeasibilityExpectation.CONDITIONALLY_FEASIBLE,
        risks=[
            StrategyRisk(
                id="core-capacity-risk",
                description="The selected organization may require more service area than available.",
                severity=AnalysisSeverity.WARNING,
                source_ids=["site-constraint"],
            )
        ],
        dependencies=[
            DependencyRecord(
                id="circulation-impact",
                source_dimension=DecisionDimension.VERTICAL_CIRCULATION,
                affected_dimensions=[DecisionDimension.FLOOR_ALLOCATION],
                relationship="affects",
                explanation="Vertical circulation affects floor organization.",
            )
        ],
        assumptions=["Site orientation will be confirmed before realization."],
    )

    assert result.feasibility_expectation is FeasibilityExpectation.CONDITIONALLY_FEASIBLE
    assert result.risks[0].source_ids == ["site-constraint"]
    assert result.dependencies[0].source_dimension is DecisionDimension.VERTICAL_CIRCULATION


def test_strategy_serializes_and_deserializes_without_geometry_or_solver_objects():
    result = strategy(
        confidence=0.8,
        feasibility_expectation=FeasibilityExpectation.EXPECTED_FEASIBLE,
        flexible_decisions=[DecisionDimension.ORIENTATION],
    )

    restored = DesignStrategy.model_validate(result.model_dump())

    assert restored == result
    assert "x" not in result.model_dump()
    assert "solver_status" not in result.model_dump()
    assert "tbm" not in result.model_dump()


def test_strategy_rejects_invalid_values_and_duplicate_ids():
    with pytest.raises(ValidationError):
        strategy(confidence=1.1)

    with pytest.raises(ValidationError):
        strategy(feasibility_expectation="solved")

    with pytest.raises(ValidationError, match="source_problem_id"):
        strategy(source_problem_id=" ")

    with pytest.raises(ValidationError, match="IDs must be unique"):
        strategy(
            risks=[
                StrategyRisk(id="same", description="one", severity=AnalysisSeverity.INFO),
                StrategyRisk(id="same", description="two", severity=AnalysisSeverity.INFO),
            ]
        )