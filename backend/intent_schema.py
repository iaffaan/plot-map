from enum import Enum
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional

class RoomCategory(str, Enum):
    BEDROOM = "bedroom"
    LIVING = "living"
    KITCHEN = "kitchen"
    BATHROOM = "bathroom"
    CORRIDOR = "corridor"
    POOJA = "pooja"

class RoomIntent(BaseModel):
    """
    Represents the user's intent for a single room, capturing its type and minimum area.
    """
    room_type: RoomCategory = Field(
        ...,
        description="The type category of the room (bedroom, living, kitchen, bathroom, corridor, pooja)."
    )
    min_area_sqft: Optional[int] = Field(
        None,
        description="Minimum area of the room in square feet. If missing, default to standard Indian minimums (Bedroom: 100, Living Room: 150, Kitchen: 60, Bathroom: 30, others: 50)."
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
    rooms: List[RoomIntent] = Field(
        default_factory=list,
        description="List of rooms to pack into the floor layout."
    )
