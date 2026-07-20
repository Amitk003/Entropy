"""Mock tools for the target agent to use during experiments."""

import json
import random
from typing import Any

from entropy.chaos_injector import chaos_injectable


@chaos_injectable
def mock_db_lookup(query: str) -> dict[str, Any]:
    """Simulate a database lookup. Returns mock customer data."""
    customers = {
        "C001": {"name": "Alice", "plan": "premium", "status": "active"},
        "C002": {"name": "Bob", "plan": "basic", "status": "active"},
        "C003": {"name": "Charlie", "plan": "premium", "status": "suspended"},
    }

    customer_id = query.strip().upper()
    if customer_id in customers:
        return {"success": True, "data": customers[customer_id]}
    return {"success": False, "error": "Customer not found"}


@chaos_injectable
def mock_api_call(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Simulate an external API call."""
    # Simulate some endpoints
    endpoints = {
        "process-payment": {"transaction_id": "TXN-12345", "status": "completed"},
        "send-email": {"message_id": "MSG-67890", "status": "queued"},
        "check-eligibility": {"eligible": True, "limit": 50000},
    }

    if endpoint in endpoints:
        return {"success": True, "data": endpoints[endpoint], "endpoint": endpoint}
    return {"success": False, "error": f"Unknown endpoint: {endpoint}"}


def format_response(data: dict[str, Any], template: str = "standard") -> str:
    """Format tool output into a human-readable response."""
    if template == "standard":
        return json.dumps(data, indent=2)
    elif template == "brief":
        return str(data.get("data", data))
    return str(data)
