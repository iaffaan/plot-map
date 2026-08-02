# Core Engine Roadmap

### **Phase 1: Geometric Boundaries (Shapely)**

**Goal:** Mathematically define the legal buildable envelope and lock the immutable vertical structures.

* **Tech Stack:** `Python 3.10+`, `shapely`.
* **Step 1: Define the Master Plot.** Create a `Polygon` representing the raw plot coordinates $(0,0)$ to $(Width, Depth)$.
* **Step 2: Subtraction Logic (Setbacks).** Write the algebraic subtraction functions to enforce municipal setbacks (e.g., subtract $5\text{ ft}$ from the $Y_{max}$ edge for the road).
* **Step 3: Anchor the Core.** Define a fixed `Polygon` for the staircase/lift shaft. Place it strictly against an external boundary (for independent floor access).
* **Step 4: The Packable Area.** Use a boolean difference operation: `Buildable_Area = (Plot - Setbacks) - Stair_Core`.
* **Validation Check:** Feed the engine a $40 \times 40\text{ ft}$ plot with a $5\text{ ft}$ setback on all sides and a $10 \times 10\text{ ft}$ core. If the resulting `Buildable_Area` is not exactly $800\text{ sq ft}$, your logic is flawed. Stop and fix it.

### **Phase 2: Topological Routing (NetworkX)**

**Goal:** Prevent privacy violations and calculate the "Distance to Air" metric before placing walls.

* **Tech Stack:** `networkx`.
* **Step 1: Define the Air Node.** Set the front road edge as the root node for ventilation.
* **Step 2: Build the Room DAG (Directed Acyclic Graph).** Define rooms as nodes and doors as edges. Enforce directional flow: `Main Door -> Living Room -> Corridor -> Bedroom -> Bathroom`.
* **Step 3: Graph Traversal (Privacy).** Write a traversal check. If the shortest path from the `Main Door` to the `Kitchen` forces the user to walk through a `Bedroom`, the graph fails validation.
* **Step 4: Airflow Calculation.** Calculate the graph distance from every room to the `Air Node`. If a `Bedroom` has a distance $> 1$ (no direct shared edge with the road/exterior), trigger the procedural Open-To-Sky (OTS) shaft generation.

### **Phase 3: The Optimization Engine (PuLP / MILP)**

**Goal:** Pack the topological graph into the geometric boundary without overlapping.

* **Tech Stack:** `pulp` (for Mixed-Integer Linear Programming) or `scipy.optimize`.
* **Step 1: Variable Definition.** For each room $i$, define continuous coordinate variables $(x_i, y_i)$ and dimensions $(w_i, h_i)$.
* **Step 2: Hard Constraints.** * No room can exist outside `Buildable_Area`.
* No room can overlap the `Stair_Core`.
* Room bounds cannot overlap each other (requires binary switch variables / Big-M method).


* **Step 3: Dimensional Constraints.** Enforce minimum area and aspect ratios (e.g., a bedroom cannot be a $2 \times 60\text{ ft}$ hallway; constrain aspect ratio between $1.0$ and $1.6$).
* **Step 4: The Objective Function.** Maximize the total area utilized (minimize dead space) while ensuring rooms requiring ventilation share an edge with either the road boundary or an OTS shaft.
* **Validation Check:** This is the hardest step. The solver will initially fail or timeout. You must limit the solver iterations or grid resolution (e.g., snap coordinates to a $0.5\text{ ft}$ grid) to ensure it returns a result in under 5 seconds.

### **Phase 4: API Orchestration (FastAPI)**

**Goal:** Expose the math engine to the frontend via a high-speed API.

* **Tech Stack:** `fastapi`, `uvicorn`, `pydantic`.
* **Step 1: Pydantic Schemas.** Define strict input schemas for the LLM payload (Floors, Plot Dimensions, Setbacks, Room List).
* **Step 2: The Compilation Endpoint.** Create a `POST /compile` route.
* **Step 3: Serialization.** Convert the Shapely polygons into standardized JSON coordinate arrays:

```json
{
  "type": "Polygon",
  "label": "MasterBedroom",
  "coordinates": [[12.5, 10.0], [12.5, 22.0], [24.0, 22.0], [24.0, 10.0]]
}

```

* **Step 4: Error Handling.** If the MILP solver proves a layout is impossible (e.g., the user asked for $3000\text{ sq ft}$ of rooms on a $1500\text{ sq ft}$ plot), the API must return a clear `422 Unprocessable Entity` error with the exact mathematical reason, rather than returning a broken map.
