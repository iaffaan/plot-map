"""
Unit Test Suite for SpatialPhase2Orchestrator (Stage 3B.6-4).

Verifies 2D spatial layout realization, Phase 2 scoring integration, failure isolation,
boundary reusability via monkeypatching, immutability, determinism, and static AST isolation.
"""

import ast
import json
from pathlib import Path
import pytest

from app.schemas.architectural_analysis import DecisionRecord, DecisionStatus
from app.schemas.design_candidate import DesignCandidate
from app.schemas.design_problem import DesignProblem, SiteDefinition, SpaceRequirement
from app.schemas.intent import RoomCategory, RoomIntent
from app.schemas.orchestration import CandidateLifecycleState, OrchestrationConfig
from app.schemas.spatial_realization import RealizationResult, RealizationStatus, SpatialLayoutPlan
from app.schemas.strategy_preference import PreferenceCatalog
from app.services.analysis.candidate_organizer import organize_candidate
from app.services.analysis.catalog_loader import get_catalog_organization_rules
from app.services.analysis.spatial_adapter import CandidateToLayoutAdapter
from app.services.orchestration.lifecycle_manager import CandidateLifecycleManager
from app.services.orchestration.spatial_phase2 import SpatialPhase2Orchestrator
from app.services.ranking.spatial_realization_scorer import SpatialRealizationScorer
from app.services.realization.compiler_bridge import SpatialCompilerBridge
from tests.fixtures.golden_organization_fixtures import (
    get_benchmark_44x42_candidate,
    get_benchmark_44x42_problem,
    get_single_family_candidate,
    get_single_family_problem,
)


def _sample_problem(problem_id: str = "prob-44x42-benchmark") -> DesignProblem:
    return get_benchmark_44x42_problem()


def _sample_candidate(candidate_id: str = "cand-44x42") -> DesignCandidate:
    prob = get_benchmark_44x42_problem()
    raw_cand = get_benchmark_44x42_candidate(prob)
    rules = get_catalog_organization_rules()
    organized = organize_candidate(raw_cand, rules, problem=prob)
    if candidate_id != organized.id:
        return organized.model_copy(update={"id": candidate_id})
    return organized








def test_01_successful_spatial_realization():
    problem = _sample_problem()
    cand = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()
    mgr.register_candidate(cand)
    mgr.transition_state(cand.id, CandidateLifecycleState.ORGANIZED)
    mgr.transition_state(cand.id, CandidateLifecycleState.PHASE1_SCORED)

    result = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)

    assert result.total_candidates_processed == 1
    assert len(result.successful_realization_ids) == 1
    assert result.successful_realization_ids[0] == "c1"



def test_02_plan_adaptation():
    problem = _sample_problem()
    cand = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    result = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)

    rec = result.candidate_records["c1"]
    assert rec.layout_plan is not None
    assert rec.layout_plan.source_candidate_id == "c1"


def test_03_compiler_bridge_invocation():
    problem = _sample_problem()
    cand = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    result = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)


    rec = result.candidate_records["c1"]
    assert rec.realization_result is not None
    assert rec.realization_result.status == RealizationStatus.SUCCESS


def test_04_solver_boundary_reuse(monkeypatch):
    problem = _sample_problem()
    cand = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    called = False
    orig_realize = SpatialCompilerBridge.realize_layout

    def mock_realize(*args, **kwargs):
        nonlocal called
        called = True
        return orig_realize(*args, **kwargs)

    monkeypatch.setattr(SpatialCompilerBridge, "realize_layout", mock_realize)

    SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)
    assert called is True


def test_05_successful_phase2_scoring():
    problem = _sample_problem()
    cand = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    result = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)

    rec = result.candidate_records["c1"]
    assert rec.phase2_score is not None
    assert rec.phase2_score.total_score >= 0.0


def test_06_phase2_score_preservation():
    problem = _sample_problem()
    cand = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    result = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)

    rec = result.candidate_records["c1"]
    assert len(rec.phase2_score.criteria) > 0


def test_07_successful_lifecycle_transitions():
    problem = _sample_problem()
    cand = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)

    history = mgr.get_history("c1")
    states = [h["to_state"] for h in history]
    assert "plan_adapted" in states
    assert "realized" in states
    assert "phase2_scored" in states


def test_08_spatial_infeasibility_handling(monkeypatch):
    problem = _sample_problem()
    cand = _sample_candidate("c-infeasible")
    mgr = CandidateLifecycleManager()

    def mock_infeasible(*args, **kwargs):
        return RealizationResult(
            status=RealizationStatus.SPATIALLY_INFEASIBLE,
            success=False,
            candidate_id="c-infeasible",
            error_message="Spatial infeasibility detected",
        )

    monkeypatch.setattr(SpatialCompilerBridge, "realize_layout", mock_infeasible)

    result = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)

    assert "c-infeasible" in result.failed_realization_ids
    rec = result.candidate_records["c-infeasible"]
    assert rec.lifecycle_state == CandidateLifecycleState.REALIZATION_FAILED


def test_09_solver_timeout_handling(monkeypatch):
    problem = _sample_problem()
    cand = _sample_candidate("c-timeout")
    mgr = CandidateLifecycleManager()

    def mock_timeout(*args, **kwargs):
        return RealizationResult(
            status=RealizationStatus.SOLVER_TIMEOUT,
            success=False,
            candidate_id="c-timeout",
            error_message="Solver execution timed out after 5s",
        )

    monkeypatch.setattr(SpatialCompilerBridge, "realize_layout", mock_timeout)

    result = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)

    assert "c-timeout" in result.failed_realization_ids
    rec = result.candidate_records["c-timeout"]
    assert rec.lifecycle_state == CandidateLifecycleState.REALIZATION_FAILED


def test_10_solver_error_handling(monkeypatch):
    problem = _sample_problem()
    cand = _sample_candidate("c-err")
    mgr = CandidateLifecycleManager()

    def mock_err(*args, **kwargs):
        return RealizationResult(
            status=RealizationStatus.SOLVER_ERROR,
            success=False,
            candidate_id="c-err",
            error_message="Internal solver error",
        )

    monkeypatch.setattr(SpatialCompilerBridge, "realize_layout", mock_err)

    result = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)

    assert "c-err" in result.failed_realization_ids


def test_11_unsupported_specification_handling(monkeypatch):
    problem = _sample_problem()
    cand = _sample_candidate("c-unsupported")
    mgr = CandidateLifecycleManager()

    def mock_unsupported(*args, **kwargs):
        return RealizationResult(
            status=RealizationStatus.UNSUPPORTED_SPEC,
            success=False,
            candidate_id="c-unsupported",
            error_message="Unsupported specification",
        )

    monkeypatch.setattr(SpatialCompilerBridge, "realize_layout", mock_unsupported)

    result = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)

    assert "c-unsupported" in result.failed_realization_ids


def test_12_invalid_candidate_handling(monkeypatch):
    problem = _sample_problem()
    cand = _sample_candidate("c-invalid")
    mgr = CandidateLifecycleManager()

    def mock_invalid(*args, **kwargs):
        return RealizationResult(
            status=RealizationStatus.INVALID_CANDIDATE,
            success=False,
            candidate_id="c-invalid",
            error_message="Invalid candidate structure",
        )

    monkeypatch.setattr(SpatialCompilerBridge, "realize_layout", mock_invalid)

    result = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)

    assert "c-invalid" in result.failed_realization_ids


def test_13_failure_isolation(monkeypatch):
    problem = _sample_problem()
    c_good = _sample_candidate("c-good")
    c_bad = _sample_candidate("c-bad")
    mgr = CandidateLifecycleManager()

    orig_realize = SpatialCompilerBridge.realize_layout

    def mock_mixed(plan, *args, **kwargs):
        if plan.source_candidate_id == "c-bad":
            return RealizationResult(
                status=RealizationStatus.SPATIALLY_INFEASIBLE,
                success=False,
                candidate_id="c-bad",
                error_message="Infeasible layout",
            )
        return orig_realize(plan, *args, **kwargs)

    monkeypatch.setattr(SpatialCompilerBridge, "realize_layout", mock_mixed)

    result = SpatialPhase2Orchestrator.realize_and_score([c_good, c_bad], problem, mgr)

    assert "c-good" in result.successful_realization_ids
    assert "c-bad" in result.failed_realization_ids


def test_14_failed_realization_result_preservation(monkeypatch):
    problem = _sample_problem()
    cand = _sample_candidate("c-bad-res")
    mgr = CandidateLifecycleManager()

    def mock_fail(*args, **kwargs):
        return RealizationResult(
            status=RealizationStatus.SOLVER_ERROR,
            success=False,
            candidate_id="c-bad-res",
            error_message="Fail message",
        )

    monkeypatch.setattr(SpatialCompilerBridge, "realize_layout", mock_fail)

    result = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)

    rec = result.candidate_records["c-bad-res"]
    assert rec.realization_result is not None
    assert rec.realization_result.error_message == "Fail message"


def test_15_provenance_preservation():
    problem = _sample_problem()
    cand = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    result = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)

    prov = result.provenance
    assert prov["orchestrator_phase"] == "SpatialPhase2Orchestrator"
    assert prov["source_problem_id"] == problem.id
    assert prov["total_processed"] == 1


def test_16_candidate_immutability():
    problem = _sample_problem()
    cand = _sample_candidate("c-immut")
    orig_dump = cand.model_dump_json()
    mgr = CandidateLifecycleManager()

    SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)
    assert cand.model_dump_json() == orig_dump


def test_17_realization_immutability(monkeypatch):
    problem = _sample_problem()
    cand = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    res = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)
    rec = res.candidate_records["c1"]
    realization = rec.realization_result

    orig_dump = realization.model_dump_json()
    # Scoring step must not mutate realization
    SpatialRealizationScorer.score_realization(cand, problem, realization)
    assert realization.model_dump_json() == orig_dump


def test_18_deterministic_ordering():
    problem = _sample_problem()
    c1 = _sample_candidate("c1")
    c2 = _sample_candidate("c2")
    mgr = CandidateLifecycleManager()

    res = SpatialPhase2Orchestrator.realize_and_score([c1, c2], problem, mgr)
    keys = list(res.candidate_records.keys())
    assert keys == ["c1", "c2"]


def test_19_repeated_execution_determinism():
    problem = _sample_problem()
    cand = _sample_candidate("c1")

    mgr1 = CandidateLifecycleManager()
    res1 = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr1)

    mgr2 = CandidateLifecycleManager()
    res2 = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr2)

    assert res1.successful_realization_ids == res2.successful_realization_ids
    assert res1.failed_realization_ids == res2.failed_realization_ids
    assert res1.candidate_records["c1"].phase2_score.model_dump() == res2.candidate_records["c1"].phase2_score.model_dump()
    assert res1.candidate_records["c1"].realization_result.success == res2.candidate_records["c1"].realization_result.success
    assert mgr1.get_record("c1").lifecycle_state == mgr2.get_record("c1").lifecycle_state


def test_20_empty_candidate_input():
    problem = _sample_problem()
    mgr = CandidateLifecycleManager()

    res = SpatialPhase2Orchestrator.realize_and_score([], problem, mgr)
    assert res.total_candidates_processed == 0
    assert len(res.successful_realization_ids) == 0


def test_21_duplicate_candidate_ids():
    problem = _sample_problem()
    cand = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    res = SpatialPhase2Orchestrator.realize_and_score([cand, cand], problem, mgr)
    assert res.total_candidates_processed == 1


def test_22_pruned_candidates_never_realized(monkeypatch):
    problem = _sample_problem()
    cand = _sample_candidate("c-pruned")
    mgr = CandidateLifecycleManager()

    mgr.register_candidate(cand)
    mgr.transition_state(cand.id, CandidateLifecycleState.ORGANIZED)
    mgr.transition_state(cand.id, CandidateLifecycleState.PHASE1_SCORED)
    mgr.transition_state(cand.id, CandidateLifecycleState.PRUNED_PRE_REALIZATION, reason="Phase 1 low score")

    called = False

    def mock_realize(*args, **kwargs):
        nonlocal called
        called = True
        raise RuntimeError("Should never be called for pruned candidate")

    monkeypatch.setattr(SpatialCompilerBridge, "realize_layout", mock_realize)

    res = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)

    assert called is False
    assert "c-pruned" in res.skipped_pruned_ids


def test_23_enable_realization_false(monkeypatch):
    problem = _sample_problem()
    cand = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    called = False

    def mock_realize(*args, **kwargs):
        nonlocal called
        called = True
        return None

    monkeypatch.setattr(SpatialCompilerBridge, "realize_layout", mock_realize)

    config = OrchestrationConfig(enable_realization=False)
    res = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr, config=config)

    assert called is False
    assert res.realization_enabled is False


def test_24_solver_time_limit_forwarding():
    problem = _sample_problem()
    cand = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    config = OrchestrationConfig(solver_time_limit_sec=12)
    res = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr, config=config)

    assert res.provenance["solver_time_limit_sec"] == 12


def test_25_grid_snap_forwarding():
    problem = _sample_problem()
    cand = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    config = OrchestrationConfig(grid_snap=0.25)
    res = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr, config=config)

    assert res.provenance["grid_snap"] == 0.25



def test_26_custom_unseen_dimensions():
    problem = _sample_problem()
    cand = _sample_candidate("c-custom-dim")
    cand.selected_decisions.append(
        DecisionRecord(
            id="dec-custom",
            dimension="custom_unseen_dimension_z",
            subject="building",
            value="custom_value",
            status=DecisionStatus.FIXED,
        )
    )
    mgr = CandidateLifecycleManager()

    res = SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)
    assert res.total_candidates_processed == 1


def test_27_no_duplicate_solver_implementation(monkeypatch):
    problem = _sample_problem()
    cand = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    called_bridge = False
    orig_realize = SpatialCompilerBridge.realize_layout

    def mock_realize(*args, **kwargs):
        nonlocal called_bridge
        called_bridge = True
        return orig_realize(*args, **kwargs)

    monkeypatch.setattr(SpatialCompilerBridge, "realize_layout", mock_realize)

    SpatialPhase2Orchestrator.realize_and_score([cand], problem, mgr)
    assert called_bridge is True


def test_28_no_duplicate_geometry_implementation():
    target_file = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "spatial_phase2.py"
    content = target_file.read_text(encoding="utf-8")
    assert "shapely" not in content.lower()
    assert "polygon" not in content.lower()


def test_29_no_direct_shapely_pulp_cbc_usage():
    target_file = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "spatial_phase2.py"
    content = target_file.read_text(encoding="utf-8")
    assert "pulp" not in content.lower()
    assert "cbc" not in content.lower()


def test_30_no_hardcoded_domain_specific_branching():
    target_file = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "spatial_phase2.py"
    content = target_file.read_text(encoding="utf-8")
    assert 'dimension == "circulation_topology"' not in content
    assert 'criterion_id == "program_usability"' not in content


def test_31_no_final_candidate_selector_invocation():
    target_file = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "spatial_phase2.py"
    content = target_file.read_text(encoding="utf-8")
    assert "CandidateSelector" not in content


def test_32_no_design_orchestrator_implementation():
    target_file = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "spatial_phase2.py"
    content = target_file.read_text(encoding="utf-8")
    assert "DesignOrchestrator" not in content


def test_33_ast_boundary_check():
    target_file = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "spatial_phase2.py"
    content = target_file.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(target_file))

    prohibited_modules = {
        "shapely", "pulp", "cbc", "solver", "compiler",
        "requests", "httpx", "google", "gemini",
        "strategy_generator", "candidate_generator"
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0].lower() not in prohibited_modules
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert node.module.split(".")[0].lower() not in prohibited_modules
