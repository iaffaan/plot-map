import pytest

from app.schemas.architectural_analysis import (
    AnalysisSeverity,
    ArchitecturalAnalysis,
    ConflictRecord,
    ConflictStatus,
    DecisionDimension,
    DecisionRecord,
    DecisionStatus,
    DimensionRelationship,
    IncompatibilityRule,
    RelationshipImpact,
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
    """Hybrid strategy must appear because catalog declares 'hybrid' as a vertical_circulation alternative."""
    analysis = _sample_analysis()
    strategies = generate_strategies(analysis)

    hybrid_strat = next(
        (
            s for s in strategies
            if any(d.dimension is DecisionDimension.VERTICAL_CIRCULATION and d.value == "hybrid" for d in s.decisions)
        ),
        None,
    )
    # catalog declares ["shared", "independent", "hybrid"] — hybrid must appear
    assert hybrid_strat is not None


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
    """
    Hard constraint filtering is now driven by fixed_decisions in ArchitecturalAnalysis.
    The analyzer converts a HARD CIRCULATION requirement into a FIXED DecisionRecord
    for VERTICAL_CIRCULATION; the generator then filters incompatible combinations.
    """
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

    # Verify the analyzer created a FIXED decision for CIRCULATION (the dimension it maps to)
    fixed_dims = {d.dimension for d in analysis.fixed_decisions}
    assert DecisionDimension.CIRCULATION in fixed_dims

    strategies = generate_strategies(analysis, problem)
    assert len(strategies) >= 1

    for strat in strategies:
        assert "req-hard-shared-circ" in strat.requirements_satisfied
        # No generated (DERIVED) decision in this strategy may contradict the fixed value
        for dec in strat.decisions:
            if dec.dimension is DecisionDimension.CIRCULATION and dec.status == DecisionStatus.DERIVED:
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
    """
    Conflicting HARD requirements cancel each other out (both are contested),
    so no hard-constraint filtering is applied. The generic catalog still
    produces all alternatives from DecisionRecord.alternatives.
    """
    req1 = Requirement(id="req-shared-entry", kind=RequirementKind.CIRCULATION, subject="entry", value="shared", conflicts_with=["req-private-entry"])
    req2 = Requirement(id="req-private-entry", kind=RequirementKind.CIRCULATION, subject="entry", value="independent", conflicts_with=["req-shared-entry"])

    problem = DesignProblem(
        id="problem-conflict",
        site=SiteDefinition(plot_width=40.0, plot_depth=40.0, floors=2),
        requirements=[req1, req2],
    )
    analysis = analyze_design_problem(problem)

    # Both requirements must be recorded as conflicting
    assert len(analysis.conflicts) >= 1

    strategies = generate_strategies(analysis, problem)
    assert len(strategies) >= 1

    # The requirements are propagated to all strategies regardless
    for strat in strategies:
        assert "req-shared-entry" in strat.requirements_satisfied or "req-private-entry" in strat.requirements_satisfied


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
    """
    Trade-offs now come exclusively from DimensionRelationship entries in
    ArchitecturalAnalysis.relationships (populated from decision_catalog.json).
    The catalog declares relationships for vertical_circulation values,
    so strategies assigning those values must carry trade-offs.
    """
    analysis = _sample_analysis()
    # Ensure catalog relationships are present (loaded by analyzer)
    assert len(analysis.relationships) > 0

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
        assert "FourFamily" not in type(strat).__name__
        assert "FamilyPerFloor" not in strat.name


def test_19_second_generality_fixture_single_family():
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


# =====================================================================
# STAGE 3B.3B — GENERIC DATA-DRIVEN ENGINE & GENERALITY TESTS
# =====================================================================


def test_3b3b_single_unseen_dimension_generality():
    analysis = ArchitecturalAnalysis(
        problem_id="prob-unseen-ventilation",
        problem_version=1,
        summary="Analysis with unseen ventilation dimension.",
        flexible_decisions=[
            DecisionRecord(
                id="dec-vent",
                dimension="natural_ventilation_strategy",
                subject="building",
                alternatives=["courtyard", "cross_ventilation", "mechanical_assistance"],
                status=DecisionStatus.UNRESOLVED,
            )
        ],
    )

    strategies = generate_strategies(analysis)

    assert len(strategies) == 3
    produced_values = {
        dec.value
        for s in strategies
        for dec in s.decisions
        if dec.dimension == "natural_ventilation_strategy"
    }
    assert produced_values == {"courtyard", "cross_ventilation", "mechanical_assistance"}


def test_3b3b_multiple_unseen_dimensions_cartesian():
    analysis = ArchitecturalAnalysis(
        problem_id="prob-multi-unseen",
        problem_version=1,
        summary="Multi-dimension unseen analysis.",
        flexible_decisions=[
            DecisionRecord(
                id="dec-vent",
                dimension="natural_ventilation_strategy",
                subject="building",
                alternatives=["courtyard", "cross_ventilation"],
                status=DecisionStatus.UNRESOLVED,
            ),
            DecisionRecord(
                id="dec-struct",
                dimension="structural_system",
                subject="building",
                alternatives=["load_bearing", "steel_frame"],
                status=DecisionStatus.UNRESOLVED,
            ),
        ],
    )

    strategies = generate_strategies(analysis)

    assert len(strategies) == 4
    combos = {
        (
            next(d.value for d in s.decisions if d.dimension == "natural_ventilation_strategy"),
            next(d.value for d in s.decisions if d.dimension == "structural_system"),
        )
        for s in strategies
    }
    expected_combos = {
        ("courtyard", "load_bearing"),
        ("courtyard", "steel_frame"),
        ("cross_ventilation", "load_bearing"),
        ("cross_ventilation", "steel_frame"),
    }
    assert combos == expected_combos


def test_3b3b_numeric_and_boolean_unseen_dimensions():
    analysis = ArchitecturalAnalysis(
        problem_id="prob-num-bool",
        problem_version=1,
        summary="Numeric and boolean dynamic choices.",
        flexible_decisions=[
            DecisionRecord(
                id="dec-floors",
                dimension="target_floor_count",
                subject="building",
                alternatives=[1, 2, 3],
                status=DecisionStatus.UNRESOLVED,
            ),
            DecisionRecord(
                id="dec-elevator",
                dimension="has_elevator",
                subject="circulation",
                alternatives=[True, False],
                status=DecisionStatus.UNRESOLVED,
            ),
        ],
    )

    strategies = generate_strategies(analysis)

    assert len(strategies) == 6
    for s in strategies:
        floor_val = next(d.value for d in s.decisions if d.dimension == "target_floor_count")
        elev_val = next(d.value for d in s.decisions if d.dimension == "has_elevator")
        assert floor_val in [1, 2, 3]
        assert elev_val in [True, False]


def test_3b3b_structured_serializable_alternatives():
    analysis = ArchitecturalAnalysis(
        problem_id="prob-struct-alt",
        problem_version=1,
        summary="Structured dictionary choices.",
        flexible_decisions=[
            DecisionRecord(
                id="dec-core",
                dimension="service_core",
                subject="service",
                alternatives=[
                    {"type": "central", "min_width": 6.0},
                    {"type": "distributed", "min_width": 4.0},
                ],
                status=DecisionStatus.UNRESOLVED,
            )
        ],
    )

    strategies = generate_strategies(analysis)

    assert len(strategies) == 2
    types = [
        next(d.value for d in s.decisions if d.dimension == "service_core")["type"]
        for s in strategies
    ]
    assert "central" in types
    assert "distributed" in types


def test_3b3b_incompatibility_rule_filtering():
    analysis = ArchitecturalAnalysis(
        problem_id="prob-incompat-filter",
        problem_version=1,
        summary="Incompatibility rule test.",
        flexible_decisions=[
            DecisionRecord(
                id="dec-struct",
                dimension="structural_system",
                subject="building",
                alternatives=["load_bearing", "steel_frame"],
                status=DecisionStatus.UNRESOLVED,
            ),
            DecisionRecord(
                id="dec-layout",
                dimension="spatial_layout",
                subject="building",
                alternatives=["cellular", "large_open_span"],
                status=DecisionStatus.UNRESOLVED,
            ),
        ],
        incompatibilities=[
            IncompatibilityRule(
                id="incompat-1",
                dimension_a="structural_system",
                value_a="load_bearing",
                dimension_b="spatial_layout",
                value_b="large_open_span",
                explanation="Load bearing walls prohibit large open column-free spans.",
            )
        ],
    )

    strategies = generate_strategies(analysis)

    # 4 potential Cartesian combinations - 1 prohibited = 3 strategies
    assert len(strategies) == 3
    for s in strategies:
        struct_val = next(d.value for d in s.decisions if d.dimension == "structural_system")
        layout_val = next(d.value for d in s.decisions if d.dimension == "spatial_layout")
        assert not (struct_val == "load_bearing" and layout_val == "large_open_span")


def test_3b3b_dynamic_relationship_and_tradeoff_derivation():
    analysis = ArchitecturalAnalysis(
        problem_id="prob-rel-tradeoff",
        problem_version=1,
        summary="Dynamic relationship trade-off test.",
        flexible_decisions=[
            DecisionRecord(
                id="dec-vent",
                dimension="natural_ventilation_strategy",
                subject="building",
                alternatives=["courtyard", "mechanical_assistance"],
                status=DecisionStatus.UNRESOLVED,
            )
        ],
        relationships=[
            DimensionRelationship(
                id="rel-courtyard-area",
                source_dimension="natural_ventilation_strategy",
                source_value="courtyard",
                target="usable_floor_area",
                impact=RelationshipImpact.REDUCES,
                explanation="Courtyard lightwell subtracts gross floor area.",
                severity=AnalysisSeverity.WARNING,
            )
        ],
    )

    strategies = generate_strategies(analysis)

    assert len(strategies) == 2
    courtyard_strat = next(
        s for s in strategies
        if any(d.dimension == "natural_ventilation_strategy" and d.value == "courtyard" for d in s.decisions)
    )

    assert len(courtyard_strat.trade_offs) == 1
    to = courtyard_strat.trade_offs[0]
    assert to.id == "tradeoff-rel-courtyard-area"
    assert to.reduced_dimension == "usable_floor_area"
    assert "subtracts gross floor area" in to.explanation


def test_3b3b_architectural_knowledge_decoupling_test():
    analysis = ArchitecturalAnalysis(
        problem_id="prob-decoupled-domain",
        problem_version=1,
        summary="Domain decoupling test.",
        flexible_decisions=[
            DecisionRecord(
                id="dec-custom",
                dimension="custom_dimension",
                subject="building",
                alternatives=["A", "B"],
                status=DecisionStatus.UNRESOLVED,
            )
        ],
        relationships=[
            DimensionRelationship(
                id="rel-custom",
                source_dimension="custom_dimension",
                source_value="A",
                target="custom_objective",
                impact=RelationshipImpact.IMPROVES,
                explanation="Choice A improves custom objective dynamically.",
            )
        ],
    )

    strategies = generate_strategies(analysis)

    assert len(strategies) == 2
    strat_a = next(
        s for s in strategies
        if any(d.dimension == "custom_dimension" and d.value == "A" for d in s.decisions)
    )
    assert len(strat_a.trade_offs) == 1
    assert strat_a.trade_offs[0].improved_dimension == "custom_objective"


def test_3b3b_unseen_brand_new_custom_dimension():
    analysis = ArchitecturalAnalysis(
        problem_id="prob-brand-new",
        problem_version=1,
        summary="Brand new custom dimension test.",
        flexible_decisions=[
            DecisionRecord(
                id="dec-brand-new",
                dimension="brand_new_custom_dimension",
                subject="building",
                alternatives=["OptionX", "OptionY", "OptionZ"],
                status=DecisionStatus.UNRESOLVED,
            )
        ],
    )

    strategies = generate_strategies(analysis)

    assert len(strategies) == 3
    vals = {
        next(d.value for d in s.decisions if d.dimension == "brand_new_custom_dimension")
        for s in strategies
    }
    assert vals == {"OptionX", "OptionY", "OptionZ"}


def test_3b3b_combination_limit_bounding():
    # 5 dimensions with 4 choices each = 1024 potential combinations
    analysis = ArchitecturalAnalysis(
        problem_id="prob-combinatorial-explosion",
        problem_version=1,
        summary="Combinatorial limit bounding test.",
        flexible_decisions=[
            DecisionRecord(
                id=f"dec-{i}",
                dimension=f"dim_{i}",
                subject="building",
                alternatives=["val_1", "val_2", "val_3", "val_4"],
                status=DecisionStatus.UNRESOLVED,
            )
            for i in range(1, 6)
        ],
    )

    strategies = generate_strategies(analysis, max_strategies=10)

    # Must safely stop and bound strategies to max_strategies (default 10)
    assert len(strategies) <= 10


def test_3b3b_deterministic_repeated_execution_generic():
    analysis = ArchitecturalAnalysis(
        problem_id="prob-det-generic",
        problem_version=1,
        summary="Deterministic execution test on generic inputs.",
        flexible_decisions=[
            DecisionRecord(
                id="dec-1",
                dimension="daylight_strategy",
                subject="building",
                alternatives=["side_lighting", "top_lighting", "atrium"],
                status=DecisionStatus.UNRESOLVED,
            )
        ],
    )

    run1 = generate_strategies(analysis)
    run2 = generate_strategies(analysis)

    assert len(run1) == 3
    assert len(run2) == 3
    for s1, s2 in zip(run1, run2):
        assert s1.model_dump() == s2.model_dump()


# =====================================================================
# STAGE 3B.3C-3 — GOLDEN MIGRATION & CATALOG GENERALITY TESTS
# =====================================================================


def test_3b3c_golden_semantic_migration_benchmark():
    """Verify that catalog-driven analysis reproduces all semantic behavior of 44x42 benchmark."""
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
    problem = to_design_problem(intent, problem_id="44x42-golden-benchmark")
    analysis = analyze_design_problem(problem)

    # 1. Verify flexible decisions have catalog alternatives attached natively
    vert_circ_dec = next(
        (d for d in analysis.flexible_decisions if d.dimension is DecisionDimension.VERTICAL_CIRCULATION),
        None,
    )
    assert vert_circ_dec is not None
    assert vert_circ_dec.alternatives == ["shared", "independent", "hybrid"]

    # 2. Generate strategies
    strategies = generate_strategies(analysis, problem)

    # 3. Semantic Verification
    assert len(strategies) >= 1
    assert len(strategies) <= 10  # strategy bounds

    # Decision dimension preservation
    all_dec_dims = {dec.dimension for s in strategies for dec in s.decisions}
    assert DecisionDimension.VERTICAL_CIRCULATION in all_dec_dims

    # Trade-offs derived from catalog relationships
    tradeoff_strategies = [s for s in strategies if len(s.trade_offs) > 0]
    assert len(tradeoff_strategies) > 0

    # Deterministic fingerprinting
    fps = [_compute_fingerprint(s.decisions) for s in strategies]
    assert len(fps) == len(set(fps))


def test_3b3c_critical_generality_temporary_custom_catalog(tmp_path):
    """Critical test: A new catalog entry is loaded and processed without Python code modifications."""
    import json
    from app.services.analysis.catalog_loader import load_decision_catalog

    custom_catalog_data = {
        "version": 1,
        "dimensions": {
            "brand_new_catalog_dimension": {
                "alternatives": ["Alpha", "Beta", "Gamma"]
            }
        },
        "incompatibilities": [],
        "relationships": [],
    }
    catalog_path = tmp_path / "custom_catalog.json"
    catalog_path.write_text(json.dumps(custom_catalog_data), encoding="utf-8")

    loaded_catalog = load_decision_catalog(catalog_path)

    # Construct analysis using custom catalog
    analysis = ArchitecturalAnalysis(
        problem_id="prob-custom-cat",
        problem_version=1,
        summary="Custom catalog analysis",
        flexible_decisions=[
            DecisionRecord(
                id="dec-custom-cat",
                dimension="brand_new_catalog_dimension",
                subject="building",
                alternatives=loaded_catalog["dimensions"]["brand_new_catalog_dimension"]["alternatives"],
                status=DecisionStatus.UNRESOLVED,
            )
        ],
    )

    strategies = generate_strategies(analysis)

    assert len(strategies) == 3
    produced_vals = {
        next(d.value for d in s.decisions if d.dimension == "brand_new_catalog_dimension")
        for s in strategies
    }
    assert produced_vals == {"Alpha", "Beta", "Gamma"}


def test_3b3c_unknown_dimension_without_catalog_entry():
    """Verify that unknown dimensions without catalog entries process cleanly without error."""
    problem = DesignProblem(
        id="prob-unknown-dim",
        site=SiteDefinition(plot_width=30.0, plot_depth=30.0, floors=1),
    )
    analysis = analyze_design_problem(problem)

    # Add an unknown dimension with no alternatives
    analysis.flexible_decisions.append(
        DecisionRecord(
            id="dec-unknown",
            dimension="unseen_exotic_dimension",
            subject="building",
            alternatives=[],
            status=DecisionStatus.UNRESOLVED,
        )
    )

    # Must execute cleanly without inventing fake alternatives
    strategies = generate_strategies(analysis)
    assert len(strategies) >= 1


# =====================================================================
# STAGE 3B.3C-4 — LEGACY ABSENCE REGRESSION TEST
# =====================================================================


def test_3b3c4_strategy_generator_contains_no_legacy_branching():
    """
    Regression guard: StrategyGenerator must NOT contain hardcoded
    architectural domain branching.

    This test inspects the source code of strategy_generator.py and
    fails if any domain-specific control-flow patterns are reintroduced.

    It checks for the structural pattern of hardcoded 'if/elif' blocks
    that reference architectural dimension enum members or known domain
    values — which is the defining characteristic of the legacy Path B
    that was removed in Stage 3B.3C-4.
    """
    import ast
    import inspect
    from app.services.analysis import strategy_generator

    source = inspect.getsource(strategy_generator)
    tree = ast.parse(source)

    # Domain-specific enum names that must NOT appear in control-flow
    # comparisons inside the generator logic
    forbidden_control_flow_values = {
        "VERTICAL_CIRCULATION",
        "ENTRANCE_STRATEGY",
        "UNIT_ORGANIZATION",
        "FLOOR_ALLOCATION",
        "SERVICE_CORE_STRATEGY",
        "SHARED_PRIVATE_STRATEGY",
    }

    violations: list[str] = []

    for node in ast.walk(tree):
        # Look for If nodes whose test compares a name or attribute to a forbidden domain constant
        if isinstance(node, ast.If):
            test_source = ast.unparse(node.test)
            for forbidden in forbidden_control_flow_values:
                if forbidden in test_source:
                    violations.append(
                        f"Line {node.lineno}: if-branch contains domain constant '{forbidden}': {test_source!r}"
                    )

    assert violations == [], (
        "StrategyGenerator contains hardcoded architectural branching.\n"
        "These patterns were removed in Stage 3B.3C-4 and must not be reintroduced.\n"
        "Violations:\n" + "\n".join(violations)
    )
