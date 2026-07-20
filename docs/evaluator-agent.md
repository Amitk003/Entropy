# Evaluator Agent Guide

The Evaluator Agent reads traces from SigNoz after a chaos experiment and produces a post-mortem report with a survival score. It acts like an automated SRE engineer that never sleeps.

## How It Works

1. A chaos experiment runs and generates traces in SigNoz
2. You call the Evaluator Agent with a trace ID
3. The agent fetches the full span tree from SigNoz
4. It analyzes the spans for errors, recovery actions, and chaos attributes
5. It produces a structured report with a survival score and confidence score

## Backends

The Evaluator Agent supports two backends for querying SigNoz:

### REST Backend (Default)

Uses SigNoz's REST API directly. No extra setup needed. Good for testing and CI.

```bash
python -m entropy.cli evaluate --trace-id abc123 --backend rest
```

### MCP Backend

Uses the SigNoz MCP server for natural language queries. Requires the MCP server to be running (port 8000). Falls back to REST automatically if MCP is unreachable.

```bash
python -m entropy.cli evaluate --trace-id abc123 --backend mcp
```

## Interpreting the Report

The Evaluator Agent produces a report with these fields:

| Field | What it means |
|-------|---------------|
| **trace_id** | The trace that was evaluated |
| **injected_fault_type** | The type of fault detected (timeout, rate-limit, etc.) |
| **outcome** | One of: full-recovery, graceful-degradation, partial-completion, silent-failure |
| **survival_score** | 0.0 to 1.0. How well the agent handled the fault. |
| **confidence_score** | 0.0 to 1.0. How complete the trace data was. |
| **evidence_spans** | Span IDs where faults or errors were found |
| **summary** | A plain-text summary of the findings |

### Survival Score Scale

| Score | Outcome | Meaning |
|-------|---------|---------|
| 0.9 - 1.0 | Full recovery | Agent retried and completed successfully |
| 0.6 - 0.89 | Graceful degradation | Agent recovered but with degraded output |
| 0.3 - 0.59 | Partial completion | Agent continued but produced incorrect output |
| 0.0 - 0.29 | Silent failure | Agent failed without recovery |

### Confidence Score

The confidence score is calculated from the trace itself:

- **Low (0.3)** -- No spans found in the trace
- **Medium (0.5-0.65)** -- Fewer than 3 spans or no error data
- **High (0.8+)** -- Multiple spans with error codes and chaos attributes

If confidence is below 0.7, the report is flagged for human review.

## Programmatic Use

```python
import asyncio
from entropy.evaluator import EvaluatorAgent

async def main():
    agent = EvaluatorAgent()
    report = await agent.evaluate("trace-id-here")
    print(f"Survival score: {report.survival_score}")
    print(f"Outcome: {report.outcome.value}")
    print(f"Summary: {report.summary}")

asyncio.run(main())
```

## Quality Controls

The Evaluator Agent has three quality controls to prevent bad reports:

1. **Pydantic validation** -- The report is a validated `ExperimentPostmortem` model. Malformed data is rejected.
2. **Confidence scoring** -- If trace data is incomplete, the confidence score drops and the report is flagged.
3. **Span evidence** -- Every report tracks which span IDs back up its findings. No evidence means no claim.
