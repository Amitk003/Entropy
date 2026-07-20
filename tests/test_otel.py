import os
import pytest
from unittest.mock import patch
from opentelemetry.trace import Tracer
from entropy.otel import setup_otel


def test_setup_otel_returns_tracer():
    tracer = setup_otel()
    assert isinstance(tracer, Tracer)


@patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_PROTOCOL": "grpc"})
def test_setup_otel_uses_grpc_when_protocol_is_grpc():
    with patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter") as mock_grpc:
        setup_otel()
        mock_grpc.assert_called_once()


@patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf"})
def test_setup_otel_uses_http_when_protocol_is_http():
    with patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter") as mock_http:
        setup_otel()
        mock_http.assert_called_once()
