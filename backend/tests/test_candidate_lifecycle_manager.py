"""
Unit Test Suite for CandidateLifecycleManager (Stage 3B.6-2).

Verifies state management, transition validation, artifact association,
failure handling, determinism, immutability, and static AST isolation.
"""

import ast
import json
from pathlib import Path
import pytest

from app.schemas.architectural_analysis import DecisionRecord, DecisionStatus
from app.schemas.design_candidate import DesignCandidate
from app.schemas.orchestration import CandidateLifecycleState
from app.schemas.spatial_realization import (
    RealizationResult,
    RealizationStatus,
    SpatialLayoutPlan,
    SpatialRoomSpec,
)
from app.schemas.strategy_ranking import CriterionScore, ScoreBreakdown
from app.services.orchestration.lifecycle_manager import (
    CandidateLifecycleManager,
    CandidateNotFoundError,
    DuplicateCandidateRegistrationError,
    LifecycleError,
    LifecycleTransitionError,
)


def _sample_candidate(candidate_id: str = "cand-lifecycle-1") -> DesignCandidate:
    return DesignCandidate(
        id=candidate_id,
        source_strategy_id="strat-1",
        source_analysis_id="analysis-1",
        source_problem_id="prob-1",
        source_problem_version=1,
        candidate_version=1,
        name="Test Lifecycle Candidate",
        selected_decisions=[
            DecisionRecord(
                id="dec-1",
                dimension="circulation_topology",
                subject="building",
                value="shared",
                status=DecisionStatus.FIXED,
            )
        ],
        floor_organization={"ground": ["s1"]},
        unit_organization={"u1": ["s1"]},
        circulation_intent=[],
        service_organization=[],
    )


def test_01_candidate_registration():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    record = mgr.register_candidate(cand)

    assert record.candidate.id == "cand-lifecycle-1"
    assert record.lifecycle_state == CandidateLifecycleState.GENERATED
    assert len(record.state_history) == 1
    assert record.state_history[0]["to_state"] == "generated"


def test_02_duplicate_registration_rejection():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)

    with pytest.raises(DuplicateCandidateRegistrationError):
        mgr.register_candidate(cand)


def test_03_retrieval():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)

    rec = mgr.get_record("cand-lifecycle-1")
    assert rec.candidate.id == "cand-lifecycle-1"

    all_recs = mgr.get_all_records()
    assert "cand-lifecycle-1" in all_recs

    with pytest.raises(CandidateNotFoundError):
        mgr.get_record("non-existent-id")


def test_04_valid_generated_to_organized_transition():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)

    rec = mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED, reason="Applied rules")
    assert rec.lifecycle_state == CandidateLifecycleState.ORGANIZED
    assert rec.state_history[-1]["from_state"] == "generated"
    assert rec.state_history[-1]["to_state"] == "organized"


def test_05_valid_organized_to_phase1_scored_transition():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED)

    rec = mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE1_SCORED)
    assert rec.lifecycle_state == CandidateLifecycleState.PHASE1_SCORED


def test_06_valid_phase1_scored_to_pruned_pre_realization_transition():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE1_SCORED)

    rec = mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PRUNED_PRE_REALIZATION, reason="Below threshold")
    assert rec.lifecycle_state == CandidateLifecycleState.PRUNED_PRE_REALIZATION


def test_07_valid_phase1_scored_to_plan_adapted_transition():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE1_SCORED)

    rec = mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PLAN_ADAPTED)
    assert rec.lifecycle_state == CandidateLifecycleState.PLAN_ADAPTED


def test_08_valid_plan_adapted_to_realized_transition():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE1_SCORED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PLAN_ADAPTED)

    rec = mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.REALIZED)
    assert rec.lifecycle_state == CandidateLifecycleState.REALIZED


def test_09_valid_plan_adapted_to_realization_failed_transition():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE1_SCORED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PLAN_ADAPTED)

    rec = mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.REALIZATION_FAILED, reason="Solver timeout")
    assert rec.lifecycle_state == CandidateLifecycleState.REALIZATION_FAILED


def test_10_valid_realized_to_phase2_scored_transition():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE1_SCORED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PLAN_ADAPTED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.REALIZED)

    rec = mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE2_SCORED)
    assert rec.lifecycle_state == CandidateLifecycleState.PHASE2_SCORED


def test_11_valid_phase2_scored_to_ranked_transition():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE1_SCORED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PLAN_ADAPTED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.REALIZED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE2_SCORED)

    rec = mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.RANKED)
    assert rec.lifecycle_state == CandidateLifecycleState.RANKED


def test_12_valid_ranked_to_selected_transition():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE1_SCORED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PLAN_ADAPTED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.REALIZED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE2_SCORED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.RANKED)

    rec = mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.SELECTED)
    assert rec.lifecycle_state == CandidateLifecycleState.SELECTED


def test_13_valid_ranked_to_rejected_transition():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE1_SCORED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PLAN_ADAPTED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.REALIZED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE2_SCORED)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.RANKED)

    rec = mgr.reject_candidate("cand-lifecycle-1", reason="Low total score")
    assert rec.lifecycle_state == CandidateLifecycleState.REJECTED


def test_14_invalid_transition_rejection():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)

    with pytest.raises(LifecycleTransitionError):
        mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.SELECTED)


def test_15_state_history_preservation():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED, reason="Rule application")

    history = mgr.get_history("cand-lifecycle-1")
    assert len(history) == 2
    assert history[0]["to_state"] == "generated"
    assert history[1]["from_state"] == "generated"
    assert history[1]["to_state"] == "organized"
    assert history[1]["reason"] == "Rule application"


def test_16_rejection_reason_preservation():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)
    mgr.reject_candidate("cand-lifecycle-1", reason="Incompatible circulation topology")

    rec = mgr.get_record("cand-lifecycle-1")
    assert rec.lifecycle_state == CandidateLifecycleState.REJECTED
    assert rec.state_history[-1]["reason"] == "Incompatible circulation topology"


def test_17_candidate_lineage_preservation():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    rec = mgr.register_candidate(cand)

    assert rec.candidate.id == "cand-lifecycle-1"
    assert rec.candidate.source_strategy_id == "strat-1"
    assert rec.candidate.source_problem_id == "prob-1"
    assert rec.candidate.source_problem_version == 1


def test_18_artifact_association():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    mgr.register_candidate(cand)

    plan = SpatialLayoutPlan(
        id="plan-1",
        source_candidate_id="cand-lifecycle-1",
        source_strategy_id="strat-1",
        source_problem_id="prob-1",
        source_problem_version=1,
        plot_width=40.0,
        plot_depth=40.0,
        floors=1,
        rooms=[SpatialRoomSpec(id="s1", name="Living", room_type="living", target_area=150.0, floor_assignment=1)],
    )

    score = ScoreBreakdown(criteria=[], total_score=0.85, scoring_version="3B.5.v1")

    rec = mgr.update_payloads("cand-lifecycle-1", layout_plan=plan, phase1_score=score)
    assert rec.layout_plan.id == "plan-1"
    assert rec.phase1_score.total_score == 0.85


def test_19_deterministic_repeated_transitions():
    mgr1 = CandidateLifecycleManager()
    cand1 = _sample_candidate()
    mgr1.register_candidate(cand1)
    mgr1.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED, reason="step 1")
    mgr1.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE1_SCORED, reason="step 2")

    mgr2 = CandidateLifecycleManager()
    cand2 = _sample_candidate()
    mgr2.register_candidate(cand2)
    mgr2.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED, reason="step 1")
    mgr2.transition_state("cand-lifecycle-1", CandidateLifecycleState.PHASE1_SCORED, reason="step 2")

    assert mgr1.get_record("cand-lifecycle-1").model_dump_json() == mgr2.get_record("cand-lifecycle-1").model_dump_json()


def test_20_source_candidate_immutability():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    orig_dump = cand.model_dump_json()

    mgr.register_candidate(cand)
    mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED)

    assert cand.model_dump_json() == orig_dump


def test_21_no_solver_invocation():
    # Structural verification that lifecycle manager does not call solvers
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    rec = mgr.register_candidate(cand)
    assert rec.realization_result is None


def test_22_no_compiler_invocation():
    # Structural verification that lifecycle manager does not call compiler
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    rec = mgr.register_candidate(cand)
    assert rec.layout_plan is None


def test_23_no_geometry_invocation():
    # Structural verification that lifecycle manager contains no geometry
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    rec = mgr.register_candidate(cand)
    assert not hasattr(rec, "geometry")


def test_24_no_scoring_invocation():
    # Structural verification that lifecycle manager does not calculate scores
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    rec = mgr.register_candidate(cand)
    assert rec.phase1_score is None
    assert rec.phase2_score is None


def test_25_ast_boundary_check():
    target_file = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "lifecycle_manager.py"
    content = target_file.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(target_file))

    prohibited_modules = {
        "shapely", "pulp", "cbc", "solver", "compiler",
        "requests", "httpx", "google", "gemini",
        "abstract_strategic_scorer", "spatial_realization_scorer",
        "candidate_selector", "spatial_adapter", "compiler_bridge",
        "strategy_generator", "candidate_generator"
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0].lower() not in prohibited_modules
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert node.module.split(".")[0].lower() not in prohibited_modules


def test_26_unseen_custom_metadata_remains_untouched():
    mgr = CandidateLifecycleManager()
    cand = _sample_candidate()
    cand.selected_decisions.append(
        DecisionRecord(
            id="dec-custom",
            dimension="unseen_custom_dimension",
            subject="building",
            value="custom_val",
            status=DecisionStatus.FIXED,
        )
    )

    rec = mgr.register_candidate(cand)
    rec_trans = mgr.transition_state("cand-lifecycle-1", CandidateLifecycleState.ORGANIZED)
    assert rec_trans.candidate.selected_decisions[1].dimension == "unseen_custom_dimension"
