"""OpenTelemetry setup and configuration."""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource


def setup_otel(service_name: str = "project-entropy") -> trace.Tracer:
    """Configure OpenTelemetry with gRPC exporter and fallback to HTTP."""
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "0.1.0",
    })

    provider = TracerProvider(resource=resource)

    # Primary: gRPC exporter on port 4317
    grpc_endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://localhost:4317",
    )

    try:
        grpc_exporter = OTLPSpanExporter(endpoint=grpc_endpoint)
        provider.add_span_processor(BatchSpanProcessor(grpc_exporter))
    except Exception as exc:
        # Fallback: HTTP exporter on port 4318
        import warnings
        warnings.warn(
            f"gRPC exporter failed ({exc}), falling back to HTTP exporter",
        )
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter as HTTPOTLPSpanExporter,
        )
        http_endpoint = os.getenv(
            "OTEL_EXPORTER_OTLP_HTTP_ENDPOINT",
            "http://localhost:4318/v1/traces",
        )
        http_exporter = HTTPOTLPSpanExporter(endpoint=http_endpoint)
        provider.add_span_processor(BatchSpanProcessor(http_exporter))

    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)
