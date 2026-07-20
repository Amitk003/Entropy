import pytest
from entropy.agent import (
    classify_intent,
    lookup_customer,
    execute_api_call,
    generate_response,
    run_agent,
    build_agent,
)


def test_classify_intent_payment():
    result = classify_intent({"input": "process payment for order"})
    assert result["intent"] == "process-payment"


def test_classify_intent_customer_lookup():
    result = classify_intent({"input": "lookup customer C001"})
    assert result["intent"] == "customer-lookup"


def test_classify_intent_unknown():
    result = classify_intent({"input": "hello world"})
    assert result["intent"] == "unknown"


def test_lookup_customer_found():
    state = {"input": "find customer C002"}
    result = lookup_customer(state)
    assert result["customer_data"]["name"] == "Bob"


def test_lookup_customer_not_found():
    state = {"input": "find customer C999"}
    result = lookup_customer(state)
    assert result["customer_data"] == {}


def test_execute_api_call():
    state = {"intent": "send-email", "customer_data": {"name": "Alice"}}
    result = execute_api_call(state)
    assert "message_id" in result.get("api_result", {})


def test_generate_response_with_data():
    state = {
        "intent": "process-payment",
        "customer_data": {"name": "Alice", "status": "active"},
        "api_result": {"transaction_id": "TXN-123", "status": "completed"},
    }
    result = generate_response(state)
    assert "Alice" in result["response"]
    assert "TXN-123" in result["response"]


def test_generate_response_empty():
    state = {}
    result = generate_response(state)
    assert result["response"] == "No data available."


def test_build_agent_returns_graph():
    agent = build_agent()
    assert agent is not None


def test_run_agent_basic_input():
    result = run_agent("Lookup customer C001", thread_id="test-1")
    assert "response" in result
    assert len(result["response"]) > 0
