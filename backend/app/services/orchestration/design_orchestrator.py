"""
End-to-End Design Orchestrator Service for Stage 3B.6-5.

Coordinates the complete BuildForgeAI architectural generation, evaluation,
spatial realization, ranking, and candidate selection pipeline.

STRICT ARCHITECTURAL BOUNDARY:
- pure coordinator: delegates strategy generation, candidate generation, candidate organization,
  lifecycle management, strategic pruning, spatial realization, and candidate selection.
- zero duplicate scoring, tie-breaking, compilation, solver, or geometry logic.
- zero hardcoded domain-specific branching.
- 100% deterministic, immutable, and data-driven.
"""

from typing import Any

from app.schemas.design_candidate import DesignCandidate
from app.schemas.design_problem import DesignProblem
from app.schemas.orchestration import (
    CandidateLifecycleState,
    DesignOrchestrationResult,
    OrchestrationConfig,
)
from app.schemas.strategy_preference import PreferenceCatalog
from app.schemas.strategy_ranking import (
    CriterionScore,
    RankedCandidate,
    ScoreBreakdown,
    SelectionStatus,
)
from app.services.analysis.architectural_analyzer import analyze_design_problem
from app.services.analysis.candidate_generator import generate_candidate_from_strategy
from app.services.analysis.candidate_organizer import organize_candidate
from app.services.analysis.catalog_loader import (
    get_catalog_organization_rules,
    get_preference_catalog,
)
from app.services.analysis.strategy_generator import generate_strategies
from app.services.orchestration.lifecycle_manager import CandidateLifecycleManager
from app.services.orchestration.phase1_pruner import Phase1Pruner
from app.services.orchestration.spatial_phase2 import SpatialPhase2Orchestrator
from app.services.ranking.candidate_selector import CandidateSelector
from app.services.ranking.spatial_realization_scorer import SpatialRealizationScorer


class DesignOrchestrator:
    """
    End-to-End Design Orchestrator Service.
    Coordinates strategy generation -> candidate generation -> spatial organization ->
    lifecycle tracking -> Phase 1 pruning -> Phase 2 spatial realization -> final ranking & selection.
    """

    @classmethod
    def run(
        cls,
        problem: DesignProblem,
        config: OrchestrationConfig | None = None,
        preference_catalog: PreferenceCatalog | None = None,
    ) -> DesignOrchestrationResult:
        """
        Executes the end-to-end design orchestration pipeline for a given DesignProblem.
        """
        if not problem or not hasattr(problem, "id") or not problem.id:
            raise ValueError("problem must be a valid DesignProblem with a non-empty ID")

        config_obj = config.model_copy(deep=True) if config else OrchestrationConfig()
        catalog = get_preference_catalog(preference_catalog)
        precision = catalog.deterministic_precision

        exec_id = f"orchestration-{problem.id}-{problem.version}"
        lifecycle_manager = CandidateLifecycleManager()

        # PHASE A: Strategy & Candidate Production
        try:
            analysis = analyze_design_problem(problem)
            strategies = generate_strategies(
                analysis,
                problem=problem,
                max_strategies=config_obj.max_strategies,
            )
        except Exception:
            strategies = []

        if not strategies:
            empty_ranking = CandidateSelector.select(
                ranked_candidates=[],
                preference_catalog=catalog,
                max_selected=config_obj.max_selected,
                source_problem_id=problem.id,
                source_problem_version=problem.version,
            )
            return DesignOrchestrationResult(
                id=exec_id,
                source_problem_id=problem.id,
                source_problem_version=problem.version,
                ranking_result=empty_ranking,
                candidate_records={},
                config_used=config_obj,
                execution_stats={
                    "total_strategies": 0,
                    "total_candidates": 0,
                    "total_phase1_survivors": 0,
                    "total_phase1_pruned": 0,
                    "total_realized_successful": 0,
                    "total_realized_failed": 0,
                    "total_selected": 0,
                },
                provenance={
                    "orchestrator": "DesignOrchestrator",
                    "orchestration_version": "3B.6-5.v1",
                    "source_problem_id": problem.id,
                    "source_problem_version": problem.version,
                    "catalog_version": catalog.version,
                },
            )

        org_rules = get_catalog_organization_rules()
        organized_candidates: list[DesignCandidate] = []
        cand_counter = 1

        for strategy in strategies:
            # Generate candidate(s) per strategy up to max_candidates_per_strategy
            for _ in range(min(1, config_obj.max_candidates_per_strategy)):
                cid = f"candidate-{cand_counter}"
                try:
                    raw_cand = generate_candidate_from_strategy(strategy, candidate_id=cid)
                    org_cand = organize_candidate(raw_cand, org_rules, problem=problem)
                except Exception:
                    continue

                lifecycle_manager.register_candidate(org_cand)
                lifecycle_manager.transition_state(
                    org_cand.id,
                    CandidateLifecycleState.ORGANIZED,
                    reason="Candidate generated and organized",
                )
                organized_candidates.append(org_cand)
                cand_counter += 1

        if not organized_candidates:
            empty_ranking = CandidateSelector.select(
                ranked_candidates=[],
                preference_catalog=catalog,
                max_selected=config_obj.max_selected,
                source_problem_id=problem.id,
                source_problem_version=problem.version,
            )
            return DesignOrchestrationResult(
                id=exec_id,
                source_problem_id=problem.id,
                source_problem_version=problem.version,
                ranking_result=empty_ranking,
                candidate_records=lifecycle_manager.get_all_records(),
                config_used=config_obj,
                execution_stats={
                    "total_strategies": len(strategies),
                    "total_candidates": 0,
                    "total_phase1_survivors": 0,
                    "total_phase1_pruned": 0,
                    "total_realized_successful": 0,
                    "total_realized_failed": 0,
                    "total_selected": 0,
                },
                provenance={
                    "orchestrator": "DesignOrchestrator",
                    "orchestration_version": "3B.6-5.v1",
                    "source_problem_id": problem.id,
                    "source_problem_version": problem.version,
                    "catalog_version": catalog.version,
                },
            )

        # PHASE B: Phase 1 Strategic Pre-Filtering & Pruning
        phase1_result = Phase1Pruner.score_and_prune(
            organized_candidates,
            problem,
            lifecycle_manager,
            config=config_obj,
            preference_catalog=catalog,
        )

        surviving_candidates = [
            c for c in organized_candidates if c.id in phase1_result.surviving_candidate_ids
        ]

        # PHASE C: Spatial Layout Realization & Phase 2 Post-Realization Scoring
        phase2_result = SpatialPhase2Orchestrator.realize_and_score(
            surviving_candidates,
            problem,
            lifecycle_manager,
            config=config_obj,
            preference_catalog=catalog,
        )

        # PHASE D: Final Scoring Combination, Ranking & Selection
        all_records = lifecycle_manager.get_all_records()
        ranked_candidates_input: list[RankedCandidate] = []

        for cand in organized_candidates:
            rec = all_records[cand.id]
            p1_score = rec.phase1_score
            p2_score = rec.phase2_score

            if p1_score is not None and p2_score is not None:
                comb_score = SpatialRealizationScorer.combine_score_breakdowns(
                    p1_score, p2_score, precision=precision
                )
            elif p1_score is not None:
                comb_score = p1_score
            else:
                comb_score = ScoreBreakdown(
                    criteria=[
                        CriterionScore(
                            criterion_id=c.id,
                            score=0.0,
                            weight=c.weight,
                            weighted_score=0.0,
                            explanation="No Phase 1 or Phase 2 score available",
                            source_ids=[],
                        )
                        for c in catalog.criteria
                    ],
                    total_score=0.0,
                    scoring_version=catalog.version,
                )

            lifecycle_manager.update_payloads(cand.id, combined_score=comb_score)

            rejection_reasons: list[str] = []
            if rec.lifecycle_state == CandidateLifecycleState.PRUNED_PRE_REALIZATION:
                initial_status = SelectionStatus.REJECTED
                rejection_reasons.append(
                    f"Pruned pre-realization: Phase 1 score below threshold {config_obj.phase1_prune_threshold}"
                )
            elif rec.lifecycle_state == CandidateLifecycleState.REALIZATION_FAILED:
                initial_status = SelectionStatus.REJECTED
                msg = rec.realization_result.error_message if rec.realization_result else "Spatial realization failed"
                rejection_reasons.append(f"Realization failed: {msg}")
            elif rec.lifecycle_state == CandidateLifecycleState.REJECTED:
                initial_status = SelectionStatus.REJECTED
                rejection_reasons.append("Rejected in upstream pipeline")
            else:
                initial_status = SelectionStatus.VIABLE

            crit_map = {c.criterion_id: c.score for c in comb_score.criteria}
            tb_values = [crit_map.get(cid, 0.0) for cid in catalog.tie_break.priority_criteria]
            tb_key = [comb_score.total_score] + tb_values + [cand.id]

            rc = RankedCandidate(
                candidate_id=cand.id,
                strategy_id=cand.source_strategy_id,
                rank=1,
                score_breakdown=comb_score,
                selection_status=initial_status,
                rejection_reasons=rejection_reasons,
                tie_break_key=tb_key,
                provenance={
                    "problem_id": problem.id,
                    "problem_version": problem.version,
                    "strategy_id": cand.source_strategy_id,
                    "candidate_id": cand.id,
                    "lifecycle_state": rec.lifecycle_state.value,
                },
            )
            ranked_candidates_input.append(rc)

        # CandidateSelector computes authoritative final ranks & selection status
        ranking_result = CandidateSelector.select(
            ranked_candidates=ranked_candidates_input,
            preference_catalog=catalog,
            max_selected=config_obj.max_selected,
            source_problem_id=problem.id,
            source_problem_version=problem.version,
        )

        # Update lifecycle manager states according to CandidateSelector decision
        for ranked_cand in ranking_result.ranked_candidates:
            rec = lifecycle_manager.get_record(ranked_cand.candidate_id)
            current_state = rec.lifecycle_state

            # Transition to RANKED first if valid from current_state
            if current_state != CandidateLifecycleState.RANKED and lifecycle_manager.is_valid_transition(current_state, CandidateLifecycleState.RANKED):
                lifecycle_manager.transition_state(
                    ranked_cand.candidate_id,
                    CandidateLifecycleState.RANKED,
                    reason=f"Candidate ranked #{ranked_cand.rank} with score {ranked_cand.score_breakdown.total_score:.{precision}f}",
                )

            # Apply final SELECTED or REJECTED state
            if ranked_cand.selection_status == SelectionStatus.SELECTED:
                lifecycle_manager.transition_state(
                    ranked_cand.candidate_id,
                    CandidateLifecycleState.SELECTED,
                    reason=f"Candidate selected at rank #{ranked_cand.rank}",
                )
            elif ranked_cand.selection_status == SelectionStatus.REJECTED:
                reasons_str = "; ".join(ranked_cand.rejection_reasons) or "Rejected by candidate selector"
                lifecycle_manager.reject_candidate(
                    ranked_cand.candidate_id,
                    reason=reasons_str,
                )

        final_records = lifecycle_manager.get_all_records()

        # PHASE E: Final Result Assembly
        execution_stats = {
            "total_strategies": len(strategies),
            "total_candidates": len(final_records),
            "total_phase1_survivors": len(phase1_result.surviving_candidate_ids),
            "total_phase1_pruned": len(phase1_result.pruned_candidate_ids),
            "total_realized_successful": len(phase2_result.successful_realization_ids),
            "total_realized_failed": len(phase2_result.failed_realization_ids),
            "total_realized_skipped": len(phase2_result.skipped_pruned_ids),
            "total_selected": len(ranking_result.selected_candidate_ids),
        }

        provenance = {
            "orchestrator": "DesignOrchestrator",
            "orchestration_version": "3B.6-5.v1",
            "source_problem_id": problem.id,
            "source_problem_version": problem.version,
            "catalog_version": catalog.version,
            "config": config_obj.model_dump(),
        }

        return DesignOrchestrationResult(
            id=exec_id,
            source_problem_id=problem.id,
            source_problem_version=problem.version,
            ranking_result=ranking_result,
            candidate_records=final_records,
            config_used=config_obj,
            execution_stats=execution_stats,
            provenance=provenance,
        )


def orchestrate_design(
    problem: DesignProblem,
    config: OrchestrationConfig | None = None,
    preference_catalog: PreferenceCatalog | None = None,
) -> DesignOrchestrationResult:
    """
    Module-level convenience function for DesignOrchestrator.run().
    """
    return DesignOrchestrator.run(
        problem,
        config=config,
        preference_catalog=preference_catalog,
    )
