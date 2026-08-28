"""
StrategyGenerator module for Stage 3B.2.

Transforms ArchitecturalAnalysis (and optional DesignProblem) into a list of
coherent, non-geometric DesignStrategy objects.

Architectural reasoning:
ArchitecturalAnalysis answers: "What architectural decisions exist?"
StrategyGenerator answers: "What coherent architectural approaches could resolve those decisions?"

Responsibilities:
- Identify decision dimensions and available alternatives from input analysis.
- Build coherent architectural strategy combinations.
- Preserve source requirement, constraint, preference, and objective IDs.
- Handle conflicts, trade-offs, risks, and uncertainties explicitly.
- Filter contradictory combinations that violate hard requirements.
- Deduplicate equivalent strategies.
- Enforce maximum strategy limit deterministically.
- Maintain strict non-responsibilities (no geometry, solver, CAD, LLM, etc.).
"""

from typing import Any

from app.schemas.architectural_analysis import (
    AnalysisSeverity,
    ArchitecturalAnalysis,
    ConflictRecord,
    DecisionDimension,
    DecisionRecord,
    DecisionStatus,
    DependencyRecord,
    UncertaintyRecord,
)
from app.schemas.design_problem import (
    Constraint,
    DesignProblem,
    Objective,
    Preference,
    Requirement,
    RequirementKind,
    RequirementStrength,
)
from app.schemas.design_strategy import (
    DesignStrategy,
    FeasibilityExpectation,
    StrategyRisk,
    TradeOff,
)

DEFAULT_MAX_STRATEGIES = 10
"""
Default maximum strategy limit: 10.

Reasoning:
When an ArchitecturalAnalysis contains multiple flexible decision dimensions
(e.g., vertical circulation, unit organization, entrance strategy, shared/private strategy),
naively computing the Cartesian product of all possible values can lead to exponential
growth (e.g. 5 dimensions x 4 values = 1024 combinations).
Bounding strategy generation to a configurable limit (default 10) prevents combinatorial
explosion while ensuring a diverse, distinct, and coherent set of architectural options.
"""


def _compute_fingerprint(decisions: list[DecisionRecord]) -> str:
    """Compute a deterministic fingerprint string based on meaningful decision assignments."""
    sorted_decs = sorted(decisions, key=lambda d: (d.dimension.value, d.subject, str(d.value)))
    tokens = [f"{d.dimension.value}:{d.subject}={d.value}" for d in sorted_decs]
    return "|".join(tokens)


def _extract_source_ids(analysis: ArchitecturalAnalysis) -> tuple[list[str], list[str], list[str], list[str]]:
    """Extract satisfied requirement IDs, addressed constraint IDs, supported preference IDs, and targeted objective IDs."""
    req_ids: set[str] = set()
    constraint_ids: set[str] = set()
    pref_ids: set[str] = set()
    obj_ids: set[str] = set()

    for hc in analysis.hard_constraints:
        if isinstance(hc, Requirement):
            req_ids.add(hc.id)
        elif isinstance(hc, Constraint):
            constraint_ids.add(hc.id)

    for sp in analysis.soft_preferences:
        if isinstance(sp, Requirement):
            req_ids.add(sp.id)
        elif isinstance(sp, Preference):
            pref_ids.add(sp.id)

    for obj in analysis.objectives:
        if isinstance(obj, Objective):
            obj_ids.add(obj.id)

    for dec in analysis.fixed_decisions:
        for sid in dec.source_ids:
            if not sid.startswith("site."):
                req_ids.add(sid)

    return sorted(req_ids), sorted(constraint_ids), sorted(pref_ids), sorted(obj_ids)


def generate_strategies(
    analysis: ArchitecturalAnalysis,
    problem: DesignProblem | None = None,
    max_strategies: int = DEFAULT_MAX_STRATEGIES,
) -> list[DesignStrategy]:
    """
    Generate a list of coherent, non-geometric DesignStrategy objects from an ArchitecturalAnalysis.

    Parameters:
    - analysis: ArchitecturalAnalysis object containing decisions, constraints, conflicts, etc.
    - problem: Optional DesignProblem for traceability and source metadata.
    - max_strategies: Conservative upper bound on generated strategies to prevent combinatorial explosion.

    Returns:
    - list[DesignStrategy]: Structurally valid, deterministic, deduplicated architectural strategies.
    """
    problem_id = analysis.problem_id
    problem_version = analysis.problem_version
    analysis_id = str(analysis.provenance.get("analysis_id", f"analysis-{problem_id}"))

    req_satisfied, constraints_addressed, pref_supported, obj_targeted = _extract_source_ids(analysis)

    fixed_decisions = list(analysis.fixed_decisions)
    fixed_dimensions = {dec.dimension for dec in fixed_decisions}

    flexible_records = list(analysis.flexible_decisions)
    flexible_dims = [dec.dimension for dec in flexible_records if dec.dimension not in fixed_dimensions]

    # Collect hard requirements for constraint checking
    uncontested_hard_reqs: dict[DecisionDimension, Any] = {}
    conflicting_req_ids: set[str] = set()
    for conflict in analysis.conflicts:
        conflicting_req_ids.update(conflict.source_ids)

    for hc in analysis.hard_constraints:
        if isinstance(hc, Requirement) and hc.id not in conflicting_req_ids:
            if hc.kind == RequirementKind.CIRCULATION:
                uncontested_hard_reqs[DecisionDimension.VERTICAL_CIRCULATION] = hc.value
                uncontested_hard_reqs[DecisionDimension.CIRCULATION] = hc.value
            elif hc.kind == RequirementKind.PRIVACY:
                uncontested_hard_reqs[DecisionDimension.PRIVACY] = hc.value

    # Determine candidate archetypes / combinations
    raw_candidate_specs: list[dict[str, Any]] = []

    has_flexible_circulation = (
        DecisionDimension.VERTICAL_CIRCULATION in flexible_dims
        or DecisionDimension.CIRCULATION in flexible_dims
        or DecisionDimension.ENTRANCE_STRATEGY in flexible_dims
    )

    has_flexible_unit_org = (
        DecisionDimension.UNIT_ORGANIZATION in flexible_dims
        or DecisionDimension.FLOOR_ALLOCATION in flexible_dims
    )

    # 1. Conflict-Driven Strategies
    if analysis.conflicts:
        for conflict in analysis.conflicts:
            # Generate resolution strategies for each conflict option
            # Option 1: Favor first side of conflict
            raw_candidate_specs.append({
                "name": f"Strategy favoring {conflict.source_ids[0] if conflict.source_ids else 'Option 1'}",
                "approach": f"Resolves conflict ({conflict.id}) by prioritizing requirement {conflict.source_ids[0] if conflict.source_ids else '1'}.",
                "decision_assignments": {
                    DecisionDimension.VERTICAL_CIRCULATION: "shared" if "shared" in conflict.explanation.lower() else "independent",
                    DecisionDimension.ENTRANCE_STRATEGY: "shared" if "shared" in conflict.explanation.lower() else "independent",
                    DecisionDimension.SHARED_PRIVATE_STRATEGY: "shared_services",
                },
                "conflict_id": conflict.id,
                "conflict_resolution": "option_1",
            })
            # Option 2: Favor second side of conflict
            raw_candidate_specs.append({
                "name": f"Strategy favoring {conflict.source_ids[1] if len(conflict.source_ids) > 1 else 'Option 2'}",
                "approach": f"Resolves conflict ({conflict.id}) by prioritizing requirement {conflict.source_ids[1] if len(conflict.source_ids) > 1 else '2'}.",
                "decision_assignments": {
                    DecisionDimension.VERTICAL_CIRCULATION: "independent",
                    DecisionDimension.ENTRANCE_STRATEGY: "independent",
                    DecisionDimension.SHARED_PRIVATE_STRATEGY: "independent_services",
                },
                "conflict_id": conflict.id,
                "conflict_resolution": "option_2",
            })
            # Option 3: Compromise / Hybrid
            raw_candidate_specs.append({
                "name": "Hybrid Conflict Resolution Strategy",
                "approach": f"Provides a hybrid compromise resolving conflict ({conflict.id}) with controlled access thresholds.",
                "decision_assignments": {
                    DecisionDimension.VERTICAL_CIRCULATION: "hybrid",
                    DecisionDimension.ENTRANCE_STRATEGY: "controlled_shared",
                    DecisionDimension.SHARED_PRIVATE_STRATEGY: "hybrid_services",
                },
                "conflict_id": conflict.id,
                "conflict_resolution": "hybrid",
            })

    # 2. Archetype Strategies (Shared, Independent, Hybrid, Compact)
    if flexible_dims and (has_flexible_circulation or has_flexible_unit_org or not raw_candidate_specs):
        raw_candidate_specs.extend([
            {
                "name": "Shared Circulation & Central Service Strategy",
                "approach": "Organize building around a single shared vertical circulation core and central service infrastructure to maximize area efficiency.",
                "decision_assignments": {
                    DecisionDimension.VERTICAL_CIRCULATION: "shared",
                    DecisionDimension.CIRCULATION: "shared",
                    DecisionDimension.ENTRANCE_STRATEGY: "shared",
                    DecisionDimension.SHARED_PRIVATE_STRATEGY: "shared_services",
                    DecisionDimension.UNIT_ORGANIZATION: "stacked",
                    DecisionDimension.SERVICE_CORE_STRATEGY: "centralized",
                },
                "archetype": "shared",
            },
            {
                "name": "Independent Circulation & Privacy Strategy",
                "approach": "Provide independent vertical circulation and private entrances per unit or user group to maximize privacy and autonomy.",
                "decision_assignments": {
                    DecisionDimension.VERTICAL_CIRCULATION: "independent",
                    DecisionDimension.CIRCULATION: "independent",
                    DecisionDimension.ENTRANCE_STRATEGY: "independent",
                    DecisionDimension.SHARED_PRIVATE_STRATEGY: "independent_services",
                    DecisionDimension.UNIT_ORGANIZATION: "distributed",
                    DecisionDimension.SERVICE_CORE_STRATEGY: "decentralized",
                },
                "archetype": "independent",
            },
            {
                "name": "Hybrid Circulation & Controlled Access Strategy",
                "approach": "Combine a primary shared entrance core with controlled access points, balancing spatial efficiency with unit privacy.",
                "decision_assignments": {
                    DecisionDimension.VERTICAL_CIRCULATION: "hybrid",
                    DecisionDimension.CIRCULATION: "hybrid",
                    DecisionDimension.ENTRANCE_STRATEGY: "controlled_shared",
                    DecisionDimension.SHARED_PRIVATE_STRATEGY: "hybrid_services",
                    DecisionDimension.UNIT_ORGANIZATION: "grouped",
                    DecisionDimension.SERVICE_CORE_STRATEGY: "hybrid_core",
                },
                "archetype": "hybrid",
            },
        ])

    # 3. Ground Floor / Single Family / Multi-Floor Variations
    if DecisionDimension.FLOOR_ALLOCATION in flexible_dims:
        raw_candidate_specs.append({
            "name": "Ground-Floor-Focused Strategy",
            "approach": "Prioritize primary living and accessible spaces on the ground floor while utilizing upper levels for secondary spaces.",
            "decision_assignments": {
                DecisionDimension.FLOOR_ALLOCATION: "ground_floor_only",
                DecisionDimension.UNIT_ORGANIZATION: "ground_floor_focused",
            },
            "archetype": "ground_floor",
        })
        raw_candidate_specs.append({
            "name": "Distributed Multi-Floor Strategy",
            "approach": "Distribute space allocations evenly across all available floors for vertical balance.",
            "decision_assignments": {
                DecisionDimension.FLOOR_ALLOCATION: "distributed",
                DecisionDimension.UNIT_ORGANIZATION: "stacked",
            },
            "archetype": "distributed_floors",
        })

    # Build DesignStrategy objects from candidate specs
    candidate_strategies: list[DesignStrategy] = []
    seen_fingerprints: set[str] = set()

    for spec_idx, spec in enumerate(raw_candidate_specs, start=1):
        assignments: dict[DecisionDimension, Any] = spec["decision_assignments"]

        # Check hard constraint violations
        violates_hard_constraint = False
        for dim, req_val in uncontested_hard_reqs.items():
            if dim in assignments and assignments[dim] != req_val:
                violates_hard_constraint = True
                break
        if violates_hard_constraint:
            continue

        # Build strategy decisions list
        strategy_decisions: list[DecisionRecord] = list(fixed_decisions)
        assigned_dims: set[DecisionDimension] = {d.dimension for d in fixed_decisions}

        for dim, val in assignments.items():
            if dim in flexible_dims or dim in analysis.decision_dimensions:
                if dim not in assigned_dims:
                    strategy_decisions.append(
                        DecisionRecord(
                            id=f"strategy-decision-{dim.value}",
                            dimension=dim,
                            subject="building",
                            value=val,
                            source_ids=[],
                            status=DecisionStatus.DERIVED,
                            rationale=f"Assigned conceptual choice '{val}' for strategy '{spec['name']}'.",
                        )
                    )
                    assigned_dims.add(dim)

        # Remaining flexible dimensions
        remaining_flexible = [d for d in flexible_dims if d not in assigned_dims]

        # Fingerprint & Deduplication
        fingerprint = _compute_fingerprint(strategy_decisions)
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)

        # Build Trade-offs
        trade_offs: list[TradeOff] = []
        vert_circ = assignments.get(DecisionDimension.VERTICAL_CIRCULATION)
        if vert_circ == "independent":
            trade_offs.append(
                TradeOff(
                    id="tradeoff-privacy-circulation",
                    improved_dimension=DecisionDimension.PRIVACY,
                    reduced_dimension=DecisionDimension.CIRCULATION,
                    explanation="Independent circulation cores increase user privacy but require additional circulation area.",
                    source_ids=pref_supported + obj_targeted,
                    severity=AnalysisSeverity.WARNING,
                    accepted=True,
                )
            )
        elif vert_circ == "shared":
            trade_offs.append(
                TradeOff(
                    id="tradeoff-efficiency-privacy",
                    improved_dimension=DecisionDimension.CIRCULATION,
                    reduced_dimension=DecisionDimension.PRIVACY,
                    explanation="Shared vertical circulation minimizes core footprint but increases shared access interactions.",
                    source_ids=pref_supported + obj_targeted,
                    severity=AnalysisSeverity.INFO,
                    accepted=True,
                )
            )
        elif vert_circ == "hybrid":
            trade_offs.append(
                TradeOff(
                    id="tradeoff-hybrid-balance",
                    improved_dimension=DecisionDimension.PRIVACY,
                    reduced_dimension=DecisionDimension.CIRCULATION,
                    explanation="Hybrid circulation balances private thresholds with shared core efficiency.",
                    source_ids=pref_supported + obj_targeted,
                    severity=AnalysisSeverity.INFO,
                    accepted=True,
                )
            )

        # Build Risks
        risks: list[StrategyRisk] = []
        for concern in analysis.feasibility_concerns:
            risks.append(
                StrategyRisk(
                    id=f"risk-{concern.id}",
                    description=concern.description,
                    severity=concern.severity,
                    source_ids=concern.source_ids,
                )
            )

        if vert_circ == "independent":
            risks.append(
                StrategyRisk(
                    id="risk-area-duplication",
                    description="Multiple circulation cores increase gross building area requirements.",
                    severity=AnalysisSeverity.WARNING,
                    source_ids=[],
                )
            )

        # Build Assumptions
        assumptions: list[str] = []
        for uncertainty in analysis.uncertainties:
            assumptions.append(f"Assumes {uncertainty.topic}: {uncertainty.description}")

        if not assumptions:
            assumptions.append("Assumes standard site access and regulatory compliance.")

        # Feasibility Expectation
        if any(c.severity == AnalysisSeverity.BLOCKING for c in analysis.feasibility_concerns):
            feasibility = FeasibilityExpectation.BLOCKED
        elif any(u.required_for_strategy for u in analysis.uncertainties):
            feasibility = FeasibilityExpectation.CONDITIONALLY_FEASIBLE
        else:
            feasibility = FeasibilityExpectation.EXPECTED_FEASIBLE

        # Rationale
        rationale_lines = [
            f"Strategy '{spec['name']}' addresses the design problem through a conceptual approach of: {spec['approach']}",
            f"Key conceptual decision assignments: {', '.join(f'{d.value}={v}' for d, v in assignments.items() if d in assigned_dims and d not in fixed_dimensions)}.",
        ]
        if trade_offs:
            rationale_lines.append(f"Introduces explicit trade-off: {trade_offs[0].explanation}")
        if assumptions:
            rationale_lines.append(f"Depends on {len(assumptions)} explicit assumption(s).")
        rationale = " ".join(rationale_lines)

        strategy_obj = DesignStrategy(
            id=f"strategy-{len(candidate_strategies) + 1}",
            source_problem_id=problem_id,
            source_problem_version=problem_version,
            source_analysis_id=analysis_id,
            name=spec["name"],
            approach=spec["approach"],
            decisions=strategy_decisions,
            flexible_decisions=remaining_flexible,
            requirements_satisfied=req_satisfied,
            constraints_addressed=constraints_addressed,
            preferences_supported=pref_supported,
            objectives_targeted=obj_targeted,
            trade_offs=trade_offs,
            dependencies=list(analysis.dependencies),
            risks=risks,
            assumptions=assumptions,
            feasibility_expectation=feasibility,
            rationale=rationale,
            confidence=0.85 if feasibility == FeasibilityExpectation.EXPECTED_FEASIBLE else 0.70,
            provenance={
                "generator": "deterministic-rule-based",
                "source_problem_id": problem_id,
                "source_analysis_id": analysis_id,
                "fingerprint": fingerprint,
            },
        )
        candidate_strategies.append(strategy_obj)

    # If no strategies generated (e.g. empty flexible decisions and no archetypes matched), create 1 baseline strategy
    if not candidate_strategies:
        fingerprint = _compute_fingerprint(fixed_decisions)
        baseline = DesignStrategy(
            id="strategy-1",
            source_problem_id=problem_id,
            source_problem_version=problem_version,
            source_analysis_id=analysis_id,
            name="Baseline Design Strategy",
            approach="Baseline architectural organization incorporating all fixed decisions.",
            decisions=fixed_decisions,
            flexible_decisions=flexible_dims,
            requirements_satisfied=req_satisfied,
            constraints_addressed=constraints_addressed,
            preferences_supported=pref_supported,
            objectives_targeted=obj_targeted,
            trade_offs=[],
            dependencies=list(analysis.dependencies),
            risks=[],
            assumptions=[f"Assumes {u.topic}: {u.description}" for u in analysis.uncertainties] or ["Baseline assumptions apply."],
            feasibility_expectation=FeasibilityExpectation.EXPECTED_FEASIBLE,
            rationale="Baseline strategy derived directly from fixed decisions in the ArchitecturalAnalysis.",
            confidence=0.9,
            provenance={
                "generator": "deterministic-rule-based",
                "source_problem_id": problem_id,
                "source_analysis_id": analysis_id,
                "fingerprint": fingerprint,
            },
        )
        candidate_strategies.append(baseline)

    # Sort strategies deterministically by fingerprint before assigning final sequential IDs
    candidate_strategies.sort(key=lambda s: str(s.provenance.get("fingerprint", s.name)))

    # Re-assign sequential IDs to guarantee deterministic ordering strategy-1, strategy-2, ...
    final_strategies: list[DesignStrategy] = []
    for idx, strat in enumerate(candidate_strategies[:max_strategies], start=1):
        strat_dict = strat.model_dump()
        strat_dict["id"] = f"strategy-{idx}"
        strat_dict["provenance"]["strategy_count"] = min(len(candidate_strategies), max_strategies)
        final_strategies.append(DesignStrategy.model_validate(strat_dict))

    return final_strategies
