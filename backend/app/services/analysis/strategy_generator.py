"""
StrategyGenerator module for Stage 3B.3C.

Transforms ArchitecturalAnalysis (and optional DesignProblem) into a list of
coherent, non-geometric DesignStrategy objects.

Stage 3B.3C Architecture:
Pure Generic Data-Driven Strategy Generation Engine.
Legacy hardcoded archetype path removed.

Pipeline:
1. Alternative Discovery (from DecisionRecord.alternatives)
2. Bounded Combination Generation (Cartesian product over sorted flexible dimensions)
3. Generic Compatibility Filtering (via IncompatibilityRule and hard constraints)
4. Dynamic Trade-Off & Relationship Processing (from DimensionRelationship graph)
5. Fingerprint Deduplication
6. Deterministic Ordering & Strategy Bounding

Non-responsibilities:
- No geometry, coordinates, walls, bounding boxes, or CAD elements.
- No solver invocation (MILP, PuLP, CBC).
- No LLM / external API calls.
- No hardcoded architectural domain concepts (dimensions, values, archetypes).
"""

import itertools
from typing import Any

from app.schemas.architectural_analysis import (
    AnalysisSeverity,
    ArchitecturalAnalysis,
    DecisionDimension,
    DecisionRecord,
    DecisionStatus,
    DimensionRelationship,
    IncompatibilityRule,
    RelationshipImpact,
)
from app.schemas.design_problem import (
    Constraint,
    DesignProblem,
    Objective,
    Preference,
    Requirement,
)
from app.schemas.design_strategy import (
    DesignStrategy,
    FeasibilityExpectation,
    StrategyRisk,
    TradeOff,
)

MAX_CANDIDATE_COMBINATIONS = 100
DEFAULT_MAX_STRATEGIES = 10


def _parse_dimension(dim: Any) -> DecisionDimension | str:
    """Coerce string to DecisionDimension enum if valid, otherwise return string."""
    if isinstance(dim, DecisionDimension):
        return dim
    try:
        return DecisionDimension(str(dim))
    except ValueError:
        return str(dim)


def _dim_to_str(dim: Any) -> str:
    """Convert a decision dimension (Enum or str) to string representation."""
    if hasattr(dim, "value"):
        return str(dim.value)
    return str(dim)


def _compute_fingerprint(decisions: list[DecisionRecord]) -> str:
    """Compute a deterministic fingerprint string based on decision assignments."""
    sorted_decs = sorted(decisions, key=lambda d: (_dim_to_str(d.dimension), d.subject, str(d.value)))
    tokens = [f"{_dim_to_str(d.dimension)}:{d.subject}={d.value}" for d in sorted_decs]
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


def _extract_alternative_map(
    flexible_decisions: list[DecisionRecord],
) -> dict[str, tuple[DecisionRecord, list[Any]]]:
    """
    Extract candidate alternative choices for each flexible decision.
    Uses DecisionRecord.alternatives as the authoritative source.
    """
    alt_map: dict[str, tuple[DecisionRecord, list[Any]]] = {}

    for record in flexible_decisions:
        dim_key = _dim_to_str(record.dimension)
        if record.alternatives:
            sorted_alts = sorted(
                record.alternatives,
                key=lambda a: str(a) if not isinstance(a, dict) else str(sorted(a.items())),
            )
            alt_map[dim_key] = (record, sorted_alts)

    return alt_map


def _generate_candidate_combinations(
    alt_map: dict[str, tuple[DecisionRecord, list[Any]]],
    max_combinations: int = MAX_CANDIDATE_COMBINATIONS,
) -> list[dict[str, Any]]:
    """
    Generate bounded Cartesian product of alternatives across sorted flexible dimensions.
    Deterministic lexicographical ordering.
    """
    if not alt_map:
        return []

    sorted_dims = sorted(alt_map.keys())
    value_lists = [alt_map[dim][1] for dim in sorted_dims]

    combinations: list[dict[str, Any]] = []
    for raw_combo in itertools.product(*value_lists):
        combo_dict = {dim: val for dim, val in zip(sorted_dims, raw_combo)}
        combinations.append(combo_dict)
        if len(combinations) >= max_combinations:
            break

    return combinations


def _build_uncontested_hard_reqs(
    analysis: ArchitecturalAnalysis,
) -> dict[str, Any]:
    """
    Gather uncontested hard requirement dimension-value constraints generically.

    Only includes FIXED decisions that were sourced from explicit requirements
    (identified by their id prefix 'fixed-', as set by ArchitecturalAnalyzer).
    Site-dimension and program-definition decisions are intentionally excluded:
    their values (floor counts, plot dimensions) are not architectural choices
    that constrain the strategy combination space.

    No hardcoded RequirementKind branching.
    """
    conflicting_req_ids: set[str] = set()
    for conflict in analysis.conflicts:
        conflicting_req_ids.update(conflict.source_ids)

    uncontested: dict[str, Any] = {}
    for dec in analysis.fixed_decisions:
        if (
            dec.status == DecisionStatus.FIXED
            and dec.value is not None
            # Only requirement-derived fixed decisions carry a 'fixed-' id prefix
            and dec.id.startswith("fixed-")
            and not conflicting_req_ids.intersection(set(dec.source_ids))
        ):
            uncontested[_dim_to_str(dec.dimension)] = dec.value

    return uncontested



def _is_combination_compatible(
    combo: dict[str, Any],
    incompatibilities: list[IncompatibilityRule],
    uncontested_hard_reqs: dict[str, Any],
) -> bool:
    """
    Check combination against generic IncompatibilityRule pairs and uncontested hard requirements.
    No hardcoded domain logic.
    """
    # 1. IncompatibilityRules
    for rule in incompatibilities:
        dim_a = _dim_to_str(rule.dimension_a)
        dim_b = _dim_to_str(rule.dimension_b)
        if dim_a in combo and dim_b in combo:
            if combo[dim_a] == rule.value_a and combo[dim_b] == rule.value_b:
                return False

    # 2. Hard Requirements (from fixed decisions only, no RequirementKind branching)
    for req_dim, req_val in uncontested_hard_reqs.items():
        if req_dim in combo and combo[req_dim] != req_val:
            return False

    return True


def _derive_relationships_and_tradeoffs(
    combo: dict[str, Any],
    relationships: list[DimensionRelationship],
    source_ids: list[str],
) -> list[TradeOff]:
    """
    Dynamically construct TradeOff instances from declared DimensionRelationship instances matching assigned decision choices.
    Purely data-driven; zero domain string matching.
    """
    trade_offs: list[TradeOff] = []

    for rel in relationships:
        source_dim = _dim_to_str(rel.source_dimension)
        if source_dim in combo and combo[source_dim] == rel.source_value:
            improved = _parse_dimension(rel.target) if rel.impact == RelationshipImpact.IMPROVES else _parse_dimension("baseline")
            reduced = _parse_dimension(rel.target) if rel.impact in (RelationshipImpact.REDUCES, RelationshipImpact.CONSTRAINS) else _parse_dimension("unconstrained")

            trade_offs.append(
                TradeOff(
                    id=f"tradeoff-{rel.id}",
                    improved_dimension=improved,
                    reduced_dimension=reduced,
                    explanation=rel.explanation,
                    source_ids=rel.source_ids or source_ids,
                    severity=rel.severity,
                    accepted=True,
                )
            )

    return trade_offs


def generate_strategies(
    analysis: ArchitecturalAnalysis,
    problem: DesignProblem | None = None,
    max_strategies: int = DEFAULT_MAX_STRATEGIES,
) -> list[DesignStrategy]:
    """
    Generate a list of coherent, non-geometric DesignStrategy objects from an ArchitecturalAnalysis.

    Stage 3B.3C: Pure generic data-driven algorithm. Legacy hardcoded archetype path removed.
    Architectural domain knowledge (alternatives, incompatibilities, relationships) must be
    supplied via ArchitecturalAnalysis, populated from the declarative Decision Catalog by
    the ArchitecturalAnalyzer.
    """
    problem_id = analysis.problem_id
    problem_version = analysis.problem_version
    analysis_id = str(analysis.provenance.get("analysis_id", f"analysis-{problem_id}"))

    req_satisfied, constraints_addressed, pref_supported, obj_targeted = _extract_source_ids(analysis)

    fixed_decisions = list(analysis.fixed_decisions)
    fixed_dims = {_dim_to_str(dec.dimension) for dec in fixed_decisions}

    flexible_records = list(analysis.flexible_decisions)
    flexible_dims = [_dim_to_str(dec.dimension) for dec in flexible_records if _dim_to_str(dec.dimension) not in fixed_dims]

    # Collect uncontested hard constraints generically from fixed decisions
    uncontested_hard_reqs = _build_uncontested_hard_reqs(analysis)

    # Extract dynamic alternatives map from DecisionRecord.alternatives
    alt_map = _extract_alternative_map(flexible_records)

    # =========================================================================
    # GENERIC DATA-DRIVEN ENGINE
    # Enumerate Cartesian combinations over all declared alternatives.
    # =========================================================================
    raw_candidate_specs: list[dict[str, Any]] = []

    combinations = _generate_candidate_combinations(alt_map, max_combinations=MAX_CANDIDATE_COMBINATIONS)

    for combo_idx, combo in enumerate(combinations, start=1):
        if not _is_combination_compatible(combo, analysis.incompatibilities, uncontested_hard_reqs):
            continue

        combo_summary = ", ".join(f"{dim}={val}" for dim, val in sorted(combo.items()))
        raw_candidate_specs.append({
            "name": f"Strategy Option {combo_idx} ({combo_summary})",
            "approach": f"Generic architectural approach implementing assignments: {combo_summary}.",
            "decision_assignments": combo,
        })

    # =========================================================================
    # BUILD STRATEGY OBJECTS
    # =========================================================================
    candidate_strategies: list[DesignStrategy] = []
    seen_fingerprints: set[str] = set()

    for spec_idx, spec in enumerate(raw_candidate_specs, start=1):
        assignments: dict[str, Any] = spec["decision_assignments"]

        # Build strategy decisions list
        strategy_decisions: list[DecisionRecord] = list(fixed_decisions)
        assigned_dims: set[str] = {_dim_to_str(d.dimension) for d in fixed_decisions}

        for dim_str, val in assignments.items():
            parsed_dim = _parse_dimension(dim_str)
            if dim_str not in assigned_dims:
                strategy_decisions.append(
                    DecisionRecord(
                        id=f"strategy-decision-{dim_str}",
                        dimension=parsed_dim,
                        subject="building",
                        value=val,
                        source_ids=[],
                        status=DecisionStatus.DERIVED,
                        rationale=f"Assigned choice '{val}' for strategy '{spec['name']}'.",
                    )
                )
                assigned_dims.add(dim_str)

        # Remaining flexible dimensions (not assigned in this combination)
        remaining_flexible = [_parse_dimension(d) for d in flexible_dims if d not in assigned_dims]

        # Fingerprint & Deduplication
        fingerprint = _compute_fingerprint(strategy_decisions)
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)

        # Build Trade-offs from declared DimensionRelationship data only
        trade_offs: list[TradeOff] = _derive_relationships_and_tradeoffs(
            assignments, analysis.relationships, pref_supported + obj_targeted
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
            f"Key decision assignments: {', '.join(f'{d}={v}' for d, v in assignments.items() if d in assigned_dims and d not in fixed_dims)}.",
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
                "generator": "deterministic-data-driven",
                "source_problem_id": problem_id,
                "source_analysis_id": analysis_id,
                "fingerprint": fingerprint,
            },
        )
        candidate_strategies.append(strategy_obj)

    # Baseline fallback if no combinations were available (no alternatives declared)
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
            flexible_decisions=[_parse_dimension(d) for d in flexible_dims],
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
                "generator": "deterministic-data-driven",
                "source_problem_id": problem_id,
                "source_analysis_id": analysis_id,
                "fingerprint": fingerprint,
            },
        )
        candidate_strategies.append(baseline)

    # Sort strategies deterministically by fingerprint
    candidate_strategies.sort(key=lambda s: str(s.provenance.get("fingerprint", s.name)))

    # Re-assign sequential IDs to guarantee deterministic strategy-1, strategy-2, ...
    final_strategies: list[DesignStrategy] = []
    for idx, strat in enumerate(candidate_strategies[:max_strategies], start=1):
        strat_dict = strat.model_dump()
        strat_dict["id"] = f"strategy-{idx}"
        strat_dict["provenance"]["strategy_count"] = min(len(candidate_strategies), max_strategies)
        final_strategies.append(DesignStrategy.model_validate(strat_dict))

    return final_strategies
