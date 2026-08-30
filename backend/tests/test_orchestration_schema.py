"""
Schema Contract Test Suite for Stage 3B.6-1: Pipeline Contracts & Schemas.

Verifies:
1. Valid construction & default parameters
2. Candidate lifecycle state enum values & transitions
3. Configuration validation & bounds
4. Candidate record tracking & optional payloads
5. DesignOrchestrationResult lineage preservation
6. Failure & rejection representation
7. Duplicate candidate ID key mismatch protection
8. Invalid empty identifiers and negative version rejection
9. JSON serialization & round-trip determinism
10. Unseen / custom metadata dimensions survival
11. Non-mutation of nested source models
12. Static AST boundary checks (no shapely, pulp, cbc, solver, compiler, requests, httpx, google, gemini)
"""

import ast
import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.schemas.architectural_analysis import DecisionRecord, DecisionStatus
from app.schemas.design_candidate import DesignCandidate
from app.schemas.design_problem import DesignProblem, SiteDefinition, SpaceRequirement
from app.schemas.intent import RoomCategory, RoomIntent
from app.schemas.orchestration import (
    CandidateLifecycleState,
    DesignOrchestrationResult,
    OrchestrationCandidateRecord,
    OrchestrationConfig,
)
from app.schemas.spatial_realization import (
    RealizationResult,
    RealizationStatus,
    SpatialLayoutPlan,
    SpatialRoomSpec,
)
from app.schemas.strategy_ranking import (
    RankedCandidate,
    RankingResult,
    ScoreBreakdown,
    SelectionStatus,
)


def _sample_candidate() -> DesignCandidate:
    return DesignCandidate(
        id="cand-orchestrate-1",
        source_strategy_id="strat-1",
        source_analysis_id="analysis-1",
        source_problem_id="prob-1",
        source_problem_version=1,
        candidate_version=1,
        name="Test Candidate",
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


def _sample_ranking_result() -> RankingResult:
    return RankingResult(
        id="rank-res-1",
        source_problem_id="prob-1",
        source_problem_version=1,
        ranked_candidates=[
            RankedCandidate(
                candidate_id="cand-orchestrate-1",
                strategy_id="strat-1",
                rank=1,
                score_breakdown=ScoreBreakdown(criteria=[], total_score=0.85, scoring_version="3B.5.v1"),
                selection_status=SelectionStatus.SELECTED,
                rejection_reasons=[],
                provenance={},
            )
        ],
        selected_candidate_ids=["cand-orchestrate-1"],
        ranking_version="3B.5.v1",
        provenance={},
    )


def test_01_valid_construction_and_defaults():
    config = OrchestrationConfig()
    assert config.max_strategies == 10
    assert config.max_candidates_per_strategy == 5
    assert config.max_selected == 3
    assert config.phase1_prune_threshold == 0.30
    assert config.enable_realization is True
    assert config.solver_time_limit_sec == 5
    assert config.grid_snap == 0.5


def test_02_candidate_lifecycle_enum_values():
    states = [s.value for s in CandidateLifecycleState]
    assert "generated" in states
    assert "organized" in states
    assert "phase1_scored" in states
    assert "pruned_pre_realization" in states
    assert "plan_adapted" in states
    assert "realized" in states
    assert "realization_failed" in states
    assert "phase2_scored" in states
    assert "ranked" in states
    assert "selected" in states
    assert "rejected" in states


def test_03_orchestration_config_validation_and_bounds():
    with pytest.raises(ValidationError):
        OrchestrationConfig(max_strategies=0)

    with pytest.raises(ValidationError):
        OrchestrationConfig(phase1_prune_threshold=1.5)

    with pytest.raises(ValidationError):
        OrchestrationConfig(grid_snap=0.0)

    cfg = OrchestrationConfig(extra_parameters={"custom_flag": True})
    assert cfg.extra_parameters["custom_flag"] is True


def test_04_orchestration_candidate_record_minimal_and_full():
    cand = _sample_candidate()
    record = OrchestrationCandidateRecord(candidate=cand)

    assert record.candidate.id == "cand-orchestrate-1"
    assert record.lifecycle_state == CandidateLifecycleState.GENERATED
    assert record.layout_plan is None
    assert record.realization_result is None

    plan = SpatialLayoutPlan(
        id="plan-1",
        source_candidate_id="cand-orchestrate-1",
        source_strategy_id="strat-1",
        source_problem_id="prob-1",
        source_problem_version=1,
        plot_width=40.0,
        plot_depth=40.0,
        floors=1,
        rooms=[SpatialRoomSpec(id="s1", name="Living", room_type="living", target_area=150.0, floor_assignment=1)],
    )

    rr = RealizationResult(
        status=RealizationStatus.SUCCESS,
        success=True,
        candidate_id="cand-orchestrate-1",
        layout_plan=plan,
    )

    full_record = OrchestrationCandidateRecord(
        candidate=cand,
        layout_plan=plan,
        realization_result=rr,
        lifecycle_state=CandidateLifecycleState.SELECTED,
        state_history=[{"from": "ranked", "to": "selected", "reason": "top_score"}],
    )
    assert full_record.layout_plan.id == "plan-1"
    assert full_record.realization_result.success is True


def test_05_design_orchestration_result_valid_construction():
    cand = _sample_candidate()
    record = OrchestrationCandidateRecord(candidate=cand, lifecycle_state=CandidateLifecycleState.SELECTED)

    res = DesignOrchestrationResult(
        id="orch-res-1",
        source_problem_id="prob-1",
        source_problem_version=1,
        ranking_result=_sample_ranking_result(),
        candidate_records={"cand-orchestrate-1": record},
        config_used=OrchestrationConfig(),
        execution_stats={"total_duration_sec": 0.42},
        provenance={"engine": "DesignOrchestrator"},
    )

    assert res.id == "orch-res-1"
    assert res.source_problem_id == "prob-1"
    assert "cand-orchestrate-1" in res.candidate_records


def test_06_source_lineage_preservation():
    cand = _sample_candidate()
    record = OrchestrationCandidateRecord(candidate=cand)
    res = DesignOrchestrationResult(
        id="orch-lineage-1",
        source_problem_id=cand.source_problem_id,
        source_problem_version=cand.source_problem_version,
        ranking_result=_sample_ranking_result(),
        candidate_records={"cand-orchestrate-1": record},
        config_used=OrchestrationConfig(),
    )

    assert res.source_problem_id == "prob-1"
    assert res.source_problem_version == 1
    assert res.candidate_records["cand-orchestrate-1"].candidate.source_strategy_id == "strat-1"


def test_07_failure_and_rejection_representation():
    cand = _sample_candidate()
    rr_failed = RealizationResult(
        status=RealizationStatus.SPATIALLY_INFEASIBLE,
        success=False,
        candidate_id="cand-orchestrate-1",
        error_message="Boundary collision",
        infeasible_constraints=["c-left-wall"],
    )

    record = OrchestrationCandidateRecord(
        candidate=cand,
        realization_result=rr_failed,
        lifecycle_state=CandidateLifecycleState.REJECTED,
        state_history=[{"state": "rejected", "reason": "Spatial infeasibility"}],
    )

    assert record.realization_result.status == RealizationStatus.SPATIALLY_INFEASIBLE
    assert record.realization_result.error_message == "Boundary collision"
    assert record.lifecycle_state == CandidateLifecycleState.REJECTED


def test_08_duplicate_candidate_id_key_mismatch_rejection():
    cand = _sample_candidate()
    record = OrchestrationCandidateRecord(candidate=cand)

    with pytest.raises(ValidationError):
        DesignOrchestrationResult(
            id="orch-mismatch",
            source_problem_id="prob-1",
            source_problem_version=1,
            ranking_result=_sample_ranking_result(),
            candidate_records={"cand-wrong-key": record},
            config_used=OrchestrationConfig(),
        )


def test_09_invalid_empty_identifiers_rejected():
    with pytest.raises(ValidationError):
        DesignOrchestrationResult(
            id="",
            source_problem_id="prob-1",
            source_problem_version=1,
            ranking_result=_sample_ranking_result(),
            config_used=OrchestrationConfig(),
        )

    with pytest.raises(ValidationError):
        DesignOrchestrationResult(
            id="orch-1",
            source_problem_id="  ",
            source_problem_version=1,
            ranking_result=_sample_ranking_result(),
            config_used=OrchestrationConfig(),
        )


def test_10_invalid_source_problem_version_rejected():
    with pytest.raises(ValidationError):
        DesignOrchestrationResult(
            id="orch-1",
            source_problem_id="prob-1",
            source_problem_version=0,
            ranking_result=_sample_ranking_result(),
            config_used=OrchestrationConfig(),
        )


def test_11_json_serialization_and_round_trip():
    cand = _sample_candidate()
    record = OrchestrationCandidateRecord(candidate=cand)
    res = DesignOrchestrationResult(
        id="orch-json-1",
        source_problem_id="prob-1",
        source_problem_version=1,
        ranking_result=_sample_ranking_result(),
        candidate_records={"cand-orchestrate-1": record},
        config_used=OrchestrationConfig(),
    )

    json_str = res.model_dump_json()
    parsed = json.loads(json_str)

    res_restored = DesignOrchestrationResult.model_validate(parsed)
    assert res_restored.model_dump_json() == json_str


def test_12_unseen_custom_metadata_dimensions():
    cand = _sample_candidate()
    cand.selected_decisions.append(
        DecisionRecord(
            id="dec-custom",
            dimension="unseen_custom_metric",
            subject="building",
            value="solar_active",
            status=DecisionStatus.FIXED,
        )
    )

    record = OrchestrationCandidateRecord(
        candidate=cand,
        provenance={"custom_dimension": "unseen_custom_metric"},
    )
    res = DesignOrchestrationResult(
        id="orch-custom-1",
        source_problem_id="prob-1",
        source_problem_version=1,
        ranking_result=_sample_ranking_result(),
        candidate_records={"cand-orchestrate-1": record},
        config_used=OrchestrationConfig(extra_parameters={"solar_boost": 1.2}),
    )

    assert res.candidate_records["cand-orchestrate-1"].candidate.selected_decisions[1].dimension == "unseen_custom_metric"
    assert res.config_used.extra_parameters["solar_boost"] == 1.2


def test_13_no_mutation_of_nested_source_models():
    cand = _sample_candidate()
    orig_dump = cand.model_dump_json()

    record = OrchestrationCandidateRecord(candidate=cand)
    record.lifecycle_state = CandidateLifecycleState.SELECTED

    assert cand.model_dump_json() == orig_dump


def test_14_non_geometric_ast_boundary():
    target_file = Path(__file__).parent.parent / "app" / "schemas" / "orchestration.py"
    content = target_file.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(target_file))

    prohibited_strings = {"polygon", "vertex", "vertices", "coordinate", "bounding_box"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value.lower() not in prohibited_strings


def test_15_no_solver_geometry_llm_imports():
    target_file = Path(__file__).parent.parent / "app" / "schemas" / "orchestration.py"
    content = target_file.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(target_file))

    prohibited_modules = {"shapely", "pulp", "cbc", "solver", "compiler", "requests", "httpx", "google", "gemini"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0].lower() not in prohibited_modules
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert node.module.split(".")[0].lower() not in prohibited_modules
