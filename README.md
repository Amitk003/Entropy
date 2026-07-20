# Project Entropy

**Automated Resilience Testing for AI Agent Systems**

AI agents fail silently. They hit API rate limits, receive corrupted data, get stuck in infinite reasoning loops, and hallucinate confidently wrong answers. These failures are hard to find because they only show up under real-world stress. Project Entropy changes that.

## What It Does

Project Entropy deliberately injects controlled failures into your AI agent's environment then automatically checks how well your agent recovers. It turns unpredictable production crashes into measurable data you can act on.

- **Inject faults** into LLM calls and tool executions (timeouts, rate limits, data corruption, memory poisoning)
- **Monitor everything** with OpenTelemetry powered traces that capture every reasoning step and token spend
- **Get automated reports** the Evaluator Agent reads your traces through SigNoz and produces a clear post-mortem with a survival score
- **Visualize resilience** with live dashboards that show your agent's recovery rate, latency impact, and failure patterns

## Architecture

```
Target Agent (LangGraph)  -->  Chaos Injector (decorator + transport middleware)
        |                              |
        +--- OpenTelemetry traces -----+
        |
        v
   SigNoz Backend (ClickHouse + MCP Server)
        |
        v
   Evaluator Agent (LLM-as-a-Judge)
        |
        v
   Post-mortem Report + Dashboard
```

## Quick Start

If you are on Windows with WSL 2, run this in PowerShell as Administrator first to allocate enough memory for ClickHouse:

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\wsl_config_helper.ps1
```

Then run these commands:

```bash
# 1. Deploy the observability stack
foundryctl cast -f infra/casting.yaml

# 2. Set up your environment
cp .env.example .env
# Edit .env and add your API keys

# 3. Run a baseline test
python -m entropy.cli run --mode baseline

# 4. Run a chaos experiment
python -m entropy.cli run --mode chaos --fault rate-limit

# 5. View the post-mortem report
python -m entropy.cli evaluate --trace-id <trace-id>

# 6. Open the Command Center
streamlit run src/entropy/ui/dashboard.py
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | LangGraph 0.3+ |
| LLM providers | OpenAI GPT-4o, Anthropic Claude 3.5 |
| Telemetry | OpenTelemetry (gRPC + HTTP) |
| Observability backend | SigNoz (ClickHouse) |
| MCP server | SigNoz MCP |
| Data validation | Pydantic v2 |
| CLI | Typer |
| Web UI | Streamlit |

## Documentation

Full documentation is in the `docs/` folder:

- `docs/getting-started.md` - Setup and first run
- `docs/architecture.md` - System design and components
- `docs/chaos-injector.md` - How fault injection works
- `docs/evaluator-agent.md` - Automated post-mortem analysis
- `docs/dashboard.md` - Command Center guide
- `docs/deployment.md` - Foundry deployment and configuration
- `docs/testing.md` - Testing strategy and validation
