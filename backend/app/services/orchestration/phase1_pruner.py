"""
Phase 1 Strategic Pre-Filtering & Pruning Orchestrator for Stage 3B.6-3.

Evaluates DesignCandidates using AbstractStrategicScorer and applies
deterministic pre-realization pruning thresholds before spatial layout realization.
"""

from typing import Any

from app.schemas.design_candidate import DesignCandidate
from app.schemas.design_problem import DesignProblem
from app.schemas.orchestration import (
    CandidateLifecycleState,
    OrchestrationConfig,
    Phase1PruningResult,
)
from app.schemas.strategy_preference import PreferenceCatalog
from app.schemas.strategy_ranking import CriterionScore, ScoreBreakdown
from app.services.analysis.catalog_loader import get_preference_catalog
from app.services.orchestration.lifecycle_manager import CandidateLifecycleManager
from app.services.ranking.abstract_strategic_scorer import AbstractStrategicScorer


class Phase1Pruner:
    """
    Orchestrates Phase 1 pre-realization strategic evaluation and candidate pruning.
    """

    @classmethod
    def score_and_prune(
        cls,
        candidates: list[DesignCandidate],
        problem: DesignProblem,
        lifecycle_manager: CandidateLifecycleManager,
        config: OrchestrationConfig | None = None,
        preference_catalog: PreferenceCatalog | None = None,
    ) -> Phase1PruningResult:
        """
        Executes Phase 1 scoring for a collection of candidates and applies
        deterministic pre-realization pruning threshold bounds.
        """
        config_obj = config or OrchestrationConfig()
        catalog = get_preference_catalog(preference_catalog)
        prune_threshold = config_obj.phase1_prune_threshold
        precision = catalog.deterministic_precision

        if not problem or not problem.id:
            raise ValueError("Problem must be a valid DesignProblem with a non-empty ID")

        if not candidates:
            return Phase1PruningResult(
                source_problem_id=problem.id,
                source_problem_version=problem.version,
                prune_threshold_used=prune_threshold,
                total_candidates_processed=0,
                surviving_candidate_ids=[],
                pruned_candidate_ids=[],
                candidate_records=lifecycle_manager.get_all_records(),
                provenance={
                    "orchestrator_phase": "Phase1Pruner",
                    "source_problem_id": problem.id,
                    "source_problem_version": problem.version,
                    "total_processed": 0,
                    "total_surviving": 0,
                    "total_pruned": 0,
                    "phase1_prune_threshold": prune_threshold,
                    "scoring_catalog_version": catalog.version,
                },
            )

        surviving_ids: list[str] = []
        pruned_ids: list[str] = []

        for candidate in candidates:
            if not candidate or not candidate.id:
                continue

            # Ensure candidate is registered in lifecycle manager
            try:
                rec = lifecycle_manager.get_record(candidate.id)
            except Exception:
                rec = lifecycle_manager.register_candidate(candidate)

            # Ensure transition to ORGANIZED if starting from GENERATED
            if rec.lifecycle_state == CandidateLifecycleState.GENERATED:
                lifecycle_manager.transition_state(
                    candidate.id,
                    CandidateLifecycleState.ORGANIZED,
                    reason="Candidate organized for Phase 1 scoring",
                )

            # Abstract Strategic Scoring
            try:
                score_breakdown = AbstractStrategicScorer.score_candidate(
                    candidate, problem, catalog
                )
            except Exception as scoring_err:
                # Contain scoring exception into invalid zero score breakdown
                score_breakdown = ScoreBreakdown(
                    criteria=[
                        CriterionScore(
                            criterion_id=c.id,
                            score=0.0,
                            weight=c.weight,
                            weighted_score=0.0,
                            explanation=f"Phase 1 scoring failed: {scoring_err}",
                            source_ids=[],
                        )
                        for c in catalog.criteria
                    ],
                    total_score=0.0,
                    scoring_version=catalog.version,
                )

            # Update lifecycle record payload with Phase 1 ScoreBreakdown
            lifecycle_manager.update_payloads(candidate.id, phase1_score=score_breakdown)

            # Transition to PHASE1_SCORED
            lifecycle_manager.transition_state(
                candidate.id,
                CandidateLifecycleState.PHASE1_SCORED,
                reason=f"Phase 1 scoring complete (Total Score: {score_breakdown.total_score:.{precision}f})",
            )

            # Evaluate Pruning Threshold
            total_score = score_breakdown.total_score
            if total_score < prune_threshold:
                prune_reason = (
                    f"Pruned pre-realization: Phase 1 total score {total_score:.{precision}f} "
                    f"below threshold {prune_threshold:.{precision}f}"
                )
                lifecycle_manager.transition_state(
                    candidate.id,
                    CandidateLifecycleState.PRUNED_PRE_REALIZATION,
                    reason=prune_reason,
                )
                pruned_ids.append(candidate.id)
            else:
                surviving_ids.append(candidate.id)

        all_records = lifecycle_manager.get_all_records()
        provenance = {
            "orchestrator_phase": "Phase1Pruner",
            "source_problem_id": problem.id,
            "source_problem_version": problem.version,
            "total_processed": len(candidates),
            "total_surviving": len(surviving_ids),
            "total_pruned": len(pruned_ids),
            "phase1_prune_threshold": prune_threshold,
            "scoring_catalog_version": catalog.version,
        }

        return Phase1PruningResult(
            source_problem_id=problem.id,
            source_problem_version=problem.version,
            prune_threshold_used=prune_threshold,
            total_candidates_processed=len(candidates),
            surviving_candidate_ids=surviving_ids,
            pruned_candidate_ids=pruned_ids,
            candidate_records=all_records,
            provenance=provenance,
        )
