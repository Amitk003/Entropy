import pytest
from unittest.mock import patch
from opentelemetry.trace import Tracer
from entropy.otel import setup_otel

def test_setup_otel_returns_tracer():
    tracer = setup_otel()
    assert isinstance(tracer, Tracer)

@patch("entropy.otel._is_endpoint_reachable")
def test_setup_otel_grpc_fallback(mock_reachable):
    # Case 1: Test when gRPC is reachable, gRPC exporter should be used
    mock_reachable.return_value = True
    with patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter") as mock_grpc:
        setup_otel()
        mock_grpc.assert_called_once()

    # Case 2: Test fallback when gRPC is unreachable, HTTP exporter should be used
    mock_reachable.return_value = False
    with patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter") as mock_http:
        setup_otel()
        mock_http.assert_called_once()
