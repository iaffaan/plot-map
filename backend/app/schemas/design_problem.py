from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.intent import RoomIntent


class RequirementStrength(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class RequirementKind(str, Enum):
    SITE = "site"
    SPACE = "space"
    QUANTITY = "quantity"
    ASSIGNMENT = "assignment"
    CIRCULATION = "circulation"
    ACCESSIBILITY = "accessibility"
    PRIVACY = "privacy"
    RELATIONSHIP = "relationship"
    ENVIRONMENTAL = "environmental"
    REGULATORY = "regulatory"
    COST = "cost"
    AESTHETIC = "aesthetic"
    OPERATIONAL = "operational"


class RelationshipType(str, Enum):
    ADJACENT = "adjacent"
    CONNECTED = "connected"
    SEPARATED = "separated"
    STACKED = "stacked"
    SHARED = "shared"
    INDEPENDENT = "independent"
    CONTAINS = "contains"


class RequirementSource(str, Enum):
    USER = "user"
    PARSER = "parser"
    DERIVED = "derived"
    SYSTEM = "system"


class RequirementRelation(BaseModel):
    relation: RelationshipType
    target_id: str
    distance: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Requirement(BaseModel):
    id: str
    kind: RequirementKind
    subject: str
    value: Any
    strength: RequirementStrength = RequirementStrength.HARD
    priority: int = Field(50, ge=0, le=100)
    weight: float = Field(1.0, ge=0.0)
    scope: str | None = None
    relationships: list[RequirementRelation] = Field(default_factory=list)
    conflicts_with: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    optional: bool = False
    source: RequirementSource = RequirementSource.USER


class Constraint(BaseModel):
    id: str
    expression: str
    strength: RequirementStrength = RequirementStrength.HARD
    priority: int = Field(50, ge=0, le=100)
    penalty: float = Field(1.0, ge=0.0)
    scope: str | None = None
    explanation: str | None = None


class Preference(BaseModel):
    id: str
    description: str
    target: Any
    priority: int = Field(50, ge=0, le=100)
    weight: float = Field(1.0, ge=0.0)
    scope: str | None = None


class Objective(BaseModel):
    id: str
    metric: str
    direction: Literal["maximize", "minimize"]
    priority: int = Field(50, ge=0, le=100)
    weight: float = Field(1.0, ge=0.0)
    scope: str | None = None


class SpaceRequirement(BaseModel):
    id: str
    room: RoomIntent
    quantity: int = Field(1, ge=1)
    owner_id: str | None = None
    optional: bool = False
    priority: int = Field(50, ge=0, le=100)
    relationships: list[RequirementRelation] = Field(default_factory=list)


class UserGroup(BaseModel):
    id: str
    name: str | None = None
    spaces: list[SpaceRequirement] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SiteDefinition(BaseModel):
    plot_width: float = Field(..., gt=0)
    plot_depth: float = Field(..., gt=0)
    floors: int = Field(1, ge=1)
    setbacks: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RequirementDelta(BaseModel):
    id: str
    base_problem_id: str
    parent_version: int = Field(..., ge=1)
    operation: Literal["add", "remove", "replace", "modify"]
    target_id: str | None = None
    value: Any = None
    source_text: str | None = None


class ValidationResult(BaseModel):
    success: bool
    candidate_id: str | None = None
    hard_constraints: dict[str, bool] = Field(default_factory=dict)
    soft_constraints: dict[str, bool] = Field(default_factory=dict)
    requirement_results: dict[str, bool] = Field(default_factory=dict)
    conflicts: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class DesignProblem(BaseModel):
    id: str
    version: int = Field(1, ge=1)
    site: SiteDefinition
    user_groups: list[UserGroup] = Field(default_factory=list)
    spaces: list[SpaceRequirement] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    preferences: list[Preference] = Field(default_factory=list)
    objectives: list[Objective] = Field(default_factory=list)
    deltas: list[RequirementDelta] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "DesignProblem":
        collections = (
            self.user_groups,
            self.spaces,
            self.requirements,
            self.constraints,
            self.preferences,
            self.objectives,
            self.deltas,
        )
        for collection in collections:
            ids = [item.id for item in collection]
            if len(ids) != len(set(ids)):
                raise ValueError("IDs must be unique within each DesignProblem collection")
        return self