# Deployment Guide

This guide walks you through setting up the SigNoz observability stack. You need Docker Desktop and the Foundry CLI installed on your machine.

## Prerequisites

- Docker Desktop 4.0+ (with WSL 2 backend on Windows)
- Foundry CLI (`foundryctl`)
- At least 8GB of RAM allocated to Docker

If you are on Windows with WSL 2, run the WSL helper script first:

```powershell
powershell -ExecutionPolicy Bypass -File infra/wsl_config_helper.ps1
```

This script creates a `.wslconfig` file with 8GB memory and 4 CPU cores, then restarts WSL.

## Deploy SigNoz

```bash
# Step 1: Check your environment is ready
foundryctl gauge -f infra/casting.yaml

# Step 2: Generate deployment manifests and lock file
foundryctl forge -f infra/casting.yaml

# Step 3: Deploy the stack
foundryctl cast -f infra/casting.yaml
```

After deployment, you can access:
- SigNoz UI at http://localhost:8080
- OTel gRPC endpoint at localhost:4317
- OTel HTTP endpoint at localhost:4318
- SigNoz MCP server at localhost:8000

## Verify the Deployment

1. Open http://localhost:8080 in your browser
2. Create a login account (first-time setup)
3. Go to Settings -> Service Accounts
4. Generate an API key for the Evaluator Agent

## Shut Down

```bash
foundryctl destroy -f infra/casting.yaml
```

## Troubleshooting

### ClickHouse fails with EOF error

This usually means Docker does not have enough memory. Run the WSL helper script (Windows) or increase Docker Desktop memory settings.

### Port already in use

Check if something is already running on ports 8080, 4317, 4318, or 8000:

```bash
netstat -ano | findstr :8080
```

### MCP server not responding

Make sure the MCP server is enabled in `infra/casting.yaml` (`spec.mcp.spec.enabled: true`). After changing the config, re-run `foundryctl forge` and `foundryctl cast`.
