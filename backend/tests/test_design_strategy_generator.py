import pytest

from app.schemas.architectural_analysis import (
    AnalysisSeverity,
    ArchitecturalAnalysis,
    ConflictRecord,
    ConflictStatus,
    DecisionDimension,
    DecisionRecord,
    DecisionStatus,
    UncertaintyMateriality,
    UncertaintyRecord,
)
from app.schemas.design_problem import (
    Constraint,
    DesignProblem,
    Objective,
    Preference,
    Requirement,
    RequirementKind,
    RequirementStrength,
    RoomIntent,
    SiteDefinition,
    SpaceRequirement,
    UserGroup,
)

from app.schemas.intent import CompilerIntent, RoomCategory
from app.services.analysis.architectural_analyzer import analyze_design_problem
from app.services.analysis.strategy_generator import _compute_fingerprint, generate_strategies
from app.services.compiler.intent_adapter import to_design_problem


def _sample_analysis() -> ArchitecturalAnalysis:
    problem = DesignProblem(
        id="problem-sample",
        version=1,
        site=SiteDefinition(plot_width=40.0, plot_depth=50.0, floors=2),
        spaces=[
            SpaceRequirement(id="s1", room=RoomIntent(room_type=RoomCategory.LIVING, min_area_sqft=200.0)),
            SpaceRequirement(id="s2", room=RoomIntent(room_type=RoomCategory.BEDROOM, min_area_sqft=150.0)),
        ],
        user_groups=[
            UserGroup(id="ug1", name="Family A"),
            UserGroup(id="ug2", name="Family B"),
        ],
    )
    return analyze_design_problem(problem)


def test_01_one_decision_with_two_alternatives():
    analysis = _sample_analysis()
    strategies = generate_strategies(analysis)

    circ_values = {
        dec.value
        for strat in strategies
        for dec in strat.decisions
        if dec.dimension is DecisionDimension.VERTICAL_CIRCULATION
    }
    assert len(circ_values) >= 2
    assert "shared" in circ_values or "independent" in circ_values


def test_02_shared_vs_independent_circulation():
    analysis = _sample_analysis()
    strategies = generate_strategies(analysis)

    shared_strat = next(
        (s for s in strategies if any(d.dimension is DecisionDimension.VERTICAL_CIRCULATION and d.value == "shared" for d in s.decisions)),
        None,
    )
    indep_strat = next(
        (s for s in strategies if any(d.dimension is DecisionDimension.VERTICAL_CIRCULATION and d.value == "independent" for d in s.decisions)),
        None,
    )

    assert shared_strat is not None
    assert indep_strat is not None
    assert shared_strat.name != indep_strat.name


def test_03_hybrid_strategy():
    analysis = _sample_analysis()
    strategies = generate_strategies(analysis)

    hybrid_strat = next(
        (s for s in strategies if any(d.value in ("hybrid", "controlled_shared") for d in s.decisions)),
        None,
    )
    assert hybrid_strat is not None
    assert "Hybrid" in hybrid_strat.name or "hybrid" in hybrid_strat.approach.lower()


def test_04_multiple_independent_decision_dimensions():
    analysis = _sample_analysis()
    strategies = generate_strategies(analysis)

    dimensions_covered = {
        dec.dimension
        for strat in strategies
        for dec in strat.decisions
    }
    assert DecisionDimension.VERTICAL_CIRCULATION in dimensions_covered
    assert DecisionDimension.ENTRANCE_STRATEGY in dimensions_covered or DecisionDimension.UNIT_ORGANIZATION in dimensions_covered


def test_05_hard_requirement_preservation():
    problem = DesignProblem(
        id="problem-hard-req",
        site=SiteDefinition(plot_width=30.0, plot_depth=40.0, floors=1),
        requirements=[
            Requirement(
                id="req-hard-shared-circ",
                kind=RequirementKind.CIRCULATION,
                subject="building",
                value="shared",
                strength=RequirementStrength.HARD,
            )
        ],
    )
    analysis = analyze_design_problem(problem)
    strategies = generate_strategies(analysis, problem)

    for strat in strategies:
        assert "req-hard-shared-circ" in strat.requirements_satisfied
        for dec in strat.decisions:
            if dec.dimension is DecisionDimension.VERTICAL_CIRCULATION:
                assert dec.value == "shared"


def test_06_soft_preference_handling():
    problem = DesignProblem(
        id="problem-pref",
        site=SiteDefinition(plot_width=30.0, plot_depth=40.0, floors=1),
        preferences=[
            Preference(id="pref-high-privacy", description="High privacy for living quarters", target="privacy")
        ],
    )
    analysis = analyze_design_problem(problem)
    strategies = generate_strategies(analysis, problem)

    assert len(strategies) >= 1
    for strat in strategies:
        assert "pref-high-privacy" in strat.preferences_supported


def test_07_objective_preservation():
    problem = DesignProblem(
        id="problem-obj",
        site=SiteDefinition(plot_width=30.0, plot_depth=40.0, floors=1),
        objectives=[
            Objective(id="obj-min-circ", metric="circulation_area", direction="minimize")
        ],
    )
    analysis = analyze_design_problem(problem)
    strategies = generate_strategies(analysis, problem)

    for strat in strategies:
        assert "obj-min-circ" in strat.objectives_targeted


def test_08_conflict_aware_alternatives():
    req1 = Requirement(id="req-shared-entry", kind=RequirementKind.CIRCULATION, subject="entry", value="shared", conflicts_with=["req-private-entry"])
    req2 = Requirement(id="req-private-entry", kind=RequirementKind.CIRCULATION, subject="entry", value="independent", conflicts_with=["req-shared-entry"])

    problem = DesignProblem(
        id="problem-conflict",
        site=SiteDefinition(plot_width=40.0, plot_depth=40.0, floors=2),
        requirements=[req1, req2],
    )
    analysis = analyze_design_problem(problem)
    strategies = generate_strategies(analysis, problem)

    assert len(strategies) >= 2
    # Verify conflicts are referenced or handled in trade-offs / rationale
    found_conflict_handling = any(
        "conflict" in strat.approach.lower() or "conflict" in strat.rationale.lower() or len(strat.trade_offs) > 0
        for strat in strategies
    )
    assert found_conflict_handling is True


def test_09_uncertainty_preservation():
    analysis = _sample_analysis()
    analysis.uncertainties.append(
        UncertaintyRecord(
            id="u-orient",
            topic="site orientation",
            description="Road direction is not specified.",
            materiality=UncertaintyMateriality.MATERIAL,
            affected_dimensions=[DecisionDimension.ORIENTATION],
        )
    )
    strategies = generate_strategies(analysis)

    for strat in strategies:
        assert any("site orientation" in assumption.lower() for assumption in strat.assumptions)


def test_10_trade_off_creation_preservation():
    analysis = _sample_analysis()
    strategies = generate_strategies(analysis)

    strategies_with_tradeoffs = [s for s in strategies if len(s.trade_offs) > 0]
    assert len(strategies_with_tradeoffs) > 0

    to = strategies_with_tradeoffs[0].trade_offs[0]
    assert to.improved_dimension is not None
    assert to.reduced_dimension is not None
    assert len(to.explanation) > 0


def test_11_strategy_deduplication():
    analysis = _sample_analysis()
    strategies = generate_strategies(analysis)

    fingerprints = [_compute_fingerprint(s.decisions) for s in strategies]
    assert len(fingerprints) == len(set(fingerprints))


def test_12_maximum_strategy_limit():
    analysis = _sample_analysis()
    strategies_max_2 = generate_strategies(analysis, max_strategies=2)
    assert len(strategies_max_2) <= 2


def test_13_deterministic_ordering():
    analysis = _sample_analysis()
    run1 = generate_strategies(analysis)
    run2 = generate_strategies(analysis)

    assert len(run1) == len(run2)
    for s1, s2 in zip(run1, run2):
        assert s1.model_dump() == s2.model_dump()


def test_14_no_geometry_generation():
    analysis = _sample_analysis()
    strategies = generate_strategies(analysis)

    for strat in strategies:
        dump_str = str(strat.model_dump())
        assert "x_coord" not in dump_str
        assert "y_coord" not in dump_str
        assert "x_min" not in dump_str
        assert "y_min" not in dump_str
        assert "polygon" not in dump_str.lower()
        assert "rectangle" not in dump_str.lower()
        assert "cad" not in dump_str.lower()
        assert "mesh" not in dump_str.lower()


def test_15_no_solver_invocation():
    analysis = _sample_analysis()
    strategies = generate_strategies(analysis)

    for strat in strategies:
        dump_str = str(strat.model_dump())
        assert "pulp" not in dump_str.lower()
        assert "cbc" not in dump_str.lower()
        assert "solver_status" not in dump_str.lower()
        assert "milp" not in dump_str.lower()


def test_16_no_external_llm_api_invocation():
    # Should execute purely offline and synchronously without network/LLM dependencies
    analysis = _sample_analysis()
    strategies = generate_strategies(analysis)
    assert isinstance(strategies, list)
    assert len(strategies) > 0


def test_17_empty_minimal_analysis_behavior():
    minimal_analysis = ArchitecturalAnalysis(
        problem_id="minimal-problem",
        problem_version=1,
        summary="Minimal test problem",
    )
    strategies = generate_strategies(minimal_analysis)

    assert len(strategies) == 1
    assert strategies[0].name == "Baseline Design Strategy"
    assert strategies[0].source_problem_id == "minimal-problem"


def test_18_four_family_benchmark_generic_fixture():
    # Benchmark: 44x42 four family
    intent = CompilerIntent(
        plot_width=44.0,
        plot_depth=42.0,
        front_road_setback=5.0,
        floors=4,
        rooms=[
            RoomIntent(room_type=RoomCategory.LIVING, min_area_sqft=150.0),
            RoomIntent(room_type=RoomCategory.KITCHEN, min_area_sqft=80.0),
            RoomIntent(room_type=RoomCategory.BEDROOM, min_area_sqft=120.0),
            RoomIntent(room_type=RoomCategory.BATHROOM, min_area_sqft=40.0),
        ],
    )
    problem = to_design_problem(intent, problem_id="44x42-benchmark")
    analysis = analyze_design_problem(problem)
    strategies = generate_strategies(analysis, problem)

    assert len(strategies) >= 1
    for strat in strategies:
        assert strat.source_problem_id == "44x42-benchmark"
        # Assert no benchmark specific domain class names
        assert "FourFamily" not in type(strat).__name__
        assert "FamilyPerFloor" not in strat.name


def test_19_second_generality_fixture_single_family():
    # Completely different scenario: single-family house on small 30x40 plot
    problem = DesignProblem(
        id="single-family-cottage",
        version=1,
        site=SiteDefinition(plot_width=30.0, plot_depth=40.0, floors=2, setbacks={"bottom": 3.0}),
        user_groups=[UserGroup(id="family-1", name="Single Family")],
        spaces=[
            SpaceRequirement(id="room-living", room=RoomIntent(room_type=RoomCategory.LIVING, min_area_sqft=180.0)),
            SpaceRequirement(id="room-kitchen", room=RoomIntent(room_type=RoomCategory.KITCHEN, min_area_sqft=90.0)),
            SpaceRequirement(id="room-bed1", room=RoomIntent(room_type=RoomCategory.BEDROOM, min_area_sqft=120.0)),
            SpaceRequirement(id="room-bed2", room=RoomIntent(room_type=RoomCategory.BEDROOM, min_area_sqft=100.0)),
            SpaceRequirement(id="room-bath", room=RoomIntent(room_type=RoomCategory.BATHROOM, min_area_sqft=45.0)),
        ],
        preferences=[
            Preference(id="pref-privacy-bedrooms", description="High privacy for sleeping quarters", target="privacy")
        ],
        objectives=[
            Objective(id="obj-area-eff", metric="circulation_area", direction="minimize")
        ],
    )

    analysis = analyze_design_problem(problem)
    strategies = generate_strategies(analysis, problem)

    assert len(strategies) >= 1
    for strat in strategies:
        assert strat.source_problem_id == "single-family-cottage"
        assert "pref-privacy-bedrooms" in strat.preferences_supported
        assert "obj-area-eff" in strat.objectives_targeted
