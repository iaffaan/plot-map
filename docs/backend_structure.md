# Backend Architecture Reference

## Code Structure

```bash
backend/
├── app/
│   ├── main.py                    # [1] FastAPI Entrypoint (Slim: CORS & Router inclusion only)
│   │
│   ├── api/                       # [2] Routing Layer (No math here)
│   │   ├── dependencies.py        # Auth, DB sessions, LLM client injection
│   │   └── v1/
│   │       ├── router.py          # Combines all v1 endpoints
│   │       └── endpoints/
│   │           ├── compile.py     # POST /api/v1/compile
│   │           └── health.py      # GET /api/v1/health
│   │
│   ├── core/                      # [3] Application Configuration
│   │   ├── config.py              # Loads .env (OpenAI keys, solver timeouts)
│   │   ├── exceptions.py          # Custom error classes (e.g., GeometryOverlapError)
│   │   └── logging.py             # Custom loggers for solver iterations
│   │
│   ├── schemas/                   # [4] Data Contracts in Transit (Pydantic)
│   │   ├── intent.py              # The LLM input schema (RoomIntent, CompilerIntent)
│   │   └── output.py              # The 2.5D hierarchical JSON output schema
│   │
│   ├── models/                    # [5] Data at Rest (Database/Persistence)
│   │   └── project.py             # SQLAlchemy/MongoDB models for saving layouts
│   │
│   ├── services/                  # [6] Core Business Logic (The IP Moat)
│   │   │
│   │   ├── ai/                    # AI Parsing Layer
│   │   │   └── parser.py          # Instructor/OpenAI extraction logic
│   │   │
│   │   ├── geometry/              # 2D Constraint Engine (Shapely)
│   │   │   ├── core_lock.py       # Staircase/Shaft anchoring
│   │   │   └── setbacks.py        # Municipal boundary subtraction
│   │   │
│   │   ├── optimization/          # The Physics Engine (PuLP / MILP)
│   │   │   ├── constraints.py     # Big-M non-overlap logic
│   │   │   └── solver.py          # The execution loop & timeout handling
│   │   │
│   │   └── compiler/              # The 2.5D Serializer
│   │       └── serializer.py      # Combines Geometry + Optimization into the 2.5D JSON array
│   │
│   └── assets/                    # [7] Static Constraints
│       └── rules/
│           ├── building_codes.json # FAR/FSI rules by municipality
│           └── vastu_rules.json   # Topological rules (e.g., Kitchen = SE quadrant)
│
├── tests/                         # [8] Test Suite
│   ├── api/                       # Endpoint tests
│   ├── services/                  # Math/Solver unit tests
│   └── conftest.py                # Pytest fixtures
│
├── requirements.txt
├── .env                           # Local secrets
└── .env.example                   # Template for teammates
```