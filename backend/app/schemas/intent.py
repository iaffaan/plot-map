from enum import Enum

from pydantic import BaseModel, Field, model_validator


class RoomCategory(str, Enum):
    BEDROOM = "bedroom"
    LIVING = "living"
    KITCHEN = "kitchen"
    BATHROOM = "bathroom"
    CORRIDOR = "corridor"
    POOJA = "pooja"
    BALCONY = "balcony"
    UTILITY = "utility"

class RoomIntent(BaseModel):
    """
    Represents the user's intent for a single room, capturing its type and minimum area.
    """
    room_type: RoomCategory = Field(
        ...,
        description="The type category of the room (bedroom, living, kitchen, bathroom, corridor, pooja, balcony, utility)."
    )
    min_area_sqft: int | None = Field(
        None,
        description="Minimum area of the room in square feet. If missing, default to standard Indian minimums (Bedroom: 100, Living Room: 150, Kitchen: 60, Bathroom: 30, Balcony: 40, Utility: 35, others: 50)."
    )

    @model_validator(mode='after')
    def apply_indian_minimums(self) -> 'RoomIntent':
        """
        Ensures standard Indian minimum sizes are enforced if no area is specified.
        """
        if self.min_area_sqft is None or self.min_area_sqft <= 0:
            if self.room_type == RoomCategory.BEDROOM:
                self.min_area_sqft = 100
            elif self.room_type == RoomCategory.LIVING:
                self.min_area_sqft = 150
            elif self.room_type == RoomCategory.KITCHEN:
                self.min_area_sqft = 60
            elif self.room_type == RoomCategory.BATHROOM:
                self.min_area_sqft = 30
            elif self.room_type == RoomCategory.BALCONY:
                self.min_area_sqft = 40
            elif self.room_type == RoomCategory.UTILITY:
                self.min_area_sqft = 35
            else:
                self.min_area_sqft = 50
        return self

class CompilerIntent(BaseModel):
    """
    The main schema containing all extracted parameters required by the architectural constraint engine.
    """
    plot_width: float = Field(
        ...,
        description="Width of the plot in feet."
    )
    plot_depth: float = Field(
        ...,
        description="Depth of the plot in feet."
    )
    floors: int = Field(
        1,
        description="Total number of floors. Defaults to 1. Note: G+1 = 2 floors, G+2 = 3 floors, etc."
    )
    front_road_setback: float = Field(
        5.0,
        description="Front road setback distance in feet. Defaults to 5.0."
    )
    confidence_score: float = Field(
        1.0,
        description="Confidence score of the extraction (0.0 to 1.0). Fallback parser defaults to 0.5."
    )
    fallback_used: bool = Field(
        False,
        description="Whether rule-based heuristic extraction or default rooms were used as a fallback."
    )
    prioritize_ventilation: bool = Field(
        False,
        description="Whether cross-ventilation is explicitly prioritized by the design brief."
    )
    prioritize_daylight: bool = Field(
        False,
        description="Whether natural daylight is explicitly prioritized by the design brief."
    )
    target_objectives: list[str] = Field(
        default_factory=list,
        description="List of user architectural objectives extracted from prompt."
    )
    rooms: list[RoomIntent] = Field(
        default_factory=list,
        description="List of rooms to pack into the floor layout."
    )
