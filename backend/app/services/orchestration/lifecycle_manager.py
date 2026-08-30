"""
Candidate Lifecycle Manager for Stage 3B.6-2.

Provides deterministic state management, state transition validation,
and payload association for DesignCandidates traveling through the pipeline.
"""

from typing import Any

from app.schemas.design_candidate import DesignCandidate
from app.schemas.orchestration import (
    CandidateLifecycleState,
    OrchestrationCandidateRecord,
)
from app.schemas.spatial_realization import RealizationResult, SpatialLayoutPlan
from app.schemas.strategy_ranking import ScoreBreakdown


class LifecycleError(Exception):
    """Base exception for all candidate lifecycle errors."""
    pass


class LifecycleTransitionError(LifecycleError):
    """Raised when an invalid state transition is attempted."""
    pass


class DuplicateCandidateRegistrationError(LifecycleError):
    """Raised when a candidate ID is registered more than once."""
    pass


class CandidateNotFoundError(LifecycleError):
    """Raised when a candidate ID is not found in records."""
    pass


class CandidateLifecycleManager:
    """
    Manages deterministic lifecycle state transitions and artifact provenance
    for DesignCandidate records within the orchestration pipeline.
    """

    VALID_TRANSITIONS: dict[CandidateLifecycleState, set[CandidateLifecycleState]] = {
        CandidateLifecycleState.GENERATED: {
            CandidateLifecycleState.ORGANIZED,
            CandidateLifecycleState.REJECTED,
        },
        CandidateLifecycleState.ORGANIZED: {
            CandidateLifecycleState.PHASE1_SCORED,
            CandidateLifecycleState.REJECTED,
        },
        CandidateLifecycleState.PHASE1_SCORED: {
            CandidateLifecycleState.PLAN_ADAPTED,
            CandidateLifecycleState.PRUNED_PRE_REALIZATION,
            CandidateLifecycleState.REJECTED,
        },
        CandidateLifecycleState.PRUNED_PRE_REALIZATION: {
            CandidateLifecycleState.RANKED,
            CandidateLifecycleState.REJECTED,
        },
        CandidateLifecycleState.PLAN_ADAPTED: {
            CandidateLifecycleState.REALIZED,
            CandidateLifecycleState.REALIZATION_FAILED,
            CandidateLifecycleState.RANKED,
            CandidateLifecycleState.REJECTED,
        },
        CandidateLifecycleState.REALIZED: {
            CandidateLifecycleState.PHASE2_SCORED,
            CandidateLifecycleState.REJECTED,
        },
        CandidateLifecycleState.REALIZATION_FAILED: {
            CandidateLifecycleState.PHASE2_SCORED,
            CandidateLifecycleState.RANKED,
            CandidateLifecycleState.REJECTED,
        },
        CandidateLifecycleState.PHASE2_SCORED: {
            CandidateLifecycleState.RANKED,
            CandidateLifecycleState.REJECTED,
        },
        CandidateLifecycleState.RANKED: {
            CandidateLifecycleState.SELECTED,
            CandidateLifecycleState.REJECTED,
        },
        CandidateLifecycleState.SELECTED: set(),
        CandidateLifecycleState.REJECTED: set(),
    }

    def __init__(self) -> None:
        self._records: dict[str, OrchestrationCandidateRecord] = {}

    def register_candidate(self, candidate: DesignCandidate) -> OrchestrationCandidateRecord:
        """Registers a new DesignCandidate starting in the GENERATED state."""
        if not candidate or not candidate.id:
            raise LifecycleError("Cannot register candidate with empty or missing ID")

        if candidate.id in self._records:
            raise DuplicateCandidateRegistrationError(
                f"Candidate with ID '{candidate.id}' is already registered"
            )

        candidate_copy = candidate.model_copy(deep=True)
        record = OrchestrationCandidateRecord(
            candidate=candidate_copy,
            lifecycle_state=CandidateLifecycleState.GENERATED,
            state_history=[
                {
                    "from_state": None,
                    "to_state": CandidateLifecycleState.GENERATED.value,
                    "reason": "Registered candidate in lifecycle manager",
                }
            ],
        )
        self._records[candidate.id] = record
        return record.model_copy(deep=True)

    @classmethod
    def is_valid_transition(
        cls, current_state: CandidateLifecycleState, target_state: CandidateLifecycleState
    ) -> bool:
        """Determines whether a transition from current_state to target_state is allowed."""
        return target_state in cls.VALID_TRANSITIONS.get(current_state, set())

    def transition_state(
        self,
        candidate_id: str,
        new_state: CandidateLifecycleState,
        reason: str = "",
    ) -> OrchestrationCandidateRecord:
        """Transitions a candidate to a new lifecycle state if valid."""
        if candidate_id not in self._records:
            raise CandidateNotFoundError(f"Candidate ID '{candidate_id}' not registered")

        record = self._records[candidate_id]
        current_state = record.lifecycle_state

        if current_state == new_state:
            return record.model_copy(deep=True)

        if not self.is_valid_transition(current_state, new_state):
            raise LifecycleTransitionError(
                f"Invalid transition for candidate '{candidate_id}' from {current_state.value} to {new_state.value}"
            )

        record.lifecycle_state = new_state
        record.state_history.append(
            {
                "from_state": current_state.value,
                "to_state": new_state.value,
                "reason": reason or f"Transitioned from {current_state.value} to {new_state.value}",
            }
        )
        return record.model_copy(deep=True)

    def reject_candidate(self, candidate_id: str, reason: str) -> OrchestrationCandidateRecord:
        """Rejects a candidate with an explicit reason."""
        if not reason or not reason.strip():
            raise LifecycleError("Rejection reason must be a non-empty string")
        return self.transition_state(candidate_id, CandidateLifecycleState.REJECTED, reason=reason)

    def update_payloads(
        self,
        candidate_id: str,
        layout_plan: SpatialLayoutPlan | None = None,
        realization_result: RealizationResult | None = None,
        phase1_score: ScoreBreakdown | None = None,
        phase2_score: ScoreBreakdown | None = None,
        combined_score: ScoreBreakdown | None = None,
    ) -> OrchestrationCandidateRecord:
        """Associates external execution payloads/artifacts with the candidate record."""
        if candidate_id not in self._records:
            raise CandidateNotFoundError(f"Candidate ID '{candidate_id}' not registered")

        record = self._records[candidate_id]

        if layout_plan is not None:
            record.layout_plan = layout_plan.model_copy(deep=True)
        if realization_result is not None:
            record.realization_result = realization_result.model_copy(deep=True)
        if phase1_score is not None:
            record.phase1_score = phase1_score.model_copy(deep=True)
        if phase2_score is not None:
            record.phase2_score = phase2_score.model_copy(deep=True)
        if combined_score is not None:
            record.combined_score = combined_score.model_copy(deep=True)

        return record.model_copy(deep=True)

    def get_record(self, candidate_id: str) -> OrchestrationCandidateRecord:
        """Retrieves a deep copy of a candidate record."""
        if candidate_id not in self._records:
            raise CandidateNotFoundError(f"Candidate ID '{candidate_id}' not registered")
        return self._records[candidate_id].model_copy(deep=True)

    def get_history(self, candidate_id: str) -> list[dict[str, Any]]:
        """Retrieves state history for a candidate ID."""
        record = self.get_record(candidate_id)
        return list(record.state_history)

    def get_all_records(self) -> dict[str, OrchestrationCandidateRecord]:
        """Retrieves deep copies of all registered candidate records."""
        return {
            cid: rec.model_copy(deep=True) for cid, rec in self._records.items()
        }
