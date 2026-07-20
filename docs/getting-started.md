# Getting Started

This guide helps you set up Project Entropy from scratch and run your first resilience test.

## What You Need

- Python 3.12 or higher
- Docker Desktop
- Foundry CLI
- An OpenAI or Anthropic API key

## Step 1: Install Python Dependencies

Create a virtual environment and install everything:

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate  # Linux/Mac

pip install -e ".[dev]"
```

## Step 2: Configure Environment

Copy the example env file and fill in your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your editor and add your keys:
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
- `SIGNOZ_API_KEY` (you get this after deploying SigNoz)

## Step 3: Deploy SigNoz

Follow the [Deployment Guide](deployment.md) to set up the SigNoz observability stack.

## Step 4: Run a Baseline Test

Run the target agent without any fault injection:

```bash
python -m entropy.cli run --mode baseline
```

This sends traces to SigNoz. Open the SigNoz UI at http://localhost:8080 and check the Trace Explorer. You should see spans with `gen_ai.*` attributes.

## Step 5: Run a Chaos Experiment

Run the target agent with fault injection:

```bash
python -m entropy.cli run --mode chaos --fault rate-limit
```

The agent will experience a simulated rate limit. The trace in SigNoz will show a red error span with `chaos.injected=true`.

## Step 6: Generate a Post-Mortem Report

Ask the Evaluator Agent to analyze the trace:

```bash
python -m entropy.cli evaluate --trace-id <trace-id-from-sigNoz>
```

The Evaluator Agent connects to SigNoz through the MCP server and writes a structured report with a survival score.

## Step 7: Open the Command Center

Launch the Streamlit dashboard:

```bash
streamlit run src/entropy/ui/dashboard.py
```

This gives you a visual interface to run experiments and view results side by side.

## Next Steps

- Read the [Architecture Guide](architecture.md) to understand the system design
- Read the [Chaos Injector Guide](chaos-injector.md) to learn about fault types
- Read the [Evaluator Agent Guide](evaluator-agent.md) to understand the LLM-as-a-Judge workflow
