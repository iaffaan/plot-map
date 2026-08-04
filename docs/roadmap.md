For **Antigravity**, I would not ask it to "build a floor plan." That's too broad. Instead, make it implement the system in well-defined engineering phases. This reduces mistakes and keeps every change testable.

---

# Antigravity Implementation Roadmap

## Phase 0 — Project Foundation

**Goal:** Establish a production-ready backend structure before adding new features.

### Tasks

* Create the directory structure.
* Configure `config.py` using Pydantic Settings.
* Set up logging.
* Centralize exceptions.
* Configure dependency injection.
* Add `.env.example`.
* Configure pytest.
* Add type checking (mypy).
* Add linting (ruff/black).

**Deliverable**

```
FastAPI starts successfully.

Health endpoint works.

All imports resolved.

No business logic yet.
```

---

# Phase 1 — AI Requirement Extraction

**Goal**

Convert natural language into a validated `CompilerIntent`.

### Tasks

* Integrate Gemini 2.5 Flash.
* Build parser service.
* Create prompt templates.
* Validate output using Pydantic.
* Implement fallback parser.
* Retry on malformed JSON.
* Add confidence score.

**Input**

```
Need a 3BHK
30x40 plot
Budget 80 lakh
Parking
```

**Output**

```python
CompilerIntent(...)
```

**Deliverable**

```
95%+ structured parsing accuracy.
```

---

# Phase 2 — Feasibility Engine

**Goal**

Reject impossible requests before optimization.

### Tasks

Calculate:

* Plot area
* Setbacks
* Legal envelope
* FAR
* Coverage
* Maximum buildable area

Compare against

```
Requested Area
```

If impossible:

Return

```json
{
  "status":"infeasible",
  "reason":"Requested area exceeds legal envelope."
}
```

**Deliverable**

No impossible requests reach MILP.

---

# Phase 3 — Room Program Generator

**Goal**

Convert intent into optimization-ready rooms.

Example

```
3BHK
```

↓

```
Living

Dining

Kitchen

Bedroom 1

Bedroom 2

Master

Bath 1

Bath 2

Utility

Stair
```

Each room receives

```
min area

preferred area

priority

aspect ratio

adjacency

floor assignment
```

**Deliverable**

Room objects ready for optimization.

---

# Phase 4 — Optimization Engine (MILP)

This is the mathematical core.

## 4.1 Grid Discretization

Everything snaps to

```
0.5 ft
```

No floating coordinates.

---

## 4.2 Bounding Box Selection

Generate legal

```
width

height
```

pairs.

MILP selects one.

---

## 4.3 Hard Constraints

Implement

* no overlap
* inside legal envelope
* minimum room size
* aspect ratio
* setback compliance
* stair core lock
* bathroom plumbing alignment
* corridor width

---

## 4.4 Soft Constraints

Objective function rewards

* daylight
* ventilation
* compact circulation
* privacy
* kitchen near dining
* bedroom away from entrance

Penalty

* long corridors
* isolated rooms
* wasted area

---

## 4.5 Solver Configuration

CBC

```
Time Limit

8 sec
```

Relative gap

```
2%
```

Warm start

Enabled

---

**Deliverable**

Optimization completes in under 8 seconds for common residential layouts.

---

# Phase 5 — Geometry Compiler

Current prototype skips this.

This phase converts rectangles into architecture.

### Tasks

Generate

* walls
* doors
* windows
* corridors
* staircase
* wall thickness
* room labels

Merge

Shared walls.

Snap

Tiny gaps.

Validate

Topology.

**Deliverable**

Real floor plan.

Not floating boxes.

---

# Phase 6 — Multi-Floor Compiler (Completed)

Ground floor solves first.

Extract
```
Stair
Plumbing
Structural Core
```

Freeze.

Upper floors inherit.

Ensure
* vertical alignment (stair core coordinates remain perfectly snapped and identical)
* plumbing stacks (bathrooms on upper floors align with lower bathroom cores via solver penalties)
* stair continuity (staircases are locked in place across all vertical planes)

---

# Phase 7 — Metrics Engine (Completed)

Compute:
* FAR / FSI (Floor Area Ratio & Floor Space Index based on total built-up and plot area)
* Plot coverage (built-up percentage of ground floor)
* Daylighting (window-to-room ratio/ventilation compliance score)
* Cross ventilation (airflow openings/windows count evaluation)
* Cost (in INR, calculated dynamically per built sqft)
* Carbon score (embodied carbon in kg CO2e)
* Buildability score (plumbing stacks alignment evaluation)
* Privacy score (road-bedroom setback contact penalty)
* Accessibility score (vertical travel and lobby space assessment)

Exactly what appears on the dashboard.

---

# Phase 8 — Renderer (Completed)

Generate Hierarchical JSON:
```
Project
↓
Floors
↓
Rooms
↓
Walls, Doors, Windows, Furniture, Metadata
```

No calculations.
Rendering only.

---

# Phase 9 — AI Explanation Layer (Completed)

Gemini explains layout design decisions:
* Overall Concept (spatial distribution and density)
* Kitchen Placement (daylight & ventilation)
* Plumbing efficiency (vertical alignment)
* Vastu compliance (traditional zoning guidelines)
* Reduced circulation (accessibility pathways optimization)

No optimization here.
Only explanation.

---

# Phase 10 — Frontend Integration (Completed)

React frontend integration:
* Bound results panel dynamically to backend metrics service response
* Connected 3D Three.js canvas to render floor-specific room layout polygons
* Visualized AI design explanations card
* Added loading animations and timeline tracking

---

# Phase 11 — Validation Engine (Completed)

Automatically verify:
* ✓ No overlaps (using shapely polygon intersections)
* ✓ Doors connected (verifying door touch boundaries)
* ✓ Corridor reachable & vertical cores aligned
* ✓ Windows legal (facing setbacks or OTS shafts)
* ✓ Stair valid (locked location match)
* ✓ Rooms accessible (door connectivity pathways)
* ✓ Plumbing connected (bathroom stacking proximity)

Returns dynamic Buildability Score (e.g. 85.0% or 100.0%) based on check weights.

---

# Phase 12 — Testing (Completed)

Comprehensive test coverage implemented:
* ✓ Unit tests (Geometry, MILP, AI Parser, Metrics, Validation Engine)
* ✓ Integration tests (E2E compiler flow from prompt to JSON serialization)
* ✓ Performance tests (Load-tested 20 randomized constraints; 100% success rate, average runtime of 2.4s)

---

# Suggested Repository Structure

```text
AI
│
├── Parser
├── Prompt Manager
├── Validator
└── Fallback

Optimization
│
├── Feasibility
├── Room Generator
├── MILP
├── Objective
└── Post Processing

Geometry
│
├── Walls
├── Doors
├── Windows
├── Corridors
├── Stairs
└── Validation

Rendering
│
├── JSON Serializer
├── Floorplan
└── ThreeJS Output

Metrics
│
├── FAR
├── Cost
├── Daylighting
├── Ventilation
└── Compliance
```

---


