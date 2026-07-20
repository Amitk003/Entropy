# Testing Guide

This document describes the testing strategy for Project Entropy.

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src/entropy -v

# Run a specific test file
python -m pytest tests/test_evaluator.py -v

# Run a specific test class
python -m pytest tests/test_chaos_injector.py::TestChaosInjector -v
```

## Test Structure

```
tests/
├── test_agent.py           # 10 tests - LangGraph agent nodes, graph build, full runs
├── test_chaos_injector.py  # 12 tests - fault types, transport, probability skip
├── test_evaluator.py       # 15 tests - outcome classification, confidence, backends
├── test_otel.py            # 2 tests  - OTel setup, gRPC fallback
└── test_tools.py           # 5 tests  - mock DB, API, formatting
```

## Unit Tests

### Agent (`test_agent.py`)
- Intent classification (payment, lookup, unknown)
- Customer lookup (found, not found)
- API call execution
- Response generation (with data, empty)
- Graph construction
- Routing logic
- Full agent run

### Chaos Injector (`test_chaos_injector.py`)
- Enabled/disabled flag
- Passthrough when disabled
- Timeout fault
- Rate-limit fault
- Semantic corruption (dict, string)
- Memory poisoning
- Probability-based skip
- HTTP transport corruption

### Evaluator (`test_evaluator.py`)
- Outcome classification for all 4 tiers
- Confidence scoring (low, medium, high)
- Span evidence extraction
- REST backend (positive and error cases)
- MCP backend with fallback
- Full evaluate method with live trace

### OTel (`test_otel.py`)
- Tracer creation
- gRPC to HTTP fallback

### Tools (`test_tools.py`)
- Mock DB lookup (found, not found)
- Mock API call (success, unknown action)
- Response formatting

## Writing Tests

Tests use `pytest` with `pytest-asyncio` for async test support. Mock data is defined as module-level constants or fixtures.

```python
@pytest.mark.asyncio
async def test_my_feature():
    result = await my_async_function()
    assert result == expected_value
```
