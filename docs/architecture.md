# Architecture Guide

This document explains how Project Entropy is built and how its parts fit together.

## High-Level Design

The system has four main parts that work together:

1. **Target Agent** -- The AI application being tested. It runs inside LangGraph and calls tools and LLMs to complete tasks.
2. **Chaos Injector** -- A middleware layer that introduces failures into the agent's environment. It uses a Python decorator for tool calls and HTTP transport middleware for LLM streaming.
3. **SigNoz Backend** -- Stores all traces, metrics, and logs. Uses ClickHouse for fast querying. Exposes an MCP server so AI agents can query telemetry with natural language.
4. **Evaluator Agent** -- An AI agent that reads traces from SigNoz after a chaos experiment and writes a post-mortem report with a survival score.

## Data Flow

```
User Input
    |
    v
Target Agent (LangGraph StateGraph)
    |
    +--> classify_intent node
    +--> lookup_customer node (uses mock_db_lookup tool)
    +--> execute_api_call node (uses mock_api_call tool)
    +--> generate_response node
    |
    v
OpenTelemetry traces (gRPC primary, HTTP fallback)
    |
    v
SigNoz (ClickHouse storage + MCP server)
    |
    v
Evaluator Agent queries traces and produces report
```

## Target Agent

The target agent is built with LangGraph's StateGraph. It has four nodes:

| Node | What it does |
|------|-------------|
| classify_intent | Reads the input and decides what the user wants to do |
| lookup_customer | Calls mock_db_lookup to find customer data |
| execute_api_call | Calls mock_api_call to run the requested action |
| generate_response | Combines all data into a readable response |

Each node takes the current state, does its work, and returns updates. The graph structure decides which node runs next.

## Agent Graph Structure

```
classify_intent
    |
    +--> customer-lookup --> lookup_customer --> execute_api_call --> generate_response --> END
    +--> process-payment --> execute_api_call --------------------> generate_response --> END
    +--> unknown ---------> END
```

## Telemetry

Every agent run produces OpenTelemetry traces with three layers:

1. **gen_ai.* attributes** -- Captured automatically by opentelemetry-instrumentation-openai-v2. Includes model name, tokens used, finish reasons.
2. **Custom chaos attributes** -- Added by the Chaos Injector when it injects a fault. Includes `chaos.injected`, `chaos.fault_type`, `chaos.experiment_id`.
3. **Run metadata** -- Added by the CLI. Includes `run.mode`, `run.input`, `run.response`.

## Source Code Layout

```
src/entropy/
    __init__.py       - Package init
    __version__.py    - Version number
    agent.py          - LangGraph agent (nodes and graph builder)
    cli.py            - Typer CLI (run, evaluate, config commands)
    models.py         - Pydantic models for experiments and reports
    otel.py           - OpenTelemetry setup (gRPC + HTTP fallback)
    tools.py          - Mock tools (database, API, formatting)
```

## Configuration

All configuration is handled through environment variables. See `.env.example` for the full list.

Key settings:
- `OTEL_EXPORTER_OTLP_ENDPOINT` -- gRPC endpoint (default: localhost:4317)
- `SIGNOZ_API_KEY` -- API key for MCP authentication
- `SIGNOZ_BACKEND_MODE` -- mcp or rest (fallback)
