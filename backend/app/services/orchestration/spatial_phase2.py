"""
Spatial Realization & Phase 2 Ranking Orchestrator for Stage 3B.6-4.

Executes spatial layout plan adaptation, 2D MILP layout realization, and Phase 2
post-realization scoring for Phase 1 candidate survivors.
"""

from typing import Any

from app.schemas.design_candidate import DesignCandidate
from app.schemas.design_problem import DesignProblem
from app.schemas.orchestration import (
    CandidateLifecycleState,
    OrchestrationConfig,
    SpatialPhase2Result,
)
from app.schemas.spatial_realization import RealizationResult, RealizationStatus
from app.schemas.strategy_preference import PreferenceCatalog
from app.schemas.strategy_ranking import CriterionScore, ScoreBreakdown
from app.services.analysis.catalog_loader import get_preference_catalog
from app.services.analysis.spatial_adapter import CandidateToLayoutAdapter
from app.services.orchestration.lifecycle_manager import CandidateLifecycleManager
from app.services.ranking.spatial_realization_scorer import SpatialRealizationScorer
from app.services.realization.compiler_bridge import SpatialCompilerBridge


class SpatialPhase2Orchestrator:
    """
    Orchestrates Phase 2 spatial layout realization and post-realization scoring.
    """

    @classmethod
    def realize_and_score(
        cls,
        candidates: list[DesignCandidate],
        problem: DesignProblem,
        lifecycle_manager: CandidateLifecycleManager,
        config: OrchestrationConfig | None = None,
        preference_catalog: PreferenceCatalog | None = None,
    ) -> SpatialPhase2Result:
        """
        Processes candidate survivors through spatial layout adaptation, layout realization,
        and post-realization scoring.
        """
        config_obj = config or OrchestrationConfig()
        catalog = get_preference_catalog(preference_catalog)
        precision = catalog.deterministic_precision

        if not problem or not problem.id:
            raise ValueError("Problem must be a valid DesignProblem with a non-empty ID")

        realization_enabled = config_obj.enable_realization

        if not candidates:
            return SpatialPhase2Result(
                source_problem_id=problem.id,
                source_problem_version=problem.version,
                realization_enabled=realization_enabled,
                total_candidates_processed=0,
                successful_realization_ids=[],
                failed_realization_ids=[],
                skipped_pruned_ids=[],
                candidate_records=lifecycle_manager.get_all_records(),
                provenance={
                    "orchestrator_phase": "SpatialPhase2Orchestrator",
                    "source_problem_id": problem.id,
                    "source_problem_version": problem.version,
                    "realization_enabled": realization_enabled,
                    "total_processed": 0,
                    "total_successful": 0,
                    "total_failed": 0,
                    "total_skipped_pruned": 0,
                    "scoring_catalog_version": catalog.version,
                },
            )

        successful_ids: list[str] = []
        failed_ids: list[str] = []
        skipped_ids: list[str] = []
        processed_candidates: list[str] = []
        seen_candidate_ids: set[str] = set()

        for candidate in candidates:
            if not candidate or not candidate.id:
                continue

            # Ensure duplicate candidate IDs in list do not break state
            if candidate.id in seen_candidate_ids:
                continue
            seen_candidate_ids.add(candidate.id)

            # Ensure candidate is registered in lifecycle manager
            try:
                rec = lifecycle_manager.get_record(candidate.id)
            except Exception:
                rec = lifecycle_manager.register_candidate(candidate)

            # Check if candidate was pruned in Phase 1 or rejected
            if rec.lifecycle_state in {
                CandidateLifecycleState.PRUNED_PRE_REALIZATION,
                CandidateLifecycleState.REJECTED,
            }:
                skipped_ids.append(candidate.id)
                continue

            processed_candidates.append(candidate.id)

            # Ensure valid state progression to PHASE1_SCORED if starting from earlier lifecycle states
            if rec.lifecycle_state == CandidateLifecycleState.GENERATED:
                rec = lifecycle_manager.transition_state(
                    candidate.id,
                    CandidateLifecycleState.ORGANIZED,
                    reason="Candidate organized for spatial realization",
                )
            if rec.lifecycle_state == CandidateLifecycleState.ORGANIZED:
                rec = lifecycle_manager.transition_state(
                    candidate.id,
                    CandidateLifecycleState.PHASE1_SCORED,
                    reason="Candidate marked PHASE1_SCORED for spatial realization",
                )

            # If realization is disabled, do not invoke compiler or solver
            if not realization_enabled:
                lifecycle_manager.transition_state(
                    candidate.id,
                    CandidateLifecycleState.PLAN_ADAPTED,
                    reason="Spatial realization skipped (enable_realization=False)",
                )
                continue

            # Step 1: Spatial Plan Adaptation
            try:
                layout_plan = CandidateToLayoutAdapter.adapt(candidate, problem)
                lifecycle_manager.update_payloads(candidate.id, layout_plan=layout_plan)
                lifecycle_manager.transition_state(
                    candidate.id,
                    CandidateLifecycleState.PLAN_ADAPTED,
                    reason="Spatial layout plan adapted",
                )
            except Exception as adapt_err:
                # Treat adaptation failure as a realization failure
                fail_res = RealizationResult(
                    status=RealizationStatus.INVALID_CANDIDATE,
                    success=False,
                    candidate_id=candidate.id,
                    error_message=f"Plan adaptation failed: {adapt_err}",
                    provenance={"error_phase": "adaptation"},
                )
                lifecycle_manager.update_payloads(candidate.id, realization_result=fail_res)
                lifecycle_manager.transition_state(
                    candidate.id,
                    CandidateLifecycleState.REALIZATION_FAILED,
                    reason=f"Realization failed (invalid_candidate): {fail_res.error_message}",
                )
                failed_ids.append(candidate.id)
                continue

            # Step 2: Compiler Bridge & MILP Realization
            try:
                realization_res = SpatialCompilerBridge.realize_layout(
                    layout_plan,
                    problem=problem,
                )
            except Exception as bridge_err:
                norm_msg = f"Bridge invocation exception: {bridge_err}"
                status = SpatialCompilerBridge.classify_failure(norm_msg, exc=bridge_err)
                realization_res = RealizationResult(
                    status=status,
                    success=False,
                    candidate_id=candidate.id,
                    layout_plan=layout_plan,
                    error_message=norm_msg,
                    provenance={"error_phase": "bridge_invocation"},
                )

            lifecycle_manager.update_payloads(candidate.id, realization_result=realization_res)

            # Step 3: Evaluate Realization Outcome
            if realization_res.success:
                lifecycle_manager.transition_state(
                    candidate.id,
                    CandidateLifecycleState.REALIZED,
                    reason="Spatial layout realized successfully",
                )

                # Step 4: Phase 2 Spatial Scoring
                try:
                    score_breakdown = SpatialRealizationScorer.score_realization(
                        candidate, problem, realization_res, catalog
                    )
                except Exception as score_err:
                    score_breakdown = ScoreBreakdown(
                        criteria=[
                            CriterionScore(
                                criterion_id=c.id,
                                score=0.0,
                                weight=c.weight,
                                weighted_score=0.0,
                                explanation=f"Phase 2 scoring failed: {score_err}",
                                source_ids=[],
                            )
                            for c in catalog.criteria
                        ],
                        total_score=0.0,
                        scoring_version=catalog.version,
                    )

                lifecycle_manager.update_payloads(candidate.id, phase2_score=score_breakdown)
                lifecycle_manager.transition_state(
                    candidate.id,
                    CandidateLifecycleState.PHASE2_SCORED,
                    reason=f"Phase 2 scoring complete (Score: {score_breakdown.total_score:.{precision}f})",
                )
                successful_ids.append(candidate.id)
            else:
                lifecycle_manager.transition_state(
                    candidate.id,
                    CandidateLifecycleState.REALIZATION_FAILED,
                    reason=f"Realization failed ({realization_res.status.value}): {realization_res.error_message}",
                )
                failed_ids.append(candidate.id)

        all_records = lifecycle_manager.get_all_records()
        provenance = {
            "orchestrator_phase": "SpatialPhase2Orchestrator",
            "source_problem_id": problem.id,
            "source_problem_version": problem.version,
            "realization_enabled": realization_enabled,
            "solver_time_limit_sec": config_obj.solver_time_limit_sec,
            "grid_snap": config_obj.grid_snap,
            "total_processed": len(processed_candidates),
            "total_successful": len(successful_ids),
            "total_failed": len(failed_ids),
            "total_skipped_pruned": len(skipped_ids),
            "scoring_catalog_version": catalog.version,
        }

        return SpatialPhase2Result(
            source_problem_id=problem.id,
            source_problem_version=problem.version,
            realization_enabled=realization_enabled,
            total_candidates_processed=len(processed_candidates),
            successful_realization_ids=successful_ids,
            failed_realization_ids=failed_ids,
            skipped_pruned_ids=skipped_ids,
            candidate_records=all_records,
            provenance=provenance,
        )
