"""
Orchestration Services Package for BuildForgeAI Stage 3B.6.
"""

from app.schemas.orchestration import Phase1PruningResult, SpatialPhase2Result
from app.services.orchestration.design_orchestrator import (
    DesignOrchestrator,
    orchestrate_design,
)
from app.services.orchestration.lifecycle_manager import (
    CandidateLifecycleManager,
    CandidateNotFoundError,
    DuplicateCandidateRegistrationError,
    LifecycleError,
    LifecycleTransitionError,
)
from app.services.orchestration.phase1_pruner import Phase1Pruner
from app.services.orchestration.spatial_phase2 import SpatialPhase2Orchestrator

__all__ = [
    "CandidateLifecycleManager",
    "LifecycleError",
    "LifecycleTransitionError",
    "DuplicateCandidateRegistrationError",
    "CandidateNotFoundError",
    "Phase1Pruner",
    "Phase1PruningResult",
    "SpatialPhase2Orchestrator",
    "SpatialPhase2Result",
    "DesignOrchestrator",
    "orchestrate_design",
]
