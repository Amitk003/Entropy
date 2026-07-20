# Chaos Injector Guide

The Chaos Injector is the part of Project Entropy that deliberately breaks things to test your agent. It sits between your agent and its tools and APIs, and introduces failures on purpose.

## How It Works

The injector has two parts:

### 1. Tool Call Interception (Decorator)

The `@chaos_injectable` decorator wraps your tool functions. When chaos mode is on, it can:

- **Timeout** -- Sleep for a few seconds then raise `TimeoutError`. Tests if your agent has retry logic.
- **Rate limit** -- Raise `RateLimitError` (simulated HTTP 429). Tests if your agent backs off properly.
- **Semantic corruption** -- Reverse strings, negate numbers, or inject garbage into the tool output. Tests if your agent validates its inputs.
- **Memory poisoning** -- Return contradictory data to simulate state corruption across agents.

The decorator reads settings from environment variables so it can be toggled without code changes.

### 2. Streaming LLM Interception (Transport Layer)

The `ChaosHttpTransport` class wraps `httpx.AsyncHTTPTransport`. It intercepts streaming LLM responses chunk by chunk and can:

- Drop a chunk mid-stream
- Inject a garbage chunk
- Truncate the response mid-sentence
- Raise a timeout on the stream

This tests how your agent handles streaming-specific failures.

## How to Use

### Via CLI

```bash
# Run a baseline test (no faults)
python -m entropy.cli run --mode baseline

# Run with a timeout fault
python -m entropy.cli run --mode chaos --fault timeout

# Run with a rate limit
python -m entropy.cli run --mode chaos --fault rate-limit

# Run with semantic corruption
python -m entropy.cli run --mode chaos --fault semantic-corruption

# Run with memory poisoning
python -m entropy.cli run --mode chaos --fault memory-poisoning
```

### Via Code

```python
import os
from entropy.tools import mock_db_lookup

# Enable chaos
os.environ["CHAOS_ENABLED"] = "true"
os.environ["CHAOS_FAULT_TYPE"] = "rate-limit"

# The tool will now raise RateLimitError about 30% of the time
try:
    result = mock_db_lookup("C001")
except RateLimitError:
    print("Tool hit a rate limit!")
```

## Configuration

All settings are environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CHAOS_ENABLED` | `false` | Set to `true` to activate fault injection |
| `CHAOS_FAULT_TYPE` | `timeout` | One of: `timeout`, `rate-limit`, `semantic-corruption`, `memory-poisoning` |
| `CHAOS_PROBABILITY` | `0.3` | Probability (0.0 to 1.0) of injecting a fault per call |
| `CHAOS_TIMEOUT_DELAY` | `5.0` | Seconds to wait before timing out |
| `CHAOS_EXPERIMENT_ID` | (empty) | Attached to OTel spans for grouping |

## Writing Custom Faults

The chaos injector follows a simple pattern. To add a new fault type:

1. Add the fault handling logic in the `wrapper()` function inside `chaos_injectable`
2. Raise a standard Python exception so the agent's error handling catches it
3. Call `_inject_chaos_span_attributes()` to tag the OTel span
4. Use the new fault type string in `CHAOS_FAULT_TYPE`

## Telemetry

When the injector activates, it sets these custom OTel attributes on the current span:

- `chaos.injected` -- Always `true` when a fault is injected
- `chaos.fault_type` -- The type of fault (e.g. `timeout`, `rate-limit`)
- `chaos.experiment_id` -- Links multiple faults to the same experiment run

These attributes let the Evaluator Agent find the exact spans where faults happened.
