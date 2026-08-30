"""
Golden End-to-End Orchestration Fixtures for Stage 3B.6-6.

Provides canonical, deterministic problem specifications and orchestration configurations
covering all 12 end-to-end integration scenarios defined in the Stage 3B.6 architecture specification:
1. 44x42 / 4-Family Benchmark
2. Single-Family House
3. Shared Circulation Topology
4. Independent Circulation Topology
5. Hybrid Circulation Topology
6. Multi-Floor Vertical Stacking
7. Centralized Service Core
8. Unseen Custom Decision Dimensions
9. Realization Failure Handling (Infeasible Plot)
10. Phase 1 Pre-Realization Pruning
11. Mixed Success / Failure Candidates
12. Zero Viable Candidates
"""

from app.schemas.design_problem import (
    DesignProblem,
    Objective,
    Preference,
    Requirement,
    RequirementKind,
    RequirementStrength,
    SiteDefinition,
    SpaceRequirement,
)
from app.schemas.intent import RoomCategory, RoomIntent
from app.schemas.orchestration import OrchestrationConfig
from tests.fixtures.golden_organization_fixtures import (
    get_benchmark_44x42_problem,
    get_single_family_problem,
)


def get_golden_44x42_benchmark_scenario() -> tuple[DesignProblem, OrchestrationConfig]:
    """Scenario 1: Benchmark 44x42 ft, 4-family multi-floor residential scenario."""
    prob = get_benchmark_44x42_problem()
    config = OrchestrationConfig(
        max_strategies=3,
        max_candidates_per_strategy=2,
        max_selected=2,
        phase1_prune_threshold=0.20,
        enable_realization=True,
    )
    return prob, config


def get_golden_single_family_scenario() -> tuple[DesignProblem, OrchestrationConfig]:
    """Scenario 2: Single-family 30x40 ft ground floor scenario."""
    prob = get_single_family_problem()
    config = OrchestrationConfig(
        max_strategies=2,
        max_candidates_per_strategy=2,
        max_selected=1,
        enable_realization=True,
    )
    return prob, config


def get_golden_shared_circulation_scenario() -> tuple[DesignProblem, OrchestrationConfig]:
    """Scenario 3: Multi-unit building with shared vertical stair core preference."""
    prob = get_benchmark_44x42_problem()
    prob_dict = prob.model_dump()
    prob_dict["id"] = "golden-prob-shared-circ"
    prob_dict["preferences"].append(
        Preference(
            id="pref-shared-circ",
            description="Shared vertical circulation",
            target="shared",
            weight=1.0,
        ).model_dump()
    )
    custom_prob = DesignProblem.model_validate(prob_dict)
    config = OrchestrationConfig(max_strategies=2, max_candidates_per_strategy=2)
    return custom_prob, config


def get_golden_independent_circulation_scenario() -> tuple[DesignProblem, OrchestrationConfig]:
    """Scenario 4: Multi-unit building with independent circulation preference."""
    prob = get_benchmark_44x42_problem()
    prob_dict = prob.model_dump()
    prob_dict["id"] = "golden-prob-independent-circ"
    prob_dict["preferences"].append(
        Preference(
            id="pref-indep-circ",
            description="Independent vertical circulation",
            target="independent",
            weight=1.0,
        ).model_dump()
    )
    custom_prob = DesignProblem.model_validate(prob_dict)
    config = OrchestrationConfig(max_strategies=2, max_candidates_per_strategy=2)
    return custom_prob, config


def get_golden_hybrid_circulation_scenario() -> tuple[DesignProblem, OrchestrationConfig]:
    """Scenario 5: Multi-unit building with hybrid circulation preference."""
    prob = get_benchmark_44x42_problem()
    prob_dict = prob.model_dump()
    prob_dict["id"] = "golden-prob-hybrid-circ"
    prob_dict["preferences"].append(
        Preference(
            id="pref-hybrid-circ",
            description="Hybrid circulation structure",
            target="hybrid",
            weight=1.0,
        ).model_dump()
    )
    custom_prob = DesignProblem.model_validate(prob_dict)
    config = OrchestrationConfig(max_strategies=2, max_candidates_per_strategy=2)
    return custom_prob, config


def get_golden_multi_floor_stacking_scenario() -> tuple[DesignProblem, OrchestrationConfig]:
    """Scenario 6: Multi-floor vertical stacking residential scenario."""
    prob = get_benchmark_44x42_problem()
    prob_dict = prob.model_dump()
    prob_dict["id"] = "golden-prob-multi-floor-stack"
    prob_dict["site"]["floors"] = 3
    custom_prob = DesignProblem.model_validate(prob_dict)
    config = OrchestrationConfig(max_strategies=2, max_candidates_per_strategy=2)
    return custom_prob, config


def get_golden_centralized_service_core_scenario() -> tuple[DesignProblem, OrchestrationConfig]:
    """Scenario 7: Wet service core centralized stacking scenario."""
    prob = get_benchmark_44x42_problem()
    prob_dict = prob.model_dump()
    prob_dict["id"] = "golden-prob-central-service"
    prob_dict["preferences"].append(
        Preference(
            id="pref-central-core",
            description="Centralized wet service core stack",
            target="centralized",
            weight=1.0,
        ).model_dump()
    )
    custom_prob = DesignProblem.model_validate(prob_dict)
    config = OrchestrationConfig(max_strategies=2, max_candidates_per_strategy=2)
    return custom_prob, config


def get_golden_unseen_custom_dimensions_scenario() -> tuple[DesignProblem, OrchestrationConfig]:
    """Scenario 8: Unseen custom decision dimensions (solar_shading, facade_transparency)."""
    prob = get_single_family_problem()
    prob_dict = prob.model_dump()
    prob_dict["id"] = "golden-prob-custom-dims"
    prob_dict["requirements"].append(
        Requirement(
            id="req-solar-shading",
            kind=RequirementKind.ENVIRONMENTAL,
            subject="building",
            value="external_louver",
            strength=RequirementStrength.SOFT,
        ).model_dump()
    )
    prob_dict["preferences"].append(
        Preference(
            id="pref-facade-transparency",
            description="High glazed facade transparency",
            target="high_glazed",
            weight=0.8,
        ).model_dump()
    )
    custom_prob = DesignProblem.model_validate(prob_dict)
    config = OrchestrationConfig(max_strategies=2, max_candidates_per_strategy=2)
    return custom_prob, config


def get_golden_realization_failure_scenario() -> tuple[DesignProblem, OrchestrationConfig]:
    """Scenario 9: Severe spatial infeasibility (overcrowded 10x10 ft lot with large program)."""
    spaces = [
        SpaceRequirement(id="lr-1", room=RoomIntent(room_type=RoomCategory.LIVING, min_area_sqft=200)),
        SpaceRequirement(id="br-1", room=RoomIntent(room_type=RoomCategory.BEDROOM, min_area_sqft=150)),
        SpaceRequirement(id="kt-1", room=RoomIntent(room_type=RoomCategory.KITCHEN, min_area_sqft=80)),
        SpaceRequirement(id="ba-1", room=RoomIntent(room_type=RoomCategory.BATHROOM, min_area_sqft=40)),
    ]
    prob = DesignProblem(
        id="golden-prob-infeasible-lot",
        version=1,
        site=SiteDefinition(plot_width=10.0, plot_depth=10.0, floors=1),
        spaces=spaces,
    )
    config = OrchestrationConfig(
        max_strategies=1,
        max_candidates_per_strategy=1,
        phase1_prune_threshold=0.0,
        enable_realization=True,
    )
    return prob, config


def get_golden_phase1_pruning_scenario() -> tuple[DesignProblem, OrchestrationConfig]:
    """Scenario 10: High Phase 1 pruning threshold (0.999) causing pre-realization pruning."""
    prob = get_single_family_problem()
    config = OrchestrationConfig(
        max_strategies=2,
        max_candidates_per_strategy=2,
        phase1_prune_threshold=0.999,
        enable_realization=True,
    )
    return prob, config


def get_golden_mixed_success_failure_scenario() -> tuple[DesignProblem, OrchestrationConfig]:
    """Scenario 11: Mixed success and failure candidates."""
    prob = get_single_family_problem()
    config = OrchestrationConfig(
        max_strategies=3,
        max_candidates_per_strategy=2,
        phase1_prune_threshold=0.10,
        enable_realization=True,
    )
    return prob, config


def get_golden_zero_viable_candidates_scenario() -> tuple[DesignProblem, OrchestrationConfig]:
    """Scenario 12: Zero viable candidates resulting in clean empty selection."""
    prob = get_single_family_problem()
    config = OrchestrationConfig(
        max_strategies=1,
        max_candidates_per_strategy=1,
        max_selected=0,
        phase1_prune_threshold=1.0,
        enable_realization=True,
    )
    return prob, config
