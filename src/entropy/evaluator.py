"""Evaluator agent that reads traces from SigNoz and produces post-mortem reports."""

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx

from entropy.models import (
    ExperimentPostmortem,
    FaultType,
    SurvivalOutcome,
)


class TraceQueryBackend(ABC):
    """Interface for querying trace data from SigNoz."""

    @abstractmethod
    async def search_traces(self, query: str) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def get_trace_details(self, trace_id: str) -> dict[str, Any]:
        ...

    @abstractmethod
    async def aggregate_traces(self, query: str) -> dict[str, Any]:
        ...


class RESTTraceQueryBackend(TraceQueryBackend):
    """Queries SigNoz through its REST API.

    This is the primary backend used in testing and CI.
    In production, MCPTraceQueryBackend is preferred for
    natural language queries.
    """

    def __init__(self, base_url: str = "http://localhost:8080", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=30.0)

    async def search_traces(self, query: str) -> list[dict[str, Any]]:
        headers = self._build_headers()
        params = {"q": query}
        try:
            response = await self._client.get(
                f"{self.base_url}/api/v3/traces",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", []) or data.get("traces", [])
        except Exception:
            return []

    async def get_trace_details(self, trace_id: str) -> dict[str, Any]:
        headers = self._build_headers()
        try:
            response = await self._client.get(
                f"{self.base_url}/api/v3/traces/{trace_id}",
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return {"trace_id": trace_id, "spans": []}

    async def aggregate_traces(self, query: str) -> dict[str, Any]:
        headers = self._build_headers()
        params = {"q": query}
        try:
            response = await self._client.get(
                f"{self.base_url}/api/v3/metrics/traces",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return {}

    def _build_headers(self) -> dict[str, str]:
        headers = {}
        if self.api_key:
            headers["SIGNOZ-API-KEY"] = self.api_key
        return headers

    async def close(self):
        await self._client.aclose()


class MCPTraceQueryBackend(TraceQueryBackend):
    """Queries SigNoz through the MCP server.

    Uses the MCP protocol to send natural language queries.
    Falls back to RESTTraceQueryBackend on connection failure.
    """

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._rest_fallback = RESTTraceQueryBackend(
            base_url=base_url.replace(":8000", ":8080"),
            api_key=api_key,
        )

    async def search_traces(self, query: str) -> list[dict[str, Any]]:
        try:
            headers = {"SIGNOZ-API-KEY": self.api_key} if self.api_key else {}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/mcp",
                    headers=headers,
                    json={"tool": "signoz_search_traces", "args": {"query": query}},
                )
                response.raise_for_status()
                data = response.json()
                return data.get("result", [])
        except Exception:
            return await self._rest_fallback.search_traces(query)

    async def get_trace_details(self, trace_id: str) -> dict[str, Any]:
        try:
            headers = {"SIGNOZ-API-KEY": self.api_key} if self.api_key else {}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/mcp",
                    headers=headers,
                    json={"tool": "signoz_get_trace_details", "args": {"trace_id": trace_id}},
                )
                response.raise_for_status()
                data = response.json()
                return data.get("result", {})
        except Exception:
            return await self._rest_fallback.get_trace_details(trace_id)

    async def aggregate_traces(self, query: str) -> dict[str, Any]:
        try:
            headers = {"SIGNOZ-API-KEY": self.api_key} if self.api_key else {}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/mcp",
                    headers=headers,
                    json={"tool": "signoz_aggregate_traces", "args": {"query": query}},
                )
                response.raise_for_status()
                data = response.json()
                return data.get("result", {})
        except Exception:
            return await self._rest_fallback.aggregate_traces(query)


def _classify_outcome(survival_score: float) -> SurvivalOutcome:
    """Map a numerical survival score to an outcome label."""
    if survival_score >= 0.9:
        return SurvivalOutcome.FULL_RECOVERY
    elif survival_score >= 0.6:
        return SurvivalOutcome.GRACEFUL_DEGRADATION
    elif survival_score >= 0.3:
        return SurvivalOutcome.PARTIAL_COMPLETION
    return SurvivalOutcome.SILENT_FAILURE


def _estimate_confidence(trace_data: dict[str, Any]) -> float:
    """Estimate confidence in the evaluation based on trace completeness.

    Returns a value between 0.0 and 1.0. Capped at 0.5 if the
    trace data is incomplete or missing key fields.
    """
    spans = trace_data.get("spans", []) if isinstance(trace_data, dict) else []
    if not spans:
        return 0.3

    span_count = len(spans)
    has_errors = any(
        s.get("status", {}).get("code") == "ERROR" for s in spans if isinstance(s, dict)
    )
    has_chaos_attrs = any(
        isinstance(s, dict) and s.get("attributes", {}).get("chaos.injected")
        for s in spans
    )

    score = 0.5
    if span_count >= 3:
        score += 0.15
    if has_errors:
        score += 0.15
    if has_chaos_attrs:
        score += 0.15
    if span_count < 2:
        score = min(score, 0.5)

    return min(score, 1.0)


def _extract_evidence_spans(trace_data: dict[str, Any]) -> list[str]:
    """Extract span IDs that contain evidence of faults or recovery."""
    spans = trace_data.get("spans", []) if isinstance(trace_data, dict) else []
    evidence = []
    for span in spans:
        if not isinstance(span, dict):
            continue
        span_id = span.get("span_id", "") or span.get("spanId", "")
        if not span_id:
            continue
        attrs = span.get("attributes", {})
        status = span.get("status", {})
        if attrs.get("chaos.injected") or status.get("code") == "ERROR":
            evidence.append(span_id)
    return evidence


class EvaluatorAgent:
    """LLM-as-a-Judge evaluator that analyzes traces and produces post-mortems.

    Uses a structured prompting approach with Pydantic-validated output.
    The confidence score reflects how complete the trace data was.
    """

    def __init__(self, backend: Optional[TraceQueryBackend] = None):
        self.backend = backend or self._default_backend()

    def _default_backend(self) -> TraceQueryBackend:
        mode = os.environ.get("SIGNOZ_BACKEND_MODE", "rest")
        api_key = os.environ.get("SIGNOZ_API_KEY", "")

        if mode == "mcp":
            url = os.environ.get("SIGNOZ_MCP_URL", "http://localhost:8000")
            return MCPTraceQueryBackend(base_url=url, api_key=api_key)

        url = os.environ.get("SIGNOZ_URL", "http://localhost:8080")
        return RESTTraceQueryBackend(base_url=url, api_key=api_key)

    async def evaluate(self, trace_id: str) -> ExperimentPostmortem:
        """Evaluate a trace and produce a structured post-mortem report."""
        trace_data = await self._fetch_trace_data(trace_id)
        return self._analyze_trace(trace_id, trace_data)

    async def _fetch_trace_data(self, trace_id: str) -> dict[str, Any]:
        """Fetch trace details from the backend."""
        return await self.backend.get_trace_details(trace_id)

    def _analyze_trace(
        self, trace_id: str, trace_data: dict[str, Any]
    ) -> ExperimentPostmortem:
        """Analyze trace data and produce a post-mortem.

        This is a rule-based analysis that works without needing
        an actual LLM connection. In production, this would use
        an LLM-as-a-Judge with structured output.
        """
        spans = trace_data.get("spans", []) if isinstance(trace_data, dict) else []
        evidence_spans = _extract_evidence_spans(trace_data)
        confidence = _estimate_confidence(trace_data)

        # Determine fault type from chaos attributes
        fault_type = FaultType.TIMEOUT
        recovery_action = "No fault detected"
        for span in spans:
            if not isinstance(span, dict):
                continue
            attrs = span.get("attributes", {}) if isinstance(span.get("attributes"), dict) else {}
            raw_fault = attrs.get("chaos.fault_type", "")
            if raw_fault == "rate-limit":
                fault_type = FaultType.RATE_LIMIT
            elif raw_fault == "semantic-corruption":
                fault_type = FaultType.SEMANTIC_CORRUPTION
            elif raw_fault == "memory-poisoning":
                fault_type = FaultType.MEMORY_POISONING

        # Analyze recovery based on span statuses
        error_count = 0
        success_count = 0
        for span in spans:
            if not isinstance(span, dict):
                continue
            status = span.get("status", {}) if isinstance(span.get("status"), dict) else {}
            if status.get("code") == "ERROR":
                error_count += 1
            elif status.get("code") in ("OK", "ok"):
                success_count += 1

        has_recovery = error_count > 0 and success_count > 0
        total = error_count + success_count

        if total == 0:
            survival_score = 0.5
            recovery_action = "No spans with status found"
        elif error_count == 0:
            survival_score = 1.0
            recovery_action = "All operations completed without errors"
        elif has_recovery:
            recovery_ratio = success_count / total
            survival_score = 0.3 + (0.7 * recovery_ratio)
            recovery_action = f"Recovered from {error_count} error(s), {success_count} operation(s) succeeded"
        else:
            survival_score = 0.0
            recovery_action = f"All {error_count} operation(s) failed, no recovery detected"

        outcome = _classify_outcome(survival_score)

        summary = (
            f"Trace {trace_id}: injected {fault_type.value} fault. "
            f"Survival score: {survival_score:.2f} ({outcome.value}). "
            f"Confidence: {confidence:.2f}. "
            f"{recovery_action}"
        )

        return ExperimentPostmortem(
            trace_id=trace_id,
            injected_fault_type=fault_type,
            target_recovery_action=recovery_action,
            survival_score=round(survival_score, 2),
            confidence_score=round(confidence, 2),
            outcome=outcome,
            evidence_spans=evidence_spans,
            summary=summary,
        )
