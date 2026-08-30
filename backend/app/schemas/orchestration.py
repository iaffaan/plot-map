"""
Orchestration Schemas Contract for Stage 3B.6-1.

Provides schema-level data contracts to represent pipeline lifecycle states,
orchestration configuration, per-candidate execution records, and final
end-to-end design orchestration results.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator

from app.schemas.design_candidate import DesignCandidate
from app.schemas.spatial_realization import RealizationResult, SpatialLayoutPlan
from app.schemas.strategy_ranking import RankingResult, ScoreBreakdown


class CandidateLifecycleState(str, Enum):
    """Lifecycle state machine for a DesignCandidate traveling through orchestration."""
    GENERATED = "generated"
    ORGANIZED = "organized"
    PHASE1_SCORED = "phase1_scored"
    PRUNED_PRE_REALIZATION = "pruned_pre_realization"
    PLAN_ADAPTED = "plan_adapted"
    REALIZED = "realized"
    REALIZATION_FAILED = "realization_failed"
    PHASE2_SCORED = "phase2_scored"
    RANKED = "ranked"
    SELECTED = "selected"
    REJECTED = "rejected"


class OrchestrationConfig(BaseModel):
    """Configuration parameters controlling pipeline execution and resource limits."""
    max_strategies: int = Field(default=10, ge=1, description="Maximum number of strategies to consider")
    max_candidates_per_strategy: int = Field(default=5, ge=1, description="Maximum candidates per strategy")
    max_selected: int = Field(default=3, ge=0, description="Maximum candidates to mark as SELECTED")
    phase1_prune_threshold: float = Field(default=0.30, ge=0.0, le=1.0, description="Phase 1 minimum score to proceed to realization")
    enable_realization: bool = Field(default=True, description="Whether to execute 2D spatial layout realization")
    solver_time_limit_sec: int = Field(default=5, ge=1, description="Timeout limit in seconds per spatial layout solve")
    grid_snap: float = Field(default=0.5, gt=0.0, description="Grid snap resolution in meters")
    extra_parameters: dict[str, Any] = Field(default_factory=dict, description="Arbitrary custom configuration parameters")


class OrchestrationCandidateRecord(BaseModel):
    """Tracks state, data payloads, and scores for a single DesignCandidate through pipeline stages."""
    candidate: DesignCandidate
    layout_plan: SpatialLayoutPlan | None = None
    realization_result: RealizationResult | None = None
    phase1_score: ScoreBreakdown | None = None
    phase2_score: ScoreBreakdown | None = None
    combined_score: ScoreBreakdown | None = None
    lifecycle_state: CandidateLifecycleState = CandidateLifecycleState.GENERATED
    state_history: list[dict[str, Any]] = Field(default_factory=list, description="Audit log of state transitions")
    provenance: dict[str, Any] = Field(default_factory=dict, description="Custom metadata and lineage details")

    @field_validator("candidate")
    @classmethod
    def validate_candidate_not_none(cls, v: DesignCandidate) -> DesignCandidate:
        if v is None:
            raise ValueError("Candidate record must contain a valid non-null DesignCandidate")
        return v


class DesignOrchestrationResult(BaseModel):
    """End-to-end orchestration result capturing ranking, candidate records, and provenance."""
    id: str = Field(min_length=1, description="Unique orchestration execution ID")
    source_problem_id: str = Field(min_length=1, description="Source DesignProblem ID")
    source_problem_version: int = Field(ge=1, description="Source DesignProblem version")
    ranking_result: RankingResult
    candidate_records: dict[str, OrchestrationCandidateRecord] = Field(default_factory=dict, description="Per-candidate orchestration records keyed by candidate_id")
    config_used: OrchestrationConfig
    execution_stats: dict[str, Any] = Field(default_factory=dict, description="Pipeline performance statistics")
    provenance: dict[str, Any] = Field(default_factory=dict, description="Execution lineage and environment provenance")

    @field_validator("id", "source_problem_id")
    @classmethod
    def validate_non_empty_ids(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("ID fields cannot be empty or whitespace")
        return v

    @field_validator("candidate_records")
    @classmethod
    def validate_candidate_records_keys(cls, records: dict[str, OrchestrationCandidateRecord]) -> dict[str, OrchestrationCandidateRecord]:
        for key, record in records.items():
            if key != record.candidate.id:
                raise ValueError(f"Candidate record key '{key}' does not match candidate.id '{record.candidate.id}'")
        return records


class Phase1PruningResult(BaseModel):
    """Output contract for Phase 1 pre-realization strategic pruning."""
    source_problem_id: str = Field(min_length=1, description="Source DesignProblem ID")
    source_problem_version: int = Field(ge=1, description="Source DesignProblem version")
    prune_threshold_used: float = Field(ge=0.0, le=1.0, description="Phase 1 prune threshold applied")
    total_candidates_processed: int = Field(ge=0, description="Total candidates evaluated in Phase 1")
    surviving_candidate_ids: list[str] = Field(default_factory=list, description="IDs of candidates meeting or exceeding threshold")
    pruned_candidate_ids: list[str] = Field(default_factory=list, description="IDs of candidates pruned below threshold")
    candidate_records: dict[str, OrchestrationCandidateRecord] = Field(default_factory=dict, description="Updated records from lifecycle manager")
    provenance: dict[str, Any] = Field(default_factory=dict, description="Phase 1 execution provenance")

    @field_validator("source_problem_id")
    @classmethod
    def validate_source_problem_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("source_problem_id cannot be empty or whitespace")
        return v


class SpatialPhase2Result(BaseModel):
    """Output contract for Phase 2 spatial layout realization and post-realization scoring."""
    source_problem_id: str = Field(min_length=1, description="Source DesignProblem ID")
    source_problem_version: int = Field(ge=1, description="Source DesignProblem version")
    realization_enabled: bool = Field(default=True, description="Whether spatial layout realization was enabled")
    total_candidates_processed: int = Field(ge=0, description="Total candidates evaluated in Phase 2")
    successful_realization_ids: list[str] = Field(default_factory=list, description="IDs of candidates successfully realized")
    failed_realization_ids: list[str] = Field(default_factory=list, description="IDs of candidates failing spatial layout realization")
    skipped_pruned_ids: list[str] = Field(default_factory=list, description="IDs of candidates skipped because they were pruned in Phase 1")
    candidate_records: dict[str, OrchestrationCandidateRecord] = Field(default_factory=dict, description="Updated records from lifecycle manager")
    provenance: dict[str, Any] = Field(default_factory=dict, description="Phase 2 execution provenance")

    @field_validator("source_problem_id")
    @classmethod
    def validate_source_problem_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("source_problem_id cannot be empty or whitespace")
        return v


