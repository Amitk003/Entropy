"""Project Entropy CLI - Run experiments and view results."""

import typer
from typing import Optional

app = typer.Typer()


@app.command()
def run(
    mode: str = typer.Option("baseline", help="Run mode: baseline or chaos"),
    fault: Optional[str] = typer.Option(None, help="Fault type for chaos mode"),
    experiment_id: Optional[str] = typer.Option(None, help="Experiment identifier"),
):
    """Run a target agent workflow with optional chaos injection."""
    typer.echo(f"Running in {mode} mode...")
    if mode == "chaos" and fault:
        typer.echo(f"  Injecting fault: {fault}")
    typer.echo("Workflow complete. Trace ID: example-trace-id")


@app.command()
def evaluate(
    trace_id: str = typer.Argument(..., help="Trace ID to evaluate"),
):
    """Evaluate a trace and generate a post-mortem report."""
    typer.echo(f"Evaluating trace: {trace_id}")
    typer.echo("  Connecting to SigNoz MCP server...")
    typer.echo("  Retrieving span tree...")
    typer.echo("  Generating post-mortem report...")
    typer.echo("  Report ready.")


@app.command()
def config():
    """Show current configuration."""
    typer.echo("Project Entropy Configuration")
    typer.echo("  SigNoz backend: http://localhost:8000")
    typer.echo("  OTel endpoint: http://localhost:4317")
    typer.echo("  LLM provider: OpenAI GPT-4o")


if __name__ == "__main__":
    app()
