"""OpenTelemetry setup and configuration."""

import os
import socket
import warnings
from urllib.parse import urlparse
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource


def _is_endpoint_reachable(url: str) -> bool:
    """Check if a URL endpoint is reachable by attempting a socket connection."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 4317
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except Exception:
        return False


def setup_otel(service_name: str = "project-entropy") -> trace.Tracer:
    """Configure OpenTelemetry with gRPC exporter and fallback to HTTP."""
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "0.1.0",
    })

    provider = TracerProvider(resource=resource)

    # Read endpoints from environment or defaults
    grpc_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    http_endpoint = os.getenv("OTEL_EXPORTER_OTLP_HTTP_ENDPOINT", "http://localhost:4318/v1/traces")

    # Connect via gRPC if reachable, otherwise fall back to HTTP
    if _is_endpoint_reachable(grpc_endpoint):
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        exporter = OTLPSpanExporter(endpoint=grpc_endpoint)
    else:
        warnings.warn(
            f"Primary gRPC endpoint {grpc_endpoint} is unreachable. Falling back to HTTP exporter."
        )
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter as HTTPOTLPSpanExporter,
        )
        exporter = HTTPOTLPSpanExporter(endpoint=http_endpoint)

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)
