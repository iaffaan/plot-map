"""
Unit Test Suite for Phase1Pruner (Stage 3B.6-3).

Verifies Phase 1 strategic evaluation, deterministic pre-realization pruning,
lifecycle integration, failure containment, immutability, determinism, and static AST isolation.
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
from app.schemas.strategy_preference import PreferenceCatalog, PreferenceCriterion, NormalizationConfig
from app.services.orchestration.lifecycle_manager import CandidateLifecycleManager
from app.services.orchestration.phase1_pruner import Phase1Pruner
from app.services.ranking.abstract_strategic_scorer import AbstractStrategicScorer


def _sample_problem(problem_id: str = "prob-prune-1") -> DesignProblem:
    return DesignProblem(
        id=problem_id,
        version=1,
        name="Test Pruning Problem",
        site=SiteDefinition(plot_width=40.0, plot_depth=40.0),
        spaces=[
            SpaceRequirement(id="s1", room=RoomIntent(name="Living Room", room_type="living", category=RoomCategory.LIVING, target_area=200.0), quantity=1),
            SpaceRequirement(id="s2", room=RoomIntent(name="Bedroom 1", room_type="bedroom", category=RoomCategory.BEDROOM, target_area=150.0), quantity=1),
        ],
        user_groups=[],
    )


def _sample_candidate(candidate_id: str = "cand-prune-1", decisions: list[DecisionRecord] | None = None) -> DesignCandidate:
    if decisions is None:
        decisions = [
            DecisionRecord(
                id="dec-1",
                dimension="circulation_topology",
                subject="building",
                value="shared",
                status=DecisionStatus.FIXED,
            )
        ]

    return DesignCandidate(
        id=candidate_id,
        source_strategy_id="strat-1",
        source_analysis_id="analysis-1",
        source_problem_id="prob-prune-1",
        source_problem_version=1,
        candidate_version=1,
        name=f"Candidate {candidate_id}",
        selected_decisions=decisions,
        floor_organization={"ground": ["s1", "s2"]},
        unit_organization={"u1": ["s1", "s2"]},
        circulation_intent=[],
        service_organization=[],
    )


def test_01_all_candidates_above_threshold():
    problem = _sample_problem()
    cands = [_sample_candidate("c1"), _sample_candidate("c2")]
    mgr = CandidateLifecycleManager()

    config = OrchestrationConfig(phase1_prune_threshold=0.10)
    result = Phase1Pruner.score_and_prune(cands, problem, mgr, config=config)

    assert result.total_candidates_processed == 2
    assert len(result.surviving_candidate_ids) == 2
    assert len(result.pruned_candidate_ids) == 0
    assert "c1" in result.surviving_candidate_ids
    assert "c2" in result.surviving_candidate_ids


def test_02_candidates_below_threshold():
    problem = _sample_problem()
    # Incomplete candidate with no floor organization will score low
    cand = DesignCandidate(
        id="c-low",
        source_strategy_id="strat-1",
        source_analysis_id="analysis-1",
        source_problem_id="prob-prune-1",
        source_problem_version=1,
        candidate_version=1,
        name="Low Score Candidate",
        selected_decisions=[],
        floor_organization={},
        unit_organization={},
        circulation_intent=[],
        service_organization=[],
    )
    mgr = CandidateLifecycleManager()

    config = OrchestrationConfig(phase1_prune_threshold=0.95)
    result = Phase1Pruner.score_and_prune([cand], problem, mgr, config=config)

    assert result.total_candidates_processed == 1
    assert len(result.surviving_candidate_ids) == 0
    assert len(result.pruned_candidate_ids) == 1
    assert result.pruned_candidate_ids[0] == "c-low"

    rec = mgr.get_record("c-low")
    assert rec.lifecycle_state == CandidateLifecycleState.PRUNED_PRE_REALIZATION
    assert "Pruned pre-realization" in rec.state_history[-1]["reason"]


def test_03_mixed_passing_pruned_candidates():
    problem = _sample_problem()
    c_good = _sample_candidate("c-good")
    c_low = DesignCandidate(
        id="c-bad",
        source_strategy_id="strat-1",
        source_analysis_id="analysis-1",
        source_problem_id="prob-prune-1",
        source_problem_version=1,
        candidate_version=1,
        name="Bad Candidate",
        selected_decisions=[],
        floor_organization={},
        unit_organization={},
        circulation_intent=[],
        service_organization=[],
    )
    mgr = CandidateLifecycleManager()

    config = OrchestrationConfig(phase1_prune_threshold=0.50)
    result = Phase1Pruner.score_and_prune([c_good, c_low], problem, mgr, config=config)

    assert "c-good" in result.surviving_candidate_ids
    assert "c-bad" in result.pruned_candidate_ids


def test_04_threshold_boundary_behavior():
    problem = _sample_problem()
    c1 = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    # Get exact score first
    score_breakdown = AbstractStrategicScorer.score_candidate(c1, problem)
    exact_score = score_breakdown.total_score

    # Threshold equal to score must survive
    config = OrchestrationConfig(phase1_prune_threshold=exact_score)
    result = Phase1Pruner.score_and_prune([c1], problem, mgr, config=config)

    assert "c1" in result.surviving_candidate_ids


def test_05_zero_candidates():
    problem = _sample_problem()
    mgr = CandidateLifecycleManager()

    result = Phase1Pruner.score_and_prune([], problem, mgr)

    assert result.total_candidates_processed == 0
    assert len(result.surviving_candidate_ids) == 0
    assert len(result.pruned_candidate_ids) == 0
    assert result.source_problem_id == "prob-prune-1"


def test_06_duplicate_candidate_handling():
    problem = _sample_problem()
    c1 = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    # Pre-register candidate
    mgr.register_candidate(c1)

    result = Phase1Pruner.score_and_prune([c1], problem, mgr)
    assert result.total_candidates_processed == 1
    assert "c1" in result.surviving_candidate_ids


def test_07_lifecycle_state_transitions():
    problem = _sample_problem()
    c1 = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    Phase1Pruner.score_and_prune([c1], problem, mgr)

    history = mgr.get_history("c1")
    states = [h["to_state"] for h in history]
    assert "generated" in states
    assert "organized" in states
    assert "phase1_scored" in states


def test_08_phase1_score_preservation():
    problem = _sample_problem()
    c1 = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    result = Phase1Pruner.score_and_prune([c1], problem, mgr)

    rec = result.candidate_records["c1"]
    assert rec.phase1_score is not None
    assert rec.phase1_score.total_score > 0.0


def test_09_explicit_pruning_reasons():
    problem = _sample_problem()
    c_low = DesignCandidate(
        id="c-low-reason",
        source_strategy_id="strat-1",
        source_analysis_id="analysis-1",
        source_problem_id="prob-prune-1",
        source_problem_version=1,
        candidate_version=1,
        name="Low Score Candidate",
        selected_decisions=[],
        floor_organization={},
        unit_organization={},
        circulation_intent=[],
        service_organization=[],
    )
    mgr = CandidateLifecycleManager()

    config = OrchestrationConfig(phase1_prune_threshold=0.99)
    result = Phase1Pruner.score_and_prune([c_low], problem, mgr, config=config)

    rec = result.candidate_records["c-low-reason"]
    assert rec.lifecycle_state == CandidateLifecycleState.PRUNED_PRE_REALIZATION
    assert "below threshold 0.990000" in rec.state_history[-1]["reason"]


def test_10_provenance_preservation():
    problem = _sample_problem()
    c1 = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    result = Phase1Pruner.score_and_prune([c1], problem, mgr)

    prov = result.provenance
    assert prov["orchestrator_phase"] == "Phase1Pruner"
    assert prov["source_problem_id"] == "prob-prune-1"
    assert prov["total_processed"] == 1
    assert prov["total_surviving"] == 1
    assert prov["total_pruned"] == 0


def test_11_deterministic_repeated_execution():
    problem = _sample_problem()
    c1 = _sample_candidate("c1")

    mgr1 = CandidateLifecycleManager()
    res1 = Phase1Pruner.score_and_prune([c1], problem, mgr1)

    mgr2 = CandidateLifecycleManager()
    res2 = Phase1Pruner.score_and_prune([c1], problem, mgr2)

    assert res1.model_dump_json() == res2.model_dump_json()


def test_12_candidate_immutability():
    problem = _sample_problem()
    cand = _sample_candidate("c-immut")
    orig_dump = cand.model_dump_json()

    mgr = CandidateLifecycleManager()
    Phase1Pruner.score_and_prune([cand], problem, mgr)

    assert cand.model_dump_json() == orig_dump


def test_13_custom_unseen_preference_criteria():
    problem = _sample_problem()
    cand = _sample_candidate("c-custom")

    # Catalog with unseen custom criterion
    custom_catalog = PreferenceCatalog(
        id="custom-cat",
        name="Custom Catalog",
        version="3B.6.v1",
        description="Custom catalog",
        deterministic_precision=6,
        criteria=[
            PreferenceCriterion(
                id="unseen_criterion_x",
                name="Unseen Metric X",
                weight=1.0,
                description="Custom criterion",
                normalization=NormalizationConfig(min_value=0.0, max_value=1.0),
                metadata={"category": "custom_category"},
            )
        ],
    )

    mgr = CandidateLifecycleManager()
    result = Phase1Pruner.score_and_prune([cand], problem, mgr, preference_catalog=custom_catalog)

    assert result.total_candidates_processed == 1
    assert result.candidate_records["c-custom"].phase1_score.criteria[0].criterion_id == "unseen_criterion_x"


def test_14_no_solver_invocation():
    problem = _sample_problem()
    c1 = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    result = Phase1Pruner.score_and_prune([c1], problem, mgr)
    rec = result.candidate_records["c1"]
    assert rec.realization_result is None


def test_15_no_compiler_invocation():
    problem = _sample_problem()
    c1 = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    result = Phase1Pruner.score_and_prune([c1], problem, mgr)
    rec = result.candidate_records["c1"]
    assert rec.layout_plan is None


def test_16_no_geometry_invocation():
    problem = _sample_problem()
    c1 = _sample_candidate("c1")
    mgr = CandidateLifecycleManager()

    result = Phase1Pruner.score_and_prune([c1], problem, mgr)
    rec = result.candidate_records["c1"]
    assert not hasattr(rec, "geometry")


def test_17_no_mutation_of_existing_scoring_engines():
    # Structural check proving AbstractStrategicScorer method output is unaltered
    problem = _sample_problem()
    c1 = _sample_candidate("c1")

    direct_score = AbstractStrategicScorer.score_candidate(c1, problem)

    mgr = CandidateLifecycleManager()
    res = Phase1Pruner.score_and_prune([c1], problem, mgr)

    pruner_score = res.candidate_records["c1"].phase1_score
    assert pruner_score.total_score == direct_score.total_score


def test_18_structured_handling_of_scoring_failures():
    problem = _sample_problem()
    # Invalid candidate with missing candidate ID in inner dict
    cand = _sample_candidate("c-fail")
    mgr = CandidateLifecycleManager()

    # Pass invalid problem to force evaluation exception handling
    bad_prob = _sample_problem("prob-bad")
    bad_prob.spaces = []
    bad_prob.user_groups = []

    res = Phase1Pruner.score_and_prune([cand], bad_prob, mgr, config=OrchestrationConfig(phase1_prune_threshold=0.01))
    assert res.total_candidates_processed == 1


def test_19_configurable_threshold_behavior():
    problem = _sample_problem()
    c1 = _sample_candidate("c1")

    mgr1 = CandidateLifecycleManager()
    res_high = Phase1Pruner.score_and_prune([c1], problem, mgr1, config=OrchestrationConfig(phase1_prune_threshold=1.0))
    assert len(res_high.pruned_candidate_ids) == 1

    mgr2 = CandidateLifecycleManager()
    res_low = Phase1Pruner.score_and_prune([c1], problem, mgr2, config=OrchestrationConfig(phase1_prune_threshold=0.0))
    assert len(res_low.surviving_candidate_ids) == 1


def test_20_ast_boundary_check():
    target_file = Path(__file__).parent.parent / "app" / "services" / "orchestration" / "phase1_pruner.py"
    content = target_file.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(target_file))

    prohibited_modules = {
        "shapely", "pulp", "cbc", "solver", "compiler",
        "requests", "httpx", "google", "gemini",
        "spatial_adapter", "compiler_bridge",
        "strategy_generator", "candidate_generator"
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0].lower() not in prohibited_modules
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert node.module.split(".")[0].lower() not in prohibited_modules
