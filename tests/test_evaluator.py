import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from entropy.evaluator import (
    EvaluatorAgent,
    RESTTraceQueryBackend,
    MCPTraceQueryBackend,
    _classify_outcome,
    _estimate_confidence,
    _extract_evidence_spans,
)
from entropy.models import (
    ExperimentPostmortem,
    FaultType,
    SurvivalOutcome,
)


class TestOutcomeClassification:
    def test_full_recovery(self):
        assert _classify_outcome(1.0) == SurvivalOutcome.FULL_RECOVERY
        assert _classify_outcome(0.95) == SurvivalOutcome.FULL_RECOVERY
        assert _classify_outcome(0.9) == SurvivalOutcome.FULL_RECOVERY

    def test_graceful_degradation(self):
        assert _classify_outcome(0.8) == SurvivalOutcome.GRACEFUL_DEGRADATION
        assert _classify_outcome(0.6) == SurvivalOutcome.GRACEFUL_DEGRADATION

    def test_partial_completion(self):
        assert _classify_outcome(0.5) == SurvivalOutcome.PARTIAL_COMPLETION
        assert _classify_outcome(0.3) == SurvivalOutcome.PARTIAL_COMPLETION

    def test_silent_failure(self):
        assert _classify_outcome(0.2) == SurvivalOutcome.SILENT_FAILURE
        assert _classify_outcome(0.0) == SurvivalOutcome.SILENT_FAILURE


class TestConfidenceEstimation:
    def test_low_confidence_empty_trace(self):
        assert _estimate_confidence({}) == 0.3

    def test_medium_confidence_few_spans(self):
        trace = {"spans": [{"span_id": "1"}, {"span_id": "2"}]}
        score = _estimate_confidence(trace)
        assert score >= 0.5
        assert score <= 0.8

    def test_high_confidence_with_errors_and_chaos(self):
        trace = {
            "spans": [
                {"span_id": "1", "status": {"code": "OK"}},
                {"span_id": "2", "status": {"code": "ERROR"}},
                {"span_id": "3", "attributes": {"chaos.injected": True}},
            ]
        }
        score = _estimate_confidence(trace)
        assert score >= 0.8
        assert score <= 1.0


class TestEvidenceExtraction:
    def test_extracts_chaos_spans(self):
        trace = {
            "spans": [
                {"span_id": "s1", "attributes": {"chaos.injected": True}},
                {"span_id": "s2", "attributes": {}},
                {"span_id": "s3", "status": {"code": "ERROR"}},
            ]
        }
        evidence = _extract_evidence_spans(trace)
        assert "s1" in evidence
        assert "s3" in evidence
        assert "s2" not in evidence

    def test_empty_trace_returns_empty(self):
        assert _extract_evidence_spans({}) == []


class TestRESTTraceQueryBackend:
    @pytest.mark.asyncio
    async def test_search_traces_returns_list(self):
        backend = RESTTraceQueryBackend(api_key="test-key")
        with patch.object(backend._client, "get", new=AsyncMock()) as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": [{"trace_id": "abc"}]}
            mock_get.return_value = mock_response

            results = await backend.search_traces("chaos.injected=true")
            assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_traces_on_error_returns_empty(self):
        backend = RESTTraceQueryBackend()
        with patch.object(backend._client, "get", new=AsyncMock(side_effect=Exception("No connection"))):
            results = await backend.search_traces("test")
            assert results == []


class TestEvaluatorAgent:
    @pytest.mark.asyncio
    async def test_evaluate_returns_postmortem(self):
        backend = RESTTraceQueryBackend()
        evaluator = EvaluatorAgent(backend=backend)

        with patch.object(
            backend, "get_trace_details", new=AsyncMock(return_value={
                "trace_id": "test-123",
                "spans": [
                    {
                        "span_id": "s1",
                        "attributes": {"chaos.injected": True, "chaos.fault_type": "rate-limit"},
                        "status": {"code": "ERROR"},
                    },
                    {
                        "span_id": "s2",
                        "attributes": {},
                        "status": {"code": "OK"},
                    },
                ],
            }),
        ):
            report = await evaluator.evaluate("test-123")

        assert isinstance(report, ExperimentPostmortem)
        assert report.trace_id == "test-123"
        assert report.injected_fault_type == FaultType.RATE_LIMIT
        assert report.survival_score > 0
        assert report.confidence_score > 0
        assert len(report.evidence_spans) > 0

    @pytest.mark.asyncio
    async def test_evaluate_all_success_no_chaos(self):
        backend = RESTTraceQueryBackend()
        evaluator = EvaluatorAgent(backend=backend)

        with patch.object(
            backend, "get_trace_details", new=AsyncMock(return_value={
                "trace_id": "test-456",
                "spans": [
                    {"span_id": "s1", "attributes": {}, "status": {"code": "OK"}},
                    {"span_id": "s2", "attributes": {}, "status": {"code": "OK"}},
                ],
            }),
        ):
            report = await evaluator.evaluate("test-456")

        assert report.survival_score == 1.0
        assert report.outcome == SurvivalOutcome.FULL_RECOVERY
        assert report.injected_fault_type == FaultType.TIMEOUT  # default

    @pytest.mark.asyncio
    async def test_evaluate_all_errors_no_recovery(self):
        backend = RESTTraceQueryBackend()
        evaluator = EvaluatorAgent(backend=backend)

        with patch.object(
            backend, "get_trace_details", new=AsyncMock(return_value={
                "trace_id": "test-789",
                "spans": [
                    {"span_id": "s1", "attributes": {"chaos.injected": True}, "status": {"code": "ERROR"}},
                    {"span_id": "s2", "attributes": {}, "status": {"code": "ERROR"}},
                ],
            }),
        ):
            report = await evaluator.evaluate("test-789")

        assert report.survival_score == 0.0
        assert report.outcome == SurvivalOutcome.SILENT_FAILURE
        assert "failed" in report.target_recovery_action


class TestMCPTraceQueryBackend:
    @pytest.mark.asyncio
    async def test_mcp_fallback_to_rest_on_error(self):
        mcp_backend = MCPTraceQueryBackend(api_key="test-key")

        with patch.object(
            mcp_backend._client, "post",
            new=AsyncMock(side_effect=Exception("MCP connection failed")),
        ):
            with patch.object(
                mcp_backend._rest_fallback, "get_trace_details",
                new=AsyncMock(return_value={"trace_id": "fallback", "spans": []}),
            ):
                result = await mcp_backend.get_trace_details("test-id")
                assert result["trace_id"] == "fallback"
