from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.architectural_analysis import (
    AnalysisSeverity,
    DecisionDimension,
    DecisionRecord,
    DependencyRecord,
)


class FeasibilityExpectation(str, Enum):
    EXPECTED_FEASIBLE = "expected_feasible"
    CONDITIONALLY_FEASIBLE = "conditionally_feasible"
    UNCERTAIN = "uncertain"
    BLOCKED = "blocked"
    NOT_EVALUATED = "not_evaluated"


class TradeOff(BaseModel):
    id: str
    improved_dimension: DecisionDimension | str
    reduced_dimension: DecisionDimension | str
    explanation: str
    source_ids: list[str] = Field(default_factory=list)
    severity: AnalysisSeverity
    accepted: bool = False


class StrategyRisk(BaseModel):
    id: str
    description: str
    severity: AnalysisSeverity
    source_ids: list[str] = Field(default_factory=list)


class DesignStrategy(BaseModel):
    id: str
    source_problem_id: str
    source_problem_version: int = Field(..., ge=1)
    source_analysis_id: str
    name: str
    approach: str
    decisions: list[DecisionRecord] = Field(default_factory=list)
    flexible_decisions: list[DecisionDimension | str] = Field(default_factory=list)
    requirements_satisfied: list[str] = Field(default_factory=list)
    constraints_addressed: list[str] = Field(default_factory=list)
    preferences_supported: list[str] = Field(default_factory=list)
    objectives_targeted: list[str] = Field(default_factory=list)
    trade_offs: list[TradeOff] = Field(default_factory=list)
    dependencies: list[DependencyRecord] = Field(default_factory=list)
    risks: list[StrategyRisk] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    feasibility_expectation: FeasibilityExpectation = FeasibilityExpectation.NOT_EVALUATED
    rationale: str
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_strategy_identity_and_ids(self) -> "DesignStrategy":
        if not self.source_problem_id.strip() or not self.source_analysis_id.strip():
            raise ValueError("source_problem_id and source_analysis_id are required")

        collections = (self.decisions, self.trade_offs, self.dependencies, self.risks)
        for collection in collections:
            ids = [item.id for item in collection]
            if len(ids) != len(set(ids)):
                raise ValueError("IDs must be unique within each DesignStrategy collection")
        return self