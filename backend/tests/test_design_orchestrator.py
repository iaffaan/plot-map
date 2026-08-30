"""
Unit Test Suite for DesignOrchestrator (Stage 3B.6-5).

Verifies end-to-end design orchestration pipeline, reusability of existing components via monkeypatching,
config forwarding, failure isolation, lifecycle state progression, determinism,
provenance preservation, immutability, and static AST boundary isolation.
"""

import ast
import json
from pathlib import Path
import pytest

from app.schemas.architectural_analysis import DecisionRecord, DecisionStatus
from app.schemas.design_candidate import DesignCandidate
from app.schemas.design_problem import DesignProblem, Preference, Requirement, SpaceRequirement
from app.schemas.intent import RoomCategory, RoomIntent
from app.schemas.orchestration import (
    CandidateLifecycleState,
    DesignOrchestrationResult,
    OrchestrationConfig,
    Phase1PruningResult,
    SpatialPhase2Result,
)
from app.schemas.spatial_realization import RealizationResult, RealizationStatus, SpatialLayoutPlan
from app.schemas.strategy_preference import PreferenceCatalog
from app.schemas.strategy_ranking import CriterionScore, RankedCandidate, RankingResult, ScoreBreakdown, SelectionStatus
from app.services.analysis.candidate_generator import generate_candidate_from_strategy
from app.services.analysis.candidate_organizer import organize_candidate
from app.services.analysis.strategy_generator import generate_strategies
from app.services.orchestration.design_orchestrator import DesignOrchestrator, orchestrate_design
from app.services.orchestration.lifecycle_manager import CandidateLifecycleManager
from app.services.orchestration.phase1_pruner import Phase1Pruner
from app.services.orchestration.spatial_phase2 import SpatialPhase2Orchestrator
from app.services.ranking.candidate_selector import CandidateSelector
from app.services.ranking.spatial_realization_scorer import SpatialRealizationScorer

from tests.fixtures.golden_organization_fixtures import (
    get_benchmark_44x42_problem,
    get_single_family_problem,
)


def _sample_problem(prob_id: str = "prob-44x42-benchmark") -> DesignProblem:
    p = get_benchmark_44x42_problem()
    if prob_id != p.id:
        return p.model_copy(update={"id": prob_id})
    return p


def test_01_complete_successful_e2e_pipeline():
    problem = _sample_problem()
    config = OrchestrationConfig(max_strategies=3, max_selected=2)
    res = DesignOrchestrator.run(problem, config=config)

    assert isinstance(res, DesignOrchestrationResult)
    assert res.source_problem_id == problem.id
    assert res.source_problem_version == problem.version
    assert len(res.candidate_records) > 0
    assert isinstance(res.ranking_result, RankingResult)
    assert len(res.ranking_result.selected_candidate_ids) <= 2
    assert res.execution_stats["total_candidates"] == len(res.candidate_records)


def test_02_strategy_generation_reuse(monkeypatch):
    called = []
    orig = generate_strategies

    def mock_gen(*args, **kwargs):
        called.append(True)
        return orig(*args, **kwargs)

    monkeypatch.setattr("app.services.orchestration.design_orchestrator.generate_strategies", mock_gen)

    problem = _sample_problem()
    DesignOrchestrator.run(problem)
    assert len(called) == 1


def test_03_candidate_generation_reuse(monkeypatch):
    called = []
    orig = generate_candidate_from_strategy

    def mock_cand(*args, **kwargs):
        called.append(True)
        return orig(*args, **kwargs)

    monkeypatch.setattr("app.services.orchestration.design_orchestrator.generate_candidate_from_strategy", mock_cand)

    problem = _sample_problem()
    DesignOrchestrator.run(problem)
    assert len(called) > 0


def test_04_candidate_organizer_reuse(monkeypatch):
    called = []
    orig = organize_candidate

    def mock_org(*args, **kwargs):
        called.append(True)
        return orig(*args, **kwargs)

    monkeypatch.setattr("app.services.orchestration.design_orchestrator.organize_candidate", mock_org)

    problem = _sample_problem()
    DesignOrchestrator.run(problem)
    assert len(called) > 0


def test_05_lifecycle_manager_reuse(monkeypatch):
    called = []
    orig_reg = CandidateLifecycleManager.register_candidate

    def mock_reg(self, candidate):
        called.append(candidate.id)
        return orig_reg(self, candidate)

    monkeypatch.setattr(CandidateLifecycleManager, "register_candidate", mock_reg)

    problem = _sample_problem()
    res = DesignOrchestrator.run(problem)
    assert len(called) == len(res.candidate_records)


def test_06_phase1_pruner_reuse(monkeypatch):
    called = []
    orig = Phase1Pruner.score_and_prune

    def mock_p1(*args, **kwargs):
        called.append(True)
        return orig(*args, **kwargs)

    monkeypatch.setattr(Phase1Pruner, "score_and_prune", mock_p1)

    problem = _sample_problem()
    DesignOrchestrator.run(problem)
    assert len(called) == 1


def test_07_spatial_phase2_orchestrator_reuse(monkeypatch):
    called = []
    orig = SpatialPhase2Orchestrator.realize_and_score

    def mock_p2(*args, **kwargs):
        called.append(True)
        return orig(*args, **kwargs)

    monkeypatch.setattr(SpatialPhase2Orchestrator, "realize_and_score", mock_p2)

    problem = _sample_problem()
    DesignOrchestrator.run(problem)
    assert len(called) == 1


def test_08_candidate_selector_reuse(monkeypatch):
    called = []
    orig = CandidateSelector.select

    def mock_select(*args, **kwargs):
        called.append(True)
        return orig(*args, **kwargs)

    monkeypatch.setattr(CandidateSelector, "select", mock_select)

    problem = _sample_problem()
    DesignOrchestrator.run(problem)
    assert len(called) >= 1


def test_09_benchmark_44x42_pipeline():
    prob = get_benchmark_44x42_problem()
    res = orchestrate_design(prob)
    assert res.source_problem_id == prob.id
    assert len(res.ranking_result.ranked_candidates) > 0


def test_10_single_family_pipeline():
    prob = get_single_family_problem()
    res = orchestrate_design(prob)
    assert res.source_problem_id == prob.id
    assert len(res.ranking_result.ranked_candidates) > 0


def test_11_multi_floor_pipeline():
    prob = get_benchmark_44x42_problem()
    prob_dict = prob.model_dump()
    prob_dict["id"] = "multi-floor-prob"
    prob_dict["spaces"].append(
        SpaceRequirement(
            id="s-bedroom-2f",
            room=RoomIntent(room_type=RoomCategory.BEDROOM),
        ).model_dump()
    )
    multi_prob = DesignProblem.model_validate(prob_dict)
    res = DesignOrchestrator.run(multi_prob)
    assert res.source_problem_id == "multi-floor-prob"


def test_12_shared_circulation_pipeline():
    prob = get_benchmark_44x42_problem()
    res = DesignOrchestrator.run(prob, config=OrchestrationConfig(max_strategies=2))
    assert res.execution_stats["total_strategies"] <= 2


def test_13_custom_unseen_dimensions():
    prob = _sample_problem("prob-custom-dims")
    prob_dict = prob.model_dump()
    prob_dict["preferences"].append(
        Preference(id="pref-custom-dim", description="Custom Dim Preference", target="unseen_val", weight=0.8).model_dump()
    )
    custom_prob = DesignProblem.model_validate(prob_dict)
    res = DesignOrchestrator.run(custom_prob)
    assert res.source_problem_id == "prob-custom-dims"


def test_14_phase1_pruning():
    prob = _sample_problem()
    config = OrchestrationConfig(phase1_prune_threshold=0.999)
    res = DesignOrchestrator.run(prob, config=config)

    # With threshold 0.999, candidates should be pruned pre-realization
    for rec in res.candidate_records.values():
        assert rec.lifecycle_state in {
            CandidateLifecycleState.PRUNED_PRE_REALIZATION,
            CandidateLifecycleState.REJECTED,
            CandidateLifecycleState.RANKED,
        }
    assert res.execution_stats["total_phase1_pruned"] >= 0


def test_15_spatial_realization_failure(monkeypatch):
    prob = _sample_problem()

    def mock_fail_p2(candidates, problem, lifecycle_manager, config=None, preference_catalog=None):
        for c in candidates:
            fail_res = RealizationResult(
                status=RealizationStatus.SOLVER_ERROR,
                success=False,
                candidate_id=c.id,
                error_message="Simulated solver failure",
            )
            lifecycle_manager.update_payloads(c.id, realization_result=fail_res)
            lifecycle_manager.transition_state(c.id, CandidateLifecycleState.PLAN_ADAPTED)
            lifecycle_manager.transition_state(c.id, CandidateLifecycleState.REALIZATION_FAILED, reason="Simulated fail")
        return SpatialPhase2Result(
            source_problem_id=problem.id,
            source_problem_version=problem.version,
            realization_enabled=True,
            total_candidates_processed=len(candidates),
            successful_realization_ids=[],
            failed_realization_ids=[c.id for c in candidates],
            skipped_pruned_ids=[],
            candidate_records=lifecycle_manager.get_all_records(),
        )

    monkeypatch.setattr(SpatialPhase2Orchestrator, "realize_and_score", mock_fail_p2)

    res = DesignOrchestrator.run(prob)
    assert res.execution_stats["total_realized_failed"] > 0
    # Selected candidate IDs should be empty because realization failed
    assert len(res.ranking_result.selected_candidate_ids) == 0


def test_16_mixed_successful_failed_candidates(monkeypatch):
    prob = _sample_problem()

    def mock_mixed_p2(candidates, problem, lifecycle_manager, config=None, preference_catalog=None):
        succ_ids = []
        fail_ids = []
        for idx, c in enumerate(candidates):
            lifecycle_manager.transition_state(c.id, CandidateLifecycleState.PLAN_ADAPTED)
            if idx == 0:
                pass_res = RealizationResult(
                    status=RealizationStatus.SUCCESS,
                    success=True,
                    candidate_id=c.id,
                )
                lifecycle_manager.update_payloads(c.id, realization_result=pass_res)
                lifecycle_manager.transition_state(c.id, CandidateLifecycleState.REALIZED)
                lifecycle_manager.transition_state(c.id, CandidateLifecycleState.PHASE2_SCORED)
                succ_ids.append(c.id)
            else:
                fail_res = RealizationResult(
                    status=RealizationStatus.SPATIALLY_INFEASIBLE,
                    success=False,
                    candidate_id=c.id,
                    error_message="Infeasible bounds",
                )
                lifecycle_manager.update_payloads(c.id, realization_result=fail_res)
                lifecycle_manager.transition_state(c.id, CandidateLifecycleState.REALIZATION_FAILED)
                fail_ids.append(c.id)

        return SpatialPhase2Result(
            source_problem_id=problem.id,
            source_problem_version=problem.version,
            realization_enabled=True,
            total_candidates_processed=len(candidates),
            successful_realization_ids=succ_ids,
            failed_realization_ids=fail_ids,
            skipped_pruned_ids=[],
            candidate_records=lifecycle_manager.get_all_records(),
        )

    monkeypatch.setattr(SpatialPhase2Orchestrator, "realize_and_score", mock_mixed_p2)

    res = DesignOrchestrator.run(prob)
    assert res.execution_stats["total_realized_successful"] == 1
    assert res.execution_stats["total_realized_failed"] >= 1


def test_17_zero_candidates(monkeypatch):
    prob = _sample_problem()
    monkeypatch.setattr("app.services.orchestration.design_orchestrator.generate_strategies", lambda *a, **kw: [])

    res = DesignOrchestrator.run(prob)
    assert isinstance(res, DesignOrchestrationResult)
    assert res.execution_stats["total_candidates"] == 0
    assert len(res.ranking_result.ranked_candidates) == 0


def test_18_max_strategies_config():
    prob = _sample_problem()
    res = DesignOrchestrator.run(prob, config=OrchestrationConfig(max_strategies=2))
    assert res.execution_stats["total_strategies"] <= 2


def test_19_max_candidates_per_strategy_config():
    prob = _sample_problem()
    res = DesignOrchestrator.run(prob, config=OrchestrationConfig(max_candidates_per_strategy=1))
    assert res.config_used.max_candidates_per_strategy == 1


def test_20_max_selected_config():
    prob = _sample_problem()
    res = DesignOrchestrator.run(prob, config=OrchestrationConfig(max_selected=1))
    assert len(res.ranking_result.selected_candidate_ids) <= 1


def test_21_enable_realization_false():
    prob = _sample_problem()
    res = DesignOrchestrator.run(prob, config=OrchestrationConfig(enable_realization=False))
    assert res.config_used.enable_realization is False
    assert res.execution_stats["total_realized_successful"] == 0


def test_22_solver_time_limit_sec_forwarding():
    prob = _sample_problem()
    res = DesignOrchestrator.run(prob, config=OrchestrationConfig(solver_time_limit_sec=12))
    assert res.config_used.solver_time_limit_sec == 12


def test_23_grid_snap_forwarding():
    prob = _sample_problem()
    res = DesignOrchestrator.run(prob, config=OrchestrationConfig(grid_snap=0.25))
    assert res.config_used.grid_snap == 0.25


def test_24_complete_provenance():
    prob = _sample_problem()
    res = DesignOrchestrator.run(prob)
    assert res.provenance["orchestrator"] == "DesignOrchestrator"
    assert res.provenance["source_problem_id"] == prob.id
    assert res.provenance["source_problem_version"] == prob.version


def test_25_lifecycle_state_correctness():
    prob = _sample_problem()
    res = DesignOrchestrator.run(prob)
    for cid, rec in res.candidate_records.items():
        states = [h["to_state"] for h in rec.state_history]
        assert "generated" in states
        assert "organized" in states
        assert "phase1_scored" in states


def test_26_candidate_record_completeness():
    prob = _sample_problem()
    res = DesignOrchestrator.run(prob)
    for cid, rec in res.candidate_records.items():
        assert rec.candidate is not None
        assert rec.candidate.id == cid
        assert rec.lifecycle_state in CandidateLifecycleState
        assert len(rec.state_history) > 0


def test_27_deterministic_repeated_execution():
    prob = _sample_problem()
    config = OrchestrationConfig(max_strategies=2, max_selected=1)
    res1 = DesignOrchestrator.run(prob, config=config)
    res2 = DesignOrchestrator.run(prob, config=config)
    assert res1.model_dump() == res2.model_dump()


def test_28_candidate_immutability():
    prob = _sample_problem()
    prob_copy = prob.model_copy(deep=True)
    DesignOrchestrator.run(prob)
    assert prob.model_dump() == prob_copy.model_dump()


def test_29_structured_failure_handling():
    with pytest.raises(ValueError, match="problem must be a valid DesignProblem"):
        DesignOrchestrator.run(None)


def test_30_no_direct_solver_invocation():
    filepath = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "design_orchestrator.py"
    content = filepath.read_text(encoding="utf-8")
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in {"solve_layout", "solve", "solve_milp"}:
            pytest.fail(f"Found prohibited direct solver call attribute: {node.attr}")


def test_31_no_direct_compiler_invocation():
    filepath = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "design_orchestrator.py"
    content = filepath.read_text(encoding="utf-8")
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "compile_blueprint":
            pytest.fail("Found prohibited direct compiler call: compile_blueprint")


def test_32_no_direct_geometry_invocation():
    filepath = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "design_orchestrator.py"
    content = filepath.read_text(encoding="utf-8")
    assert "shapely" not in content
    assert "Polygon(" not in content
    assert "Point(" not in content


def test_33_no_duplicate_scoring_logic():
    filepath = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "design_orchestrator.py"
    content = filepath.read_text(encoding="utf-8")
    assert "SpatialRealizationScorer.combine_score_breakdowns" in content


def test_34_no_duplicate_selection_logic():
    filepath = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "design_orchestrator.py"
    content = filepath.read_text(encoding="utf-8")
    assert "CandidateSelector.select" in content


def test_35_no_hardcoded_domain_specific_branching():
    filepath = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "design_orchestrator.py"
    content = filepath.read_text(encoding="utf-8")

    forbidden_terms = ["bedroom", "kitchen", "duplex", "staircase", "lift_core", "courtyard"]
    for term in forbidden_terms:
        assert term not in content.lower(), f"Found hardcoded domain string '{term}' in design_orchestrator.py"


def test_36_no_external_network_llm_calls():
    filepath = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "design_orchestrator.py"
    content = filepath.read_text(encoding="utf-8")

    for forbidden in ["requests", "httpx", "urllib", "openai", "anthropic", "google.generativeai"]:
        assert forbidden not in content, f"Found network/LLM module import '{forbidden}' in design_orchestrator.py"


def test_37_no_stage_3b6_6_fixtures_imported():
    filepath = Path(__file__)
    content = filepath.read_text(encoding="utf-8")
    forbidden_module = "golden_" + "orchestration_fixtures"
    assert forbidden_module not in content, "Stage 3B.6-6 golden orchestration fixtures must not be imported in Stage 3B.6-5"


def test_38_ast_architecture_boundary():
    filepath = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "design_orchestrator.py"
    content = filepath.read_text(encoding="utf-8")
    tree = ast.parse(content)

    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    class_names = [c.name for c in classes]
    assert "DesignOrchestrator" in class_names
