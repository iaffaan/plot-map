from typing import Any

from pydantic import BaseModel, Field


class BoundarySchema(BaseModel):
    envelope: list[list[float]] = Field(default_factory=list, description="Buildable envelope polygon coordinates.")
    stair_core: list[list[float]] = Field(default_factory=list, description="Stair core polygon coordinates.")

class CompileMetadataSchema(BaseModel):
    plot_width: float
    plot_depth: float
    buildable_area_sqft: float
    ots_generated_count: int

class CompileOutputSchema(BaseModel):
    success: bool
    message: str
    metadata: CompileMetadataSchema
    boundaries: BoundarySchema
    layout: dict[str, Any] = Field(default_factory=dict, description="Topological room coordinates.")
