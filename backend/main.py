from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from engine.orchestrator import compile_blueprint

app = FastAPI(
    title="Uncharted | Building Blueprint Compiler Engine API",
    description="Mathematical and topological spatial compiler engine for dense urban real estate.",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Input Schemas
class PlotConfig(BaseModel):
    width: float = Field(..., description="Width of the plot in feet", gt=0)
    depth: float = Field(..., description="Depth of the plot in feet", gt=0)

class Setbacks(BaseModel):
    left: float = Field(0.0, description="Left setback in feet", ge=0)
    right: float = Field(0.0, description="Right setback in feet", ge=0)
    bottom: float = Field(0.0, description="Bottom setback in feet", ge=0)
    top: float = Field(0.0, description="Top setback in feet", ge=0)

class StairCoreConfig(BaseModel):
    width: float = Field(..., description="Stair core width in feet", ge=0)
    height: float = Field(..., description="Stair core height in feet", ge=0)
    edge: str = Field("bottom-left", description="Edge anchor for stair core (e.g. bottom-left, bottom-right, top-left, top-right)")

class RoomConfig(BaseModel):
    name: str = Field(..., description="Unique room name")
    type: str = Field(..., description="Room type (e.g., Bedroom, Kitchen, Living Room, Bathroom, Corridor)")
    min_area: float = Field(..., description="Minimum area in square feet", gt=0)
    min_width: float = Field(3.0, description="Minimum width in feet", gt=0)
    min_height: float = Field(3.0, description="Minimum height in feet", gt=0)
    requires_ventilation: bool = Field(True, description="Does the room require external ventilation?")
    adjacent_to_road: bool = Field(False, description="Is the room required to be on the road/front boundary?")
    aspect_ratio_range: Optional[tuple[float, float]] = Field((1.0, 1.6), description="Tuple of (min_aspect_ratio, max_aspect_ratio)")

class CompileRequest(BaseModel):
    plot: PlotConfig
    setbacks: Setbacks
    stair_core: StairCoreConfig
    rooms: list[RoomConfig]
    adjacencies: list[tuple[str, str]] = Field([], description="List of door/access pairs")
    road_edge: str = Field("bottom", description="Which side the road is on (bottom, top, left, right)")
    grid_snap: float = Field(0.5, description="Grid snap size in feet")
    time_limit_sec: int = Field(5, description="Solver timeout in seconds")

    model_config = {
        "json_schema_extra": {
            "example": {
                "plot": {"width": 40.0, "depth": 40.0},
                "setbacks": {"left": 5.0, "right": 5.0, "bottom": 5.0, "top": 5.0},
                "stair_core": {"width": 10.0, "height": 10.0, "edge": "bottom-left"},
                "rooms": [
                    {"name": "Main Door", "type": "Entrance", "min_area": 9.0, "min_width": 3.0, "min_height": 3.0, "requires_ventilation": False, "adjacent_to_road": True},
                    {"name": "Living Room", "type": "Living Room", "min_area": 100.0, "min_width": 10.0, "min_height": 10.0, "requires_ventilation": True, "adjacent_to_road": True},
                    {"name": "Kitchen", "type": "Kitchen", "min_area": 64.0, "min_width": 8.0, "min_height": 8.0, "requires_ventilation": True, "adjacent_to_road": False},
                    {"name": "Bedroom", "type": "Bedroom", "min_area": 100.0, "min_width": 10.0, "min_height": 10.0, "requires_ventilation": True, "adjacent_to_road": False}
                ],
                "adjacencies": [
                    ["Main Door", "Living Room"],
                    ["Living Room", "Kitchen"],
                    ["Living Room", "Bedroom"]
                ],
                "road_edge": "bottom",
                "grid_snap": 0.5,
                "time_limit_sec": 10
            }
        }
    }

@app.post("/compile", status_code=200)
def compile_layout_endpoint(request: CompileRequest):
    # Convert Pydantic request to dictionary payload
    payload = request.model_dump()
    
    # Compile the blueprint using orchestrator
    result = compile_blueprint(payload)
    
    if not result.get("success", False):
        error_msg = result.get("error", "Failed to compile layout due to mathematical constraint infeasibility.")
        print(f"\n[COMPILATION FAILED]: {error_msg}\n")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_msg
        )
        
    return result

@app.get("/health")
def health_check():
    return {"status": "healthy"}
