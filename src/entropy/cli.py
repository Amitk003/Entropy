"""Project Entropy CLI - Run experiments and view results."""

import asyncio
import os
import typer
from typing import Optional

from entropy.agent import run_agent
from entropy.evaluator import EvaluatorAgent
from entropy.otel import setup_otel

app = typer.Typer()


@app.command()
def run(
    input_text: str = typer.Option("Lookup customer C001", help="Input text for the agent"),
    mode: str = typer.Option("baseline", help="Run mode: baseline or chaos"),
    fault: Optional[str] = typer.Option(None, help="Fault type for chaos mode"),
    experiment_id: Optional[str] = typer.Option(None, help="Experiment identifier"),
):
    """Run the target agent with optional chaos injection."""
    tracer = setup_otel()
    thread_id = experiment_id or "test-run"

    typer.echo(f"Running in {mode} mode...")
    typer.echo(f"  Input: {input_text}")

    if mode == "chaos" and fault:
        os.environ["CHAOS_FAULT_TYPE"] = fault
        os.environ["CHAOS_ENABLED"] = "true"
        typer.echo(f"  Injecting fault: {fault}")

    with tracer.start_as_current_span("entropy-run") as span:
        span.set_attribute("run.mode", mode)
        span.set_attribute("run.input", input_text)

        if mode == "chaos":
            span.set_attribute("chaos.injected", True)
            span.set_attribute("chaos.fault_type", fault or "unknown")
            span.set_attribute("chaos.experiment_id", thread_id)

        result = run_agent(input_text, thread_id)

        span.set_attribute("run.response", result.get("response", ""))

    typer.echo(f"  Response: {result.get('response', 'No response')}")
    typer.echo(f"  Trace ID: {thread_id}")

    if mode == "chaos":
        os.environ.pop("CHAOS_FAULT_TYPE", None)
        os.environ.pop("CHAOS_ENABLED", None)


@app.command()
def evaluate(
    trace_id: str = typer.Argument(..., help="Trace ID to evaluate"),
    backend: str = typer.Option("rest", help="Backend type: rest or mcp"),
):
    """Evaluate a trace and generate a post-mortem report."""
    typer.echo(f"Evaluating trace: {trace_id}")
    typer.echo(f"  Backend: {backend}")

    os.environ["SIGNOZ_BACKEND_MODE"] = backend

    async def _run():
        evaluator = EvaluatorAgent()
        try:
            report = await evaluator.evaluate(trace_id)
            return report
        finally:
            await evaluator.backend.close()

    report = asyncio.run(_run())

    typer.echo("")
    typer.echo("Post-Mortem Report")
    typer.echo("=" * 40)
    typer.echo(f"  Trace ID:          {report.trace_id}")
    typer.echo(f"  Injected Fault:    {report.injected_fault_type.value}")
    typer.echo(f"  Outcome:           {report.outcome.value}")
    typer.echo(f"  Survival Score:    {report.survival_score}")
    typer.echo(f"  Confidence Score:  {report.confidence_score}")
    typer.echo(f"  Recovery Action:   {report.target_recovery_action}")
    if report.evidence_spans:
        typer.echo(f"  Evidence Spans:    {', '.join(report.evidence_spans[:5])}")
    typer.echo("")
    typer.echo(f"  Summary: {report.summary}")


@app.command()
def config():
    """Show current configuration."""
    typer.echo("Project Entropy Configuration")
    typer.echo("  SigNoz backend: http://localhost:8000")
    typer.echo("  OTel endpoint: http://localhost:4317")
    typer.echo("  LLM provider: OpenAI GPT-4o")


if __name__ == "__main__":
    app()
