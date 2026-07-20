import pytest
from entropy.agent import run_agent

def test_customer_lookup_routing_no_api_error():
    # Run the agent with customer lookup input.
    # It should classify the intent as customer-lookup, fetch customer data, 
    # and then directly generate response WITHOUT calling mock_api_call 
    # (which would return an error for 'customer-lookup').
    result = run_agent("Lookup customer C001", thread_id="test-lookup")
    
    assert "Customer: Alice (active)" in result["response"]
    assert "Error" not in result["response"]
    # Check that it did NOT trigger the unknown API call error
    assert "Unknown endpoint" not in result["response"]

def test_payment_processing_routes_correctly():
    # Input for process payment will classify as process-payment,
    # skip lookup by design, and execute the process-payment API call.
    result = run_agent("Pay customer C002", thread_id="test-payment")
    
    assert "Action: process-payment" in result["response"]
    assert "transaction_id" in result["response"]
    assert "Error" not in result["response"]
