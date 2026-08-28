# BuildForgeAI Architecture — Generic Strategy Generation Engine

**Phase**: 3 — Architectural Reasoning  
**Stage**: 3B.3 — Generic Data-Driven Strategy Generation  
**Document Status**: Canonical Architecture Specification — Stage 3B.3C Complete  

---

## 1. Overview & Architectural Goals

The **Strategy Generation Engine** transforms an `ArchitecturalAnalysis` into a list of coherent, non-geometric `DesignStrategy` objects. 

In **Stage 3B.2**, the baseline infrastructure established core operational capabilities: requirement traceability, constraint filtering, uncertainty propagation, fingerprint deduplication, deterministic ordering, and strategy limit bounding.

In **Stage 3B.3**, the generation mechanism transitions from hardcoded domain archetype logic to a **pure data-driven reasoning engine**. 

### The Core Architectural Shift:

```text
BEFORE (Stage 3B.2 Baseline):
ArchitecturalAnalysis → Hardcoded Dimension Checks (if circulation / entrance) → Predefined Strategy Templates

AFTER (Stage 3B.3 Generic Engine):
ArchitecturalAnalysis → Generic Alternative Discovery → Bounded Cartesian Combination → Data-Driven Relationship Evaluation → DesignStrategy[]
```

The generator contains **zero hardcoded domain rules** about specific building elements (e.g. staircases, entrances, courtyards). Domain semantics live strictly in the input `ArchitecturalAnalysis` contract, allowing the generator to construct coherent strategy alternatives for **unseen architectural decision dimensions without code modification**.

---

## 2. Refined Data Contracts (`ArchitecturalAnalysis`)

To ensure structural safety without using unstructured buckets (`provenance["..."]`) or unconstrained `Any` types, decision values and alternatives are governed by explicit, typed, serializable contracts.

### A. Constrained Decision Values

All decision values and alternative candidates must conform to serializable, non-geometric primitives:

```python
# Allowed types for decision values and candidate alternatives:
# - Primitive scalars: str, int, float, bool
# - Canonical dictionaries: dict[str, str | int | float | bool]
# STRICTLY FORBIDDEN: Geometry objects (polygons, meshes, coordinates, CAD elements), solver instances, arbitrary un-serializable objects.
```

### B. `DecisionRecord` Schema Extension (`alternatives`)

A `DecisionRecord` representing a flexible decision explicitly declares its available candidate choices:

```python
class DecisionRecord(BaseModel):
    id: str
    dimension: DecisionDimension | str
    subject: str = "building"
    value: str | int | float | bool | dict[str, Any] | None = None
    alternatives: list[str | int | float | bool | dict[str, Any]] = Field(
        default_factory=list,
        description="Candidate choices available when this decision dimension is flexible."
    )
    source_ids: list[str] = Field(default_factory=list)
    status: DecisionStatus = DecisionStatus.UNRESOLVED
    rationale: str | None = None
```

### C. `IncompatibilityRule` Schema

Represents incompatible pairings between decisions across different dimensions:

```python
class IncompatibilityRule(BaseModel):
    id: str
    dimension_a: str
    value_a: str | int | float | bool
    dimension_b: str
    value_b: str | int | float | bool
    explanation: str
    source_ids: list[str] = Field(default_factory=list)
```

### D. `DimensionRelationship` Schema

Represents declared domain relationships between decision values and design objectives or other dimensions:

```python
class RelationshipImpact(str, Enum):
    IMPROVES = "improves"
    REDUCES = "reduces"
    CONSTRAINS = "constrains"
    DEPENDS_ON = "depends_on"

class DimensionRelationship(BaseModel):
    id: str
    source_dimension: str
    source_value: str | int | float | bool
    target: str
    impact: RelationshipImpact
    explanation: str
    severity: AnalysisSeverity = AnalysisSeverity.INFO
    source_ids: list[str] = Field(default_factory=list)
```

---

## 3. Generic Strategy Generation Engine Pipeline

The `StrategyGenerator` executes a 6-step data-driven pipeline:

```text
ArchitecturalAnalysis
        ↓
1. Alternative Discovery & Combination Enumeration
        ↓
2. Incompatibility & Constraint Filtering
        ↓
3. Dynamic Trade-Off & Risk Derivation
        ↓
4. Fingerprinting & Deduplication
        ↓
5. Deterministic Ordering & Strategy Bounding
        ↓
DesignStrategy[]
```

### Step 1: Alternative Discovery & Combination Enumeration
1. Extract fixed decisions from `analysis.fixed_decisions`.
2. Extract flexible dimensions and their `alternatives` from `analysis.flexible_decisions`.
3. Sort flexible dimensions alphabetically by key name.
4. Sort alternatives canonically within each dimension.
5. Compute the bounded Cartesian product using `itertools.product` over sorted lists.

### Step 2: Compatibility & Constraint Filtering
Each candidate combination `C` is evaluated:
- **Hard Requirements**: If an uncontested hard requirement specifies a value for a dimension, combinations with conflicting values are discarded.
- **Incompatibility Rules**: If combination `C` matches any `IncompatibilityRule` pair (`dimension_a == val_a` AND `dimension_b == val_b`), the combination is discarded.

### Step 3: Dynamic Trade-Off & Risk Derivation
For each valid candidate combination `C`:
- The generator inspects `analysis.relationships`.
- If an assigned value in `C` triggers a `DimensionRelationship` where `impact == RelationshipImpact.IMPROVES` for target $T_1$ and `impact == RelationshipImpact.REDUCES` for target $T_2$, a `TradeOff` object is constructed dynamically.
- The engine contains **no hardcoded domain rules**. It reads declared relationship graphs directly from `ArchitecturalAnalysis`.

### Step 4: Fingerprinting & Deduplication
For candidate strategy $S$:
```python
def _compute_fingerprint(decisions: list[DecisionRecord]) -> str:
    sorted_decs = sorted(decisions, key=lambda d: (str(d.dimension), d.subject, str(d.value)))
    tokens = [f"{d.dimension}:{d.subject}={d.value}" for d in sorted_decs]
    return "|".join(tokens)
```
Duplicate candidate strategies with identical fingerprints are pruned.

### Step 5: Deterministic Ordering & Strategy Bounding
- Candidates are sorted deterministically by fingerprint.
- Output is bounded by `max_strategies` (default: 10).
- Final sequential IDs (`strategy-1`, `strategy-2`, ...) and provenance metadata are attached.

---

## 4. Combinatorial Control & Determinism

To prevent exponential combination explosion when analyzing many flexible dimensions:

1. **Max Candidate Bound**: Candidate combination enumeration is hard-bounded at `max_candidate_combinations = 100`.
2. **Early Pruning**: Hard constraint and incompatibility rule filtering occurs *during* iteration before creating strategy objects.
3. **Deterministic Lexicographical Ordering**: All dimension keys and candidate values are sorted lexicographically before enumeration.

---

## 5. Unseen-Dimension Acceptance Test Specification

The fundamental acceptance criteria for Stage 3B.3 is **Generality Validation**.

Without modifying `strategy_generator.py`, the engine MUST successfully generate valid strategies for un-modelled architectural dimensions:

### Test Case A: Single Unseen Dimension
- Dimension: `"natural_ventilation_strategy"`
- Alternatives: `["courtyard", "cross_ventilation", "mechanical_assistance"]`
- **Expected Outcome**: Generates 3 distinct `DesignStrategy` objects assigning `"courtyard"`, `"cross_ventilation"`, and `"mechanical_assistance"` respectively.

### Test Case B: Multiple Unseen Dimensions with Incompatibility
- Dimension 1: `"structural_system"` (`["load_bearing", "steel_frame"]`)
- Dimension 2: `"spatial_layout"` (`["cellular", "large_open_span"]`)
- Incompatibility: `load_bearing` + `large_open_span` is prohibited.
- **Expected Outcome**: Generates 3 valid combinations (`load_bearing` + `cellular`, `steel_frame` + `cellular`, `steel_frame` + `large_open_span`). Combination `load_bearing` + `large_open_span` is automatically filtered out.

---

## 6. Incremental Migration Plan (3B.3 Sub-stages)

To maintain code stability and clear testing checkpoints:

```text
3B.3A — Schema Data Contract & Tests  ✅
        - Add alternatives to DecisionRecord
        - Add IncompatibilityRule and DimensionRelationship to ArchitecturalAnalysis
        - Add schema validation unit tests
        
3B.3B — Generic Strategy Engine & Tests  ✅
        - Implement data-driven combination enumeration
        - Implement dynamic constraint/incompatibility filtering
        - Implement dynamic trade-off derivation
        - Implement unseen-dimension unit tests

3B.3C — Legacy Hardcoded Archetype Removal & Full Regression  ✅
        3B.3C-1: Legacy audit — classify all hardcoded legacy rules
        3B.3C-2: Declarative Decision Catalog (decision_catalog.json)
                 - catalog_loader.py: deterministic JSON loader
                 - ArchitecturalAnalyzer: generic catalog integration
        3B.3C-3: Golden migration tests — semantic equivalence verified
        3B.3C-4: Legacy Path B removed from StrategyGenerator
                 - Hardcoded archetype archetypes removed
                 - Legacy trade-off fallback removed
                 - RequirementKind branching removed from generator
                 - _build_uncontested_hard_reqs reads fixed_decisions generically
                 - Legacy absence regression test added (AST-based guard)
                 - 85/85 tests passing
```

---

## 7. Strict Boundaries (Non-Responsibilities)

The `StrategyGenerator` engine MUST NEVER:
- Generate geometric coordinates, polygons, meshes, or CAD bounding boxes.
- Call solver engines (MILP, PuLP, CBC).
- Invoke external LLM/AI APIs.
- Hardcode scenario/benchmark specific conditions (`44x42`, `four-family`).
