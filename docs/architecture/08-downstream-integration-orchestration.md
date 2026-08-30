# BuildForgeAI Architecture — Downstream Integration & Orchestration Specification

**Phase**: 3 — Architectural Reasoning / Phase 7 — System Orchestration  
**Stage**: Stage 3B.6 — Downstream Integration & Orchestration  
**Document Status**: Canonical Architecture Specification — Stage 3B.6 Planned  

---

## 1. Purpose

Stage **3B.6 (Downstream Integration & Orchestration)** defines the computational architecture and orchestration service contract for binding together all upstream reasoning, candidate organization, spatial translation, 2D layout realization, multi-phase scoring, and candidate selection engines into a unified, deterministic, end-to-end design pipeline.

```text
Architectural Pipeline (Stage 3B.6 Orchestration Scope):
DesignProblem
    │
    ▼
ArchitecturalAnalysis (ArchitecturalAnalyzer)
    │
    ▼
DesignStrategy List (StrategyGenerator)
    │
    ▼
DesignCandidate List (CandidateGenerator)
    │
    ▼
Organized DesignCandidate List (CandidateOrganizer)
    │
    ▼
Phase 1 Abstract Scores (AbstractStrategicScorer) ──► Pre-Realization Pruning
    │
    ▼ (Surviving Candidates)
SpatialLayoutPlan List (CandidateToLayoutAdapter)
    │
    ▼
RealizationResult List (SpatialCompilerBridge -> solve_layout / compile_blueprint)
    │
    ▼
Phase 2 Spatial Scores (SpatialRealizationScorer)
    │
    ▼
Ranked & Selected Candidates (CandidateSelector -> RankingResult)
    │
    ▼
Orchestration Result (DesignOrchestrationResult)
```

### Key Orchestration Objectives:
1. **Pipeline Binding**: Connect independently implemented Stage 3B services (`ArchitecturalAnalyzer`, `StrategyGenerator`, `CandidateGenerator`, `CandidateOrganizer`, `CandidateToLayoutAdapter`, `SpatialCompilerBridge`, `AbstractStrategicScorer`, `SpatialRealizationScorer`, `CandidateSelector`) into a single entry point.
2. **State & Lifecycle Ownership**: Track each candidate through discrete lifecycle states without mutating authoritative domain objects.
3. **Structured Failure Propagation**: Ensure graceful, deterministic handling of invalid inputs, spatial infeasibilities, solver timeouts, and empty candidate pools without unhandled runtime exceptions.
4. **Lineage Preservation**: Maintain complete end-to-end provenance tracing from input `DesignProblem` through strategic reasoning down to final selected candidate layouts.
5. **Zero Redundancy**: Coordinate existing components without duplicating reasoning, geometry, solver, or ranking logic.

---

## 2. Current Architecture State

As of commit `facd567`, the BuildForgeAI codebase possesses a complete suite of decoupled, data-driven reasoning, realization, and ranking engines:

| Engine / Component | Stage | Source File | Status | Responsibilities |
|---|---|---|---|---|
| `DesignProblem` | 3B.1 | `app/schemas/design_problem.py` | Complete | Core problem specification contract (site, spaces, requirements, objectives, preferences). |
| `ArchitecturalAnalyzer` | 3B.2 | `app/services/analysis/architectural_analyzer.py` | Complete | Derives fixed/flexible decision dimensions, conflicts, and uncertainties. |
| `StrategyGenerator` | 3B.3C | `app/services/analysis/strategy_generator.py` | Complete | Generates conceptual `DesignStrategy` objects via Cartesian combinations over decision catalog. |
| `CandidateGenerator` | 3B.4A | `app/services/analysis/candidate_generator.py` | Complete | Instantiates structural `DesignCandidate` objects from strategies and analysis. |
| `CandidateOrganizer` | 3B.4C | `app/services/analysis/candidate_organizer.py` | Complete | Applies declarative `OrganizationRule` rules for floor tiers, unit containers, circulation, and wet cores. |
| `CandidateToLayoutAdapter` | 3B.4D-2 | `app/services/analysis/spatial_adapter.py` | Complete | Translates `DesignCandidate` into non-geometric `SpatialLayoutPlan`. |
| `SpatialCompilerBridge` | 3B.4D-3 | `app/services/realization/compiler_bridge.py` | Complete | Bridges `SpatialLayoutPlan` to legacy 2D compiler (`compile_blueprint`) and MILP solver (`solve_layout`). |
| `PreferenceCatalog` | 3B.5-2 | `app/services/analysis/preference_catalog.json` | Complete | Declarative criteria weights, normalization rules, and tie-breaking priorities. |
| `AbstractStrategicScorer` | 3B.5-3 | `app/services/ranking/abstract_strategic_scorer.py` | Complete | Phase 1 pre-realization strategic candidate scoring. |
| `SpatialRealizationScorer` | 3B.5-4 | `app/services/ranking/spatial_realization_scorer.py` | Complete | Phase 2 post-realization spatial evidence scoring. |
| `CandidateSelector` | 3B.5-5 | `app/services/ranking/candidate_selector.py` | Complete | Deterministic multi-criteria selection and tie-breaking engine. |

**Current Architectural Gap**: While each stage is fully implemented and tested independently (498 passing unit/migration/golden tests), there is currently no single orchestrator service that executes the full pipeline end-to-end from a `DesignProblem` input to a final `RankingResult` output. Stage 3B.6 fills this orchestration gap.

---

## 3. Scope & Boundary Rules

Stage 3B.6 is strictly an **Orchestration & Workflow Binding Layer**.

### What Stage 3B.6 MUST Own:
- Execution control flow and pipeline stage sequencing.
- Candidate lifecycle tracking and context management.
- Pre-realization Phase 1 pruning policies.
- Structured exception containment and partial-failure propagation.
- Pipeline-wide provenance and timing metadata aggregation.

### What Stage 3B.6 MUST NOT Become:
- MUST NOT implement a new reasoning engine or duplicate decision dimension logic.
- MUST NOT implement a new candidate generator or organizer.
- MUST NOT implement a new 2D/3D layout solver or placement algorithm.
- MUST NOT introduce Shapely, PuLP, CBC, or direct geometry manipulation.
- MUST NOT implement a new scoring or selection algorithm (must delegate to `AbstractStrategicScorer`, `SpatialRealizationScorer`, and `CandidateSelector`).
- MUST NOT introduce HTTP API routes, FastAPI endpoints, or web controllers (API integration remains out-of-scope for 3B.6).
- MUST NOT introduce external network clients or LLM dependencies in the execution loop.

---

## 4. Pipeline Overview & Execution Sequence

```text
                               ┌─────────────────────────┐
                               │   DesignProblem Input   │
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │  ArchitecturalAnalyzer  │
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │    StrategyGenerator    │
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │   CandidateGenerator    │
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │   CandidateOrganizer    │
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │ AbstractStrategicScorer │
                               └────────────┬────────────┘
                                            │
                             ┌──────────────┴──────────────┐
                             ▼                             ▼
                 [Phase 1 Score >= Prune]        [Phase 1 Score < Prune]
                             │                             │
                             ▼                             ▼
               ┌──────────────────────────┐    ┌──────────────────────────┐
               │ CandidateToLayoutAdapter │    │  Mark Candidate REJECTED │
               └─────────────┬────────────┘    └─────────────┬────────────┘
                             │                               │
                             ▼                               │
               ┌──────────────────────────┐                  │
               │  SpatialCompilerBridge   │                  │
               └─────────────┬────────────┘                  │
                             │                               │
                             ▼                               │
               ┌──────────────────────────┐                  │
               │ SpatialRealizationScorer │                  │
               └─────────────┬────────────┘                  │
                             │                               │
                             └──────────────┬────────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │    CandidateSelector    │
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │ DesignOrchestrationResult│
                               └─────────────────────────┘
```

---

## 5. Input & Output Contracts

Stage 3B.6 will define structured orchestration contracts in `backend/app/schemas/orchestration.py` (to be created during Stage 3B.6 implementation).

### Proposed Conceptual Schemas:

```python
class OrchestrationConfig(BaseModel):
    max_strategies: int = 10
    max_candidates_per_strategy: int = 5
    max_selected: int = 3
    phase1_prune_threshold: float = 0.30  # Candidates scoring below 0.30 in Phase 1 skip spatial realization
    enable_realization: bool = True       # Flag to allow fast pre-realization strategic-only evaluation
    solver_time_limit_sec: int = 5
    grid_snap: float = 0.5


class CandidateLifecycleState(str, Enum):
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


class OrchestrationCandidateRecord(BaseModel):
    candidate: DesignCandidate
    layout_plan: SpatialLayoutPlan | None = None
    realization_result: RealizationResult | None = None
    phase1_score: ScoreBreakdown | None = None
    phase2_score: ScoreBreakdown | None = None
    combined_score: ScoreBreakdown | None = None
    lifecycle_state: CandidateLifecycleState
    state_history: list[dict[str, Any]] = []


class DesignOrchestrationResult(BaseModel):
    id: str
    source_problem_id: str
    source_problem_version: int
    ranking_result: RankingResult
    candidate_records: dict[str, OrchestrationCandidateRecord]
    config_used: OrchestrationConfig
    execution_stats: dict[str, Any]  # Timings, counts, failure summary
    provenance: dict[str, Any]
```

---

## 6. Candidate Lifecycle Management

Each candidate progresses through a deterministic state machine managed by the orchestrator:

```text
[GENERATED] ──► [ORGANIZED] ──► [PHASE1_SCORED] ──┬──► (Score >= Prune) ──► [PLAN_ADAPTED] ──► [REALIZED / REALIZATION_FAILED] ──► [PHASE2_SCORED] ──► [RANKED] ──► [SELECTED / REJECTED]
                                                  │
                                                  └──► (Score < Prune)  ──► [PRUNED_PRE_REALIZATION] ───────────────────────────────────────────────► [RANKED] ──► [REJECTED]
```

### Transition Rules:
1. **Immutability**: Input domain objects (`DesignProblem`, `DesignCandidate`, `SpatialLayoutPlan`, `RealizationResult`) are NEVER mutated. The orchestrator wraps state in `OrchestrationCandidateRecord`.
2. **Traceability**: Every state transition appends a timestamp-free entry to `state_history` with transition name, status, and reason.
3. **No Loss of Candidates**: Pruned or failed candidates are NEVER dropped from `candidate_records`. They are preserved with explicit failure/rejection reasons for complete auditability.

---

## 7. Phase 1 Ranking Integration & Pre-Realization Pruning

Phase 1 abstract scoring (`AbstractStrategicScorer`) runs **BEFORE** spatial layout plan adaptation or MILP solver execution:

1. **Evaluation**: All organized candidates are evaluated against `DesignProblem` requirements, objectives, preferences, risks, and confidence.
2. **Threshold Evaluation**: If `candidate.phase1_score.total_score < config.phase1_prune_threshold` (default `0.30`), the orchestrator marks the candidate `PRUNED_PRE_REALIZATION`.
3. **Efficiency Gain**: Pruned candidates skip `CandidateToLayoutAdapter` and `SpatialCompilerBridge`, saving significant CPU time by avoiding unnecessary MILP solver calls.
4. **Ranking Inclusion**: Pruned candidates receive `selection_status = REJECTED` and are included at the bottom of the final `RankingResult` with reason `"Pruned pre-realization: Phase 1 score below threshold"`.

---

## 8. Spatial Realization Integration

For surviving candidates (`Phase 1 Score >= Prune`):

1. **Adaptation**: Candidate is passed to `CandidateToLayoutAdapter.adapt(candidate, problem)`. If adaptation fails or raises an error, candidate transitions to `REALIZATION_FAILED` with `INVALID_CANDIDATE` status.
2. **Realization**: `SpatialLayoutPlan` is passed to `SpatialCompilerBridge.realize_layout(plan, problem)`.
3. **Status Normalization**: `SpatialCompilerBridge` normalizes output into 1 of 6 statuses:
   - `SUCCESS`
   - `INVALID_CANDIDATE`
   - `UNSUPPORTED_SPEC`
   - `SPATIALLY_INFEASIBLE`
   - `SOLVER_TIMEOUT`
   - `SOLVER_ERROR`
4. **Safe Containment**: Solver exceptions are caught by `SpatialCompilerBridge` and returned as `RealizationResult(success=False, status=...)`. The orchestrator never crashes due to solver failures.

---

## 9. Phase 2 Ranking Integration

Post-realization scoring (`SpatialRealizationScorer`):

1. **Phase 2 Scoring**: `SpatialRealizationScorer.score_realization(candidate, problem, realization, catalog)` evaluates spatial layout evidence (room counts, area efficiency, core stacking, solver status).
2. **Score Combination**: `SpatialRealizationScorer.combine_score_breakdowns(phase1_score, phase2_score)` computes the weighted combined total score.
3. **Failed Realizations**: If `realization.success == False`, Phase 2 feasibility score is `0.0`, resulting in a low combined score and automatic `REJECTED` selection status.

---

## 10. Candidate Selection & Tie-Breaking

The orchestrator passes all scored candidates to `CandidateSelector.select()`:

1. **Multi-Criteria Combination**: Combines Phase 1 and Phase 2 score breakdowns.
2. **Threshold Assignment**: Categorizes candidates into `SELECTED`, `VIABLE`, `MARGINAL`, or `REJECTED` using `preference_catalog.json` thresholds (`selected_min_score`: 0.80, `viable_min_score`: 0.60, `marginal_min_score`: 0.40).
3. **Deterministic Cascade**: Breaks total score ties using declarative priority criteria (`program_usability` $\to$ `privacy_compliance` $\to$ `circulation_efficiency` $\to$ `service_core_stacking` $\to$ `realization_feasibility` $\to$ `objective_alignment`) followed by lexicographical candidate ID fallback.
4. **Max Selection Bounds**: Enforces `config.max_selected` (default 3), marking excess viable candidates as `VIABLE` with reason `"Exceeds max_selected limit"`.

---

## 11. Failure & Partial-Pipeline Model

The orchestrator must handle all failure modes gracefully:

| Failure Scenario | Stage | Orchestrator Action | Final Status |
|---|---|---|---|
| **Invalid DesignProblem** | Analysis | Catches validation error, produces empty `RankingResult` with explicit error in `provenance["error"]`. | Failed Run (Clean Result) |
| **Zero Strategies Generated** | Strategy Gen | Returns `RankingResult(ranked_candidates=[])` with reason `"No viable strategies generated"`. | Empty Result |
| **All Candidates Pruned (Phase 1)** | Ranking P1 | Ranks all pruned candidates as `REJECTED`. Bypasses spatial realization. Returns valid result. | All Rejected |
| **Spatial Infeasibility** | Realization | `RealizationResult(status=SPATIALLY_INFEASIBLE)`. Candidate scored with Phase 2 feasibility=0.0. Marked `REJECTED`. | Individual Rejection |
| **Solver Timeout / Error** | Realization | `RealizationResult(status=SOLVER_TIMEOUT)`. Marked `REJECTED`. Pipeline continues for remaining candidates. | Individual Rejection |
| **Partial Realization Success** | Realization | Successful candidates selected; failed candidates rejected. | Partial Selection |

**Guarding Rule**: Under NO circumstances should an individual candidate failure crash the pipeline for other candidates.

---

## 12. Provenance & Lineage Tracking

The orchestration result preserves full lineage:

```json
{
  "provenance": {
    "orchestrator": "DesignOrchestrator",
    "orchestrator_version": "3B.6.v1",
    "source_problem_id": "problem-44x42-benchmark",
    "source_problem_version": 1,
    "total_strategies_generated": 3,
    "total_candidates_generated": 6,
    "total_candidates_organized": 6,
    "total_phase1_pruned": 1,
    "total_realization_attempted": 5,
    "total_realization_successful": 4,
    "total_selected": 2,
    "selected_candidate_ids": ["cand-1", "cand-2"]
  }
}
```

---

## 13. Determinism & Precision Guarantees

1. **100% Deterministic Output**: Identical `DesignProblem` input and `OrchestrationConfig` yield identical JSON output across 50+ repeated executions.
2. **Fixed-Precision Floating-Point**: All scores rounded to 6 decimal places (`round(score, 6)`).
3. **Sorted Collection Iteration**: All dictionary keys and collection iterations are sorted deterministically by ID.
4. **No System Time or Randomness in Provenance**: Provenance metadata contains only deterministic counts, IDs, and versions (no `datetime.now()` or random UUIDs).

---

## 14. Batch & Multi-Candidate Processing Rules

1. **Multi-Strategy Bounding**: `StrategyGenerator` bounds generated strategies to `max_strategies` (default 10).
2. **Multi-Candidate Bounding**: `CandidateGenerator` bounds candidates per strategy to `max_candidates_per_strategy` (default 5).
3. **ID Uniqueness**: Duplicate candidate IDs across strategies are strictly rejected before scoring.
4. **Deduplication**: Candidates with identical decision fingerprints are deduplicated deterministically by `_compute_fingerprint()`.

---

## 15. Legacy Compatibility

The legacy compilation path (`CompilerIntent` $\rightarrow$ `to_design_problem` $\rightarrow$ `compile_blueprint` $\rightarrow$ `solve_layout`) remains fully operational:

1. **Coexistence**: Stage 3B.6 orchestration does NOT replace `compile_blueprint()` or `to_design_problem()`.
2. **Bridge Integration**: Orchestration uses `to_design_problem()` internally when given a legacy `CompilerIntent` input.
3. **Zero Deprecation Breakage**: Existing legacy tests in `test_intent_adapter.py` and `test_golden_spatial_realization.py` continue to pass without modification.

---

## 16. Dependency & Architectural Boundary Guards

| Boundary Constraint | Enforcement Mechanism |
|---|---|
| **No Solver Duplication** | Orchestration calls `SpatialCompilerBridge.realize_layout()`. Does NOT import or implement MILP solvers. |
| **No Geometry Leakage** | Orchestration handles Pydantic schema contracts only. Does NOT import Shapely, PyMOL, or CAD modules. |
| **No Domain Hardcoding** | Zero `if dimension == "..."` or `if value == "..."` branches. Evaluates criteria dynamically via `PreferenceCatalog`. |
| **No Network / External API** | Runs 100% offline. Zero requests to OpenAI, Gemini, or third-party APIs. |
| **No Unhandled Crashes** | All stage transitions wrapped in exception handling with structured failure logging into provenance. |

---

## 17. Proposed Stage 3B.6 Implementation Decomposition

Stage 3B.6 will be executed in 6 safe, incremental sub-stages:

- **Stage 3B.6-1: Pipeline Contracts & Schemas (`backend/app/schemas/orchestration.py`)** ⏳
  - Define `OrchestrationConfig`, `CandidateLifecycleState`, `OrchestrationCandidateRecord`, and `DesignOrchestrationResult`.
  - Unit tests: `test_orchestration_schema.py`.

- **Stage 3B.6-2: Candidate Lifecycle Manager (`backend/app/services/orchestration/lifecycle_manager.py`)** ⏳
  - Implement candidate record state tracking, transition validation, and non-mutating state history logging.
  - Unit tests: `test_lifecycle_manager.py`.

- **Stage 3B.6-3: Phase 1 Strategic Pre-Filtering & Pruning Orchestrator** ✅
  - Implement pipeline runner up to Phase 1 abstract strategic scoring and pre-realization pruning threshold enforcement.
  - Unit tests: `test_phase1_pruner.py`.

- **Stage 3B.6-4: Spatial Realization & Phase 2 Ranking Orchestrator** ✅
  - Implement spatial layout adaptation, bridge realization, Phase 2 spatial scoring, and score combination.
  - Unit tests: `test_spatial_phase2_orchestrator.py`.

- **Stage 3B.6-5: End-to-End Orchestrator Service (`backend/app/services/orchestration/design_orchestrator.py`)** ⏳
  - Implement `DesignOrchestrator.orchestrate(problem, config=None)` coordinating the full pipeline.
  - Unit tests: `test_design_orchestrator.py`.

- **Stage 3B.6-6: Golden End-to-End Test Fixtures & Regression Verification** ⏳
  - Create `golden_orchestration_fixtures.py` and `test_golden_orchestration.py` covering 12 end-to-end integration scenarios.
  - Run full regression suite across all 24 test modules.

---

## 18. Golden Integration Scenarios

The Stage 3B.6 golden test suite (`test_golden_orchestration.py`) will verify 12 end-to-end scenarios:

1. **Benchmark 44x42 / 4-Family**: Full end-to-end execution from problem to multi-unit selected ranking.
2. **Single-Family House**: Single-unit layout generation, Phase 1 & Phase 2 scoring, and selection.
3. **Shared Circulation Topology**: Multi-floor candidates with shared vertical stair cores.
4. **Independent Circulation Topology**: Multi-unit candidates with direct exterior access.
5. **Hybrid Circulation Topology**: Mixed entry access candidate pipeline execution.
6. **Multi-Floor Vertical Stacking**: 2+ floor plans verifying plumbing riser alignment.
7. **Centralized Service Core**: Wet stack core organization evaluation.
8. **Unseen Custom Dimensions**: Custom criteria (`solar_shading_strategy`, `facade_transparency`) flowing through orchestration without Python code changes.
9. **Realization Failure Handling**: Candidates with `SPATIALLY_INFEASIBLE` or `SOLVER_TIMEOUT` statuses gracefully rejected without crashing.
10. **Pre-Realization Pruning**: Low-scoring Phase 1 candidates pruned before spatial realization.
11. **Mixed Success / Failure Candidates**: Pipeline containing both successful and failed realizations selecting only valid candidates.
12. **No Viable Candidates Scenario**: Over-constrained problem producing zero viable candidates resulting in clean empty selection.

---

## 19. Testing Strategy

1. **Unit Tests**: Schema validation, state machine transitions, config default handling.
2. **Integration Tests**: Service-to-service boundary tests (`Analyzer` $\to$ `StrategyGen` $\to$ `CandidateGen` $\to$ `Organizer` $\to$ `Adapter` $\to$ `Bridge` $\to$ `Scorer` $\to$ `Selector`).
3. **Failure Propagation Tests**: Mocking solver timeouts and infeasibilities to verify clean error containment.
4. **Determinism Tests**: 50-iteration repeated orchestration execution assertions.
5. **AST Boundary Tests**: Confirming zero hardcoded criterion strings and zero solver/Shapely imports in `design_orchestrator.py`.
6. **Regression Tests**: Preserving 100% green status on all 498 existing Stage 3B.1-3B.5 tests.

---

## 20. Open Architectural Questions

Before executing Stage 3B.6 implementation, the following design questions should be resolved:

1. **Orchestrator Class Location**: Should the service reside in `backend/app/services/orchestration/design_orchestrator.py` or `backend/app/services/analysis/design_orchestrator.py`? (Recommended: `services/orchestration`).
2. **Default Pruning Threshold**: Is `phase1_prune_threshold = 0.30` optimal, or should Phase 1 pruning be disabled by default (`0.00`) to maximize realization coverage? (Recommended: `0.30` default, configurable via `OrchestrationConfig`).
3. **Candidate Record Return Policy**: Should `DesignOrchestrationResult` return full layout plans for all candidates, or only for selected/viable candidates to minimize payload size? (Recommended: return full layout plans for `SELECTED` and `VIABLE`, lightweight summaries for `REJECTED`).
4. **API Controller Placement**: When API routes are added in future phases, should they live in `backend/app/api/v1/endpoints/orchestration.py`? (Out-of-scope for 3B.6, but recommended for Phase 4 API integration).

---

## 21. Acceptance Criteria

Stage 3B.6 will be complete when:
- [ ] `orchestration.py` schemas defined (`OrchestrationConfig`, `DesignOrchestrationResult`, `CandidateLifecycleState`).
- [ ] `DesignOrchestrator.orchestrate()` executes full pipeline end-to-end from `DesignProblem` to `DesignOrchestrationResult`.
- [ ] Phase 1 pre-realization pruning skips spatial layout solver for low-scoring candidates when configured.
- [ ] Spatial realization failures (`SPATIALLY_INFEASIBLE`, `SOLVER_TIMEOUT`) are handled gracefully without unhandled exceptions.
- [ ] Complete lineage provenance preserved across all pipeline stages.
- [ ] Output is 100% deterministic across 50 repeated executions.
- [ ] AST checks confirm ZERO hardcoded domain `if/elif` branches and ZERO solver/geometry imports in orchestrator.
- [ ] All 12 golden orchestration scenarios pass cleanly.
- [ ] Full regression suite (500+ tests) passes 100% green.
