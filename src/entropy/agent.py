"""Target agent implementation using LangGraph."""

from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from entropy.tools import mock_api_call, mock_db_lookup, format_response


class AgentState(TypedDict):
    input: str
    intent: str
    customer_data: dict[str, Any]
    api_result: dict[str, Any]
    response: str
    error: str


def classify_intent(state: AgentState) -> dict[str, Any]:
    """Classify the user's intent based on input keywords."""
    text = state.get("input", "").lower()

    if "payment" in text or "pay" in text:
        intent = "process-payment"
    elif "email" in text or "mail" in text:
        intent = "send-email"
    elif "eligibility" in text or "check" in text:
        intent = "check-eligibility"
    elif "lookup" in text or "customer" in text or "find" in text:
        intent = "customer-lookup"
    else:
        intent = "unknown"

    return {"intent": intent}


def lookup_customer(state: AgentState) -> dict[str, Any]:
    """Look up customer data using the mock DB tool."""
    # Extract customer ID from input (simplified: look for C followed by digits)
    text = state.get("input", "")
    customer_id = "C001"
    for word in text.split():
        if word.startswith("C") and len(word) == 4:
            customer_id = word
            break

    result = mock_db_lookup(customer_id)
    if result.get("success"):
        return {"customer_data": result["data"]}
    return {"customer_data": {}, "error": result.get("error", "Lookup failed")}


def execute_api_call(state: AgentState) -> dict[str, Any]:
    """Execute the API call based on intent."""
    intent = state.get("intent", "")
    customer = state.get("customer_data", {})

    payload = {
        "customer_id": customer.get("name", "unknown"),
        "plan": customer.get("plan", "unknown"),
    }

    result = mock_api_call(intent, payload)
    if result.get("success"):
        return {"api_result": result["data"]}
    return {"api_result": {}, "error": result.get("error", "API call failed")}


def generate_response(state: AgentState) -> dict[str, Any]:
    """Generate the final response from collected data."""
    parts = []
    intent = state.get("intent", "unknown")
    customer = state.get("customer_data", {})
    api = state.get("api_result", {})

    if customer:
        status = customer.get("status", "unknown")
        parts.append(f"Customer: {customer.get('name', 'N/A')} ({status})")

    if api:
        parts.append(f"Action: {intent}")
        parts.append(f"Result: {format_response(api, 'brief')}")

    if state.get("error"):
        parts.append(f"Error: {state['error']}")

    if not parts:
        parts.append("No data available.")

    return {"response": " | ".join(parts)}


def route_after_classify(state: AgentState) -> Literal["lookup_customer", "execute_api_call", END]:
    """Route to the correct next step based on intent."""
    intent = state.get("intent", "unknown")

    if intent == "customer-lookup":
        return "lookup_customer"
    elif intent in ("process-payment", "send-email", "check-eligibility"):
        return "execute_api_call"
    return END


def route_after_lookup(state: AgentState) -> Literal["execute_api_call", "generate_response"]:
    """After customer lookup, execute API call or skip if error."""
    if state.get("customer_data"):
        return "execute_api_call"
    return "generate_response"


def build_agent() -> StateGraph:
    """Build and compile the LangGraph agent."""
    workflow = StateGraph(AgentState)

    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("lookup_customer", lookup_customer)
    workflow.add_node("execute_api_call", execute_api_call)
    workflow.add_node("generate_response", generate_response)

    workflow.set_entry_point("classify_intent")

    workflow.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {
            "lookup_customer": "lookup_customer",
            "execute_api_call": "execute_api_call",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "lookup_customer",
        route_after_lookup,
        {
            "execute_api_call": "execute_api_call",
            "generate_response": "generate_response",
        },
    )

    workflow.add_edge("execute_api_call", "generate_response")
    workflow.add_edge("generate_response", END)

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


def run_agent(input_text: str, thread_id: str = "default") -> dict[str, Any]:
    """Run the agent with the given input text."""
    agent = build_agent()
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {"input": input_text}

    result = agent.invoke(initial_state, config)
    return result
