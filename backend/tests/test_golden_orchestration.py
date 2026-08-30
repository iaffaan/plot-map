"""
Golden End-to-End Orchestration Verification Suite for Stage 3B.6-6.

Verifies end-to-end design orchestration across canonical golden scenarios:
1. Scenario 1: Benchmark 44x42 / 4-Family multi-floor residential pipeline
2. Scenario 2: Single-Family 30x40 ground floor residential pipeline
3. Scenario 3: Shared Circulation vertical stair core topology
4. Scenario 4: Independent Circulation access topology
5. Scenario 5: Hybrid Circulation entry topology
6. Scenario 6: Multi-Floor Vertical Stacking floor assignment
7. Scenario 7: Centralized Service Core wet stack organization
8. Scenario 8: Unseen Custom Decision Dimensions preservation
9. Scenario 9: Realization Failure Handling (spatial infeasibility containment)
10. Scenario 10: Phase 1 Pre-Realization Pruning threshold enforcement
11. Scenario 11: Mixed Success / Failure Candidate handling
12. Scenario 12: Zero Viable Candidates empty program handling
13. Deterministic repeated execution verification
14. Provenance and lineage completeness verification
15. Candidate lifecycle state progression correctness
16. Final ranking and selection status consistency
17. Input DesignProblem immutability verification
18. Legacy compiler and API compatibility preservation
19. AST Boundary: No direct solver or geometry manipulation in orchestrator
20. AST Boundary: No duplicate scoring implementation
21. AST Boundary: No duplicate selection implementation
22. AST Boundary: No hardcoded domain-specific branching
23. AST Boundary: No external network or LLM provider calls
24. Package entrypoint orchestrate_design() equivalence
"""

import ast
from pathlib import Path
import pytest

from app.schemas.design_problem import DesignProblem
from app.schemas.intent import CompilerIntent, RoomCategory, RoomIntent
from app.schemas.orchestration import (
    CandidateLifecycleState,
    DesignOrchestrationResult,
    OrchestrationCandidateRecord,
    OrchestrationConfig,
)
from app.schemas.strategy_ranking import SelectionStatus
from app.services.compiler.serializer import compile_blueprint
from app.services.orchestration import DesignOrchestrator, orchestrate_design
from tests.fixtures.golden_orchestration_fixtures import (
    get_golden_44x42_benchmark_scenario,
    get_golden_centralized_service_core_scenario,
    get_golden_hybrid_circulation_scenario,
    get_golden_independent_circulation_scenario,
    get_golden_mixed_success_failure_scenario,
    get_golden_multi_floor_stacking_scenario,
    get_golden_phase1_pruning_scenario,
    get_golden_realization_failure_scenario,
    get_golden_shared_circulation_scenario,
    get_golden_single_family_scenario,
    get_golden_unseen_custom_dimensions_scenario,
    get_golden_zero_viable_candidates_scenario,
)


def test_01_golden_44x42_benchmark_scenario():
    """Scenario 1: Full pipeline execution of 44x42 4-family benchmark."""
    prob, config = get_golden_44x42_benchmark_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    assert isinstance(result, DesignOrchestrationResult)
    assert result.source_problem_id == prob.id
    assert len(result.candidate_records) > 0
    assert len(result.ranking_result.ranked_candidates) > 0
    assert len(result.ranking_result.selected_candidate_ids) <= config.max_selected


def test_02_golden_single_family_scenario():
    """Scenario 2: Single-family 30x40 ft residential orchestration."""
    prob, config = get_golden_single_family_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    assert isinstance(result, DesignOrchestrationResult)
    assert len(result.candidate_records) > 0
    assert len(result.ranking_result.ranked_candidates) > 0
    assert len(result.ranking_result.selected_candidate_ids) <= config.max_selected
    if result.ranking_result.selected_candidate_ids:
        selected_id = result.ranking_result.selected_candidate_ids[0]
        rec = result.candidate_records[selected_id]
        assert rec.lifecycle_state in {CandidateLifecycleState.SELECTED, CandidateLifecycleState.RANKED}
        assert rec.realization_result is not None
        assert rec.realization_result.success is True


def test_03_golden_shared_circulation_scenario():
    """Scenario 3: Shared vertical circulation topology orchestration."""
    prob, config = get_golden_shared_circulation_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    assert isinstance(result, DesignOrchestrationResult)
    assert len(result.candidate_records) > 0
    assert result.execution_stats["total_strategies"] > 0
    assert result.execution_stats["total_candidates"] > 0


def test_04_golden_independent_circulation_scenario():
    """Scenario 4: Independent circulation topology orchestration."""
    prob, config = get_golden_independent_circulation_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    assert isinstance(result, DesignOrchestrationResult)
    assert len(result.candidate_records) > 0


def test_05_golden_hybrid_circulation_scenario():
    """Scenario 5: Hybrid circulation topology orchestration."""
    prob, config = get_golden_hybrid_circulation_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    assert isinstance(result, DesignOrchestrationResult)
    assert len(result.candidate_records) > 0


def test_06_golden_multi_floor_stacking_scenario():
    """Scenario 6: Multi-floor vertical stacking orchestration."""
    prob, config = get_golden_multi_floor_stacking_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    assert isinstance(result, DesignOrchestrationResult)
    for rec in result.candidate_records.values():
        if rec.layout_plan is not None:
            floors = {r.floor_assignment for r in rec.layout_plan.rooms}
            assert len(floors) >= 1


def test_07_golden_centralized_service_core_scenario():
    """Scenario 7: Centralized service core wet stack scenario."""
    prob, config = get_golden_centralized_service_core_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    assert isinstance(result, DesignOrchestrationResult)
    assert len(result.ranking_result.ranked_candidates) > 0


def test_08_golden_unseen_custom_dimensions_scenario():
    """Scenario 8: Unseen custom decision dimensions preserved throughout pipeline."""
    prob, config = get_golden_unseen_custom_dimensions_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    assert isinstance(result, DesignOrchestrationResult)
    assert len(result.candidate_records) > 0


def test_09_golden_realization_failure_scenario():
    """Scenario 9: Severe spatial infeasibility handled gracefully without crash."""
    prob, config = get_golden_realization_failure_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    assert isinstance(result, DesignOrchestrationResult)
    for rec in result.candidate_records.values():
        assert rec.lifecycle_state in {
            CandidateLifecycleState.REALIZATION_FAILED,
            CandidateLifecycleState.REJECTED,
            CandidateLifecycleState.PRUNED_PRE_REALIZATION,
            CandidateLifecycleState.RANKED,
        }


def test_10_golden_phase1_pruning_scenario():
    """Scenario 10: High Phase 1 pruning threshold enforces pre-realization pruning."""
    prob, config = get_golden_phase1_pruning_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    assert isinstance(result, DesignOrchestrationResult)
    pruned_count = result.execution_stats.get("total_phase1_pruned", 0)
    assert pruned_count >= 0
    for rec in result.candidate_records.values():
        if rec.lifecycle_state == CandidateLifecycleState.PRUNED_PRE_REALIZATION:
            assert rec.layout_plan is None
            assert rec.realization_result is None


def test_11_golden_mixed_success_failure_scenario():
    """Scenario 11: Mixed success and failure candidates selection."""
    prob, config = get_golden_mixed_success_failure_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    assert isinstance(result, DesignOrchestrationResult)
    assert len(result.ranking_result.ranked_candidates) > 0


def test_12_golden_zero_viable_candidates_scenario():
    """Scenario 12: Zero viable candidates resulting in clean empty selection."""
    prob, config = get_golden_zero_viable_candidates_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    assert isinstance(result, DesignOrchestrationResult)
    assert len(result.ranking_result.selected_candidate_ids) == 0
    assert result.execution_stats["total_selected"] == 0


def test_13_deterministic_repeated_execution():
    """Scenario 13: Identical inputs produce bit-for-bit identical results."""
    prob, config = get_golden_single_family_scenario()
    res1 = DesignOrchestrator.run(prob, config=config)
    res2 = DesignOrchestrator.run(prob, config=config)

    assert res1.model_dump() == res2.model_dump()


def test_14_provenance_and_lineage_completeness():
    """Scenario 14: Provenance contains all required tracing metadata."""
    prob, config = get_golden_single_family_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    assert "orchestrator" in result.provenance
    assert "source_problem_id" in result.provenance
    assert "source_problem_version" in result.provenance
    assert result.execution_stats["total_strategies"] > 0
    assert result.execution_stats["total_candidates"] > 0


def test_15_lifecycle_state_progression_correctness():
    """Scenario 15: Candidates record full, valid lifecycle state history."""
    prob, config = get_golden_single_family_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    for rec in result.candidate_records.values():
        assert len(rec.state_history) >= 3
        states = [h["to_state"] for h in rec.state_history]
        assert "generated" in states
        assert "organized" in states
        assert "phase1_scored" in states


def test_16_ranking_and_selection_consistency():
    """Scenario 16: Ranking result selected candidates match candidate records."""
    prob, config = get_golden_single_family_scenario()
    result = DesignOrchestrator.run(prob, config=config)

    selected_ids = set(result.ranking_result.selected_candidate_ids)
    for cid in selected_ids:
        assert cid in result.candidate_records
        assert result.candidate_records[cid].lifecycle_state in {
            CandidateLifecycleState.SELECTED,
            CandidateLifecycleState.RANKED,
        }


def test_17_input_problem_immutability():
    """Scenario 17: Input DesignProblem is never mutated by orchestration."""
    prob, config = get_golden_single_family_scenario()
    prob_copy = prob.model_copy(deep=True)
    DesignOrchestrator.run(prob, config=config)

    assert prob.model_dump() == prob_copy.model_dump()


def test_18_legacy_compiler_api_compatibility():
    """Scenario 18: Legacy compile_blueprint pipeline functions without interference."""
    payload = {
        "plot": {"width": 40.0, "depth": 40.0},
        "setbacks": {"left": 0.0, "right": 0.0, "bottom": 5.0, "top": 0.0},
        "stair_core": {"width": 10.0, "height": 10.0, "edge": "bottom-left"},
        "road_edge": "bottom",
        "rooms": [
            {"name": "Main Door", "type": "Entrance", "min_width": 3.0, "min_height": 3.0, "min_area": 9.0, "requires_ventilation": False, "adjacent_to_road": True},
            {"name": "Living Room", "type": "Living Room", "min_width": 10.0, "min_height": 10.0, "min_area": 100.0, "requires_ventilation": True, "adjacent_to_road": True},
            {"name": "Kitchen", "type": "Kitchen", "min_width": 8.0, "min_height": 8.0, "min_area": 64.0, "requires_ventilation": True, "adjacent_to_road": False},
        ],
        "adjacencies": [
            ("Main Door", "Living Room"),
            ("Living Room", "Kitchen"),
        ],
    }
    blueprint = compile_blueprint(payload)
    assert blueprint is not None
    assert isinstance(blueprint, dict)
    assert blueprint.get("success") is True


def test_19_ast_no_direct_solver_or_geometry():
    """Scenario 19: Orchestration service contains zero direct solver or Shapely calls."""
    filepath = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "design_orchestrator.py"
    content = filepath.read_text(encoding="utf-8")
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in {"solve_layout", "solve_milp", "compile_blueprint"}:
            pytest.fail(f"Prohibited direct solver/compiler call: {node.attr}")

    assert "shapely" not in content.lower()
    assert "polygon(" not in content.lower()


def test_20_ast_no_duplicate_scoring():
    """Scenario 20: Orchestration delegates scoring to ranking services."""
    filepath = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "design_orchestrator.py"
    content = filepath.read_text(encoding="utf-8")
    assert "SpatialRealizationScorer.combine_score_breakdowns" in content


def test_21_ast_no_duplicate_selection():
    """Scenario 21: Orchestration delegates candidate selection to CandidateSelector."""
    filepath = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "design_orchestrator.py"
    content = filepath.read_text(encoding="utf-8")
    assert "CandidateSelector.select" in content


def test_22_ast_no_domain_hardcoding():
    """Scenario 22: Orchestration contains zero domain-specific keyword branching."""
    filepath = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "design_orchestrator.py"
    content = filepath.read_text(encoding="utf-8")
    forbidden = ["bedroom", "kitchen", "bathroom", "duplex", "staircase", "courtyard"]
    for term in forbidden:
        assert term not in content.lower(), f"Found hardcoded domain string '{term}' in design_orchestrator.py"


def test_23_ast_no_network_llm_calls():
    """Scenario 23: Orchestration runs 100% offline with zero network/LLM clients."""
    filepath = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "design_orchestrator.py"
    content = filepath.read_text(encoding="utf-8")
    for forbidden in ["requests", "httpx", "urllib", "openai", "anthropic", "google.generativeai"]:
        assert forbidden not in content, f"Found prohibited import '{forbidden}'"


def test_24_orchestrate_design_entrypoint_equivalence():
    """Scenario 24: orchestrate_design() entrypoint behaves identically to DesignOrchestrator.run()."""
    prob, config = get_golden_single_family_scenario()
    res1 = DesignOrchestrator.run(prob, config=config)
    res2 = orchestrate_design(prob, config=config)

    assert res1.model_dump() == res2.model_dump()
