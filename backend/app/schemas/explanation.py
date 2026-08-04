from pydantic import BaseModel, Field


class DesignExplanation(BaseModel):
    """
    Structured model containing explanations for different architectural aspects
    of the compiled floor plan.
    """
    overall_concept: str = Field(
        ..., 
        description="Overall architectural design concept, layout theme, and spatial distribution."
    )
    kitchen_placement: str = Field(
        ..., 
        description="Reasoning behind the kitchen's placement (ventilation, morning sunlight, Vastu, proximity)."
    )
    plumbing_efficiency: str = Field(
        ..., 
        description="Details on how the vertical plumbing core is stacked to optimize drainage runs."
    )
    vastu_compliance: str = Field(
        ..., 
        description="Vastu Shastra alignment assessment (kitchen orientation, entry direction, zoning)."
    )
    circulation_efficiency: str = Field(
        ..., 
        description="Evaluation of circulation corridors, accessibility flow, and minimization of dead/wasted space."
    )
