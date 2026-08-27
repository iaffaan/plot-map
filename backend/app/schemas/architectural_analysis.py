from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.design_problem import (
    Constraint,
    Objective,
    Preference,
    Requirement,
    RequirementSource,
)


class DecisionStatus(str, Enum):
    FIXED = "fixed"
    FLEXIBLE = "flexible"
    PARTIALLY_FIXED = "partially_fixed"
    UNKNOWN = "unknown"
    BLOCKED = "blocked"
    DERIVED = "derived"


class ConflictStatus(str, Enum):
    DETECTED = "detected"
    RESOLVABLE_BY_PRIORITY = "resolvable_by_priority"
    REQUIRES_CLARIFICATION = "requires_clarification"
    ACCEPTED_TRADEOFF = "accepted_tradeoff"
    RESOLVED = "resolved"


class UncertaintyMateriality(str, Enum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MATERIAL = "material"
    BLOCKING = "blocking"


class AnalysisSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class DecisionDimension(str, Enum):
    SITE_RESPONSE = "site_response"
    PROGRAM_DEFINITION = "program_definition"
    SPACE_QUANTITY = "space_quantity"
    SPACE_OWNERSHIP = "space_ownership"
    FLOOR_ALLOCATION = "floor_allocation"
    UNIT_ORGANIZATION = "unit_organization"
    CIRCULATION = "circulation"
    VERTICAL_CIRCULATION = "vertical_circulation"
    ENTRANCE_STRATEGY = "entrance_strategy"
    SHARED_PRIVATE_STRATEGY = "shared_private_strategy"
    SERVICE_CORE_STRATEGY = "service_core_strategy"
    ORIENTATION = "orientation"
    ZONING = "zoning"
    ACCESSIBILITY = "accessibility"
    PRIVACY = "privacy"
    ENVIRONMENTAL_RESPONSE = "environmental_response"
    STRUCTURAL_STRATEGY = "structural_strategy"
    REGULATORY_STRATEGY = "regulatory_strategy"
    COST_STRATEGY = "cost_strategy"


class DecisionRecord(BaseModel):
    id: str
    dimension: DecisionDimension
    subject: str
    value: Any = None
    source_ids: list[str] = Field(default_factory=list)
    status: DecisionStatus
    rationale: str | None = None


class ConflictRecord(BaseModel):
    id: str
    source_ids: list[str] = Field(default_factory=list)
    type: str
    severity: AnalysisSeverity
    status: ConflictStatus
    explanation: str
    affected_dimensions: list[DecisionDimension] = Field(default_factory=list)
    resolution_options: list[str] = Field(default_factory=list)
    clarification_question: str | None = None


class UncertaintyRecord(BaseModel):
    id: str
    topic: str
    description: str
    materiality: UncertaintyMateriality
    affected_dimensions: list[DecisionDimension] = Field(default_factory=list)
    required_for_strategy: bool = False
    clarification_question: str | None = None
    source: RequirementSource = RequirementSource.SYSTEM


class DependencyRecord(BaseModel):
    id: str
    source_dimension: DecisionDimension
    affected_dimensions: list[DecisionDimension] = Field(default_factory=list)
    relationship: str
    explanation: str


class FeasibilityConcern(BaseModel):
    id: str
    dimension: DecisionDimension
    description: str
    severity: AnalysisSeverity
    source_ids: list[str] = Field(default_factory=list)


class ArchitecturalAnalysis(BaseModel):
    problem_id: str
    problem_version: int = Field(..., ge=1)
    summary: str
    fixed_decisions: list[DecisionRecord] = Field(default_factory=list)
    flexible_decisions: list[DecisionRecord] = Field(default_factory=list)
    hard_constraints: list[Constraint | Requirement] = Field(default_factory=list)
    soft_preferences: list[Preference | Requirement] = Field(default_factory=list)
    objectives: list[Objective] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    uncertainties: list[UncertaintyRecord] = Field(default_factory=list)
    decision_dimensions: list[DecisionDimension] = Field(default_factory=list)
    dependencies: list[DependencyRecord] = Field(default_factory=list)
    feasibility_concerns: list[FeasibilityConcern] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_collection_ids(self) -> "ArchitecturalAnalysis":
        collections = (
            self.fixed_decisions,
            self.flexible_decisions,
            self.conflicts,
            self.uncertainties,
            self.dependencies,
            self.feasibility_concerns,
        )
        for collection in collections:
            ids = [item.id for item in collection]
            if len(ids) != len(set(ids)):
                raise ValueError("IDs must be unique within each ArchitecturalAnalysis collection")
        return self