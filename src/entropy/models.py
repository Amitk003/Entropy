from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class FaultType(str, Enum):
    RATE_LIMIT = "rate-limit"
    TIMEOUT = "timeout"
    SEMANTIC_CORRUPTION = "semantic-corruption"
    MEMORY_POISONING = "memory-poisoning"


class ExperimentConfig(BaseModel):
    fault_type: FaultType
    probability: float = Field(default=0.3, ge=0.0, le=1.0)
    experiment_id: str
    target_tools: list[str] = Field(default_factory=list)
    duration_seconds: Optional[float] = None


class SurvivalOutcome(str, Enum):
    FULL_RECOVERY = "full-recovery"
    GRACEFUL_DEGRADATION = "graceful-degradation"
    PARTIAL_COMPLETION = "partial-completion"
    SILENT_FAILURE = "silent-failure"


class ExperimentPostmortem(BaseModel):
    trace_id: str
    injected_fault_type: FaultType
    target_recovery_action: str
    survival_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    outcome: SurvivalOutcome
    evidence_spans: list[str] = Field(default_factory=list)
    summary: str
