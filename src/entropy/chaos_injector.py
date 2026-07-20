"""Chaos injector middleware for fault injection in tool calls and LLM streaming."""

import os
import random
import time
import json
from typing import Any, Callable
from functools import wraps

import httpx
from opentelemetry import trace


class RateLimitError(Exception):
    """Raised when a simulated rate limit is triggered."""


def is_chaos_enabled() -> bool:
    """Check if chaos mode is active."""
    return os.environ.get("CHAOS_ENABLED", "").lower() == "true"


def get_chaos_fault_type() -> str:
    """Get the configured fault type from environment."""
    return os.environ.get("CHAOS_FAULT_TYPE", "timeout")


def get_chaos_probability() -> float:
    """Get the fault injection probability."""
    return float(os.environ.get("CHAOS_PROBABILITY", "0.3"))


def _inject_chaos_span_attributes(fault_type: str):
    """Set custom OTel attributes on the current span."""
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute("chaos.injected", True)
        span.set_attribute("chaos.fault_type", fault_type)
        experiment_id = os.environ.get("CHAOS_EXPERIMENT_ID", "")
        if experiment_id:
            span.set_attribute("chaos.experiment_id", experiment_id)


def chaos_injectable(func: Callable) -> Callable:
    """Decorator that wraps a tool function to inject faults probabilistically.

    Reads CHAOS_ENABLED, CHAOS_FAULT_TYPE, and CHAOS_PROBABILITY from
    the environment. Raises standard Python exceptions inside the tool's
    execution scope so the agent's retry and error handling logic fires.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not is_chaos_enabled():
            return func(*args, **kwargs)

        fault_type = get_chaos_fault_type()
        probability = get_chaos_probability()

        if random.random() >= probability:
            return func(*args, **kwargs)

        _inject_chaos_span_attributes(fault_type)

        if fault_type == "timeout":
            delay = float(os.environ.get("CHAOS_TIMEOUT_DELAY", "5.0"))
            time.sleep(delay)
            raise TimeoutError(
                f"Simulated tool API timeout after {delay}s"
            )

        elif fault_type == "rate-limit":
            raise RateLimitError("Simulated HTTP 429: Too Many Requests")

        elif fault_type == "semantic-corruption":
            try:
                result = func(*args, **kwargs)
            except Exception:
                raise ValueError("Simulated semantic corruption - tool failed")

            if isinstance(result, dict):
                corrupted = _corrupt_dict(result)
                return corrupted
            elif isinstance(result, str):
                return _corrupt_string(result)
            return result

        elif fault_type == "memory-poisoning":
            # Return data with contradictory fields to simulate state corruption
            return {"success": True, "data": {"name": "UNKNOWN", "status": "corrupted", "error": "memory_poisoned"}}

        return func(*args, **kwargs)

    return wrapper


def _corrupt_dict(data: dict) -> dict:
    """Randomly corrupt fields in a dictionary to simulate bad tool output."""
    corrupted = {}
    for key, value in data.items():
        if isinstance(value, dict):
            corrupted[key] = _corrupt_dict(value)
        elif isinstance(value, str):
            corrupted[key] = value[::-1]  # Reverse the string
        elif isinstance(value, (int, float)):
            corrupted[key] = value * -1  # Negate numbers
        else:
            corrupted[key] = "CORRUPTED"
    return corrupted


def _corrupt_string(data: str) -> str:
    """Replace a string with garbage."""
    try:
        parsed = json.loads(data)
        if isinstance(parsed, dict):
            return json.dumps(_corrupt_dict(parsed))
    except (json.JSONDecodeError, TypeError):
        pass
    return data[::-1]


class ChaosHttpTransport(httpx.AsyncHTTPTransport):
    """HTTP transport middleware that injects faults into streaming LLM responses.

    Wraps httpx.AsyncHTTPTransport and intercepts streaming responses
    chunk-by-chunk. Can inject mid-stream delays, drop chunks, or
    truncate the response mid-sentence.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._chaos_enabled = False
        self._fault_type = ""
        self._probability = 0.3

    def configure(
        self,
        enabled: bool = False,
        fault_type: str = "timeout",
        probability: float = 0.3,
    ):
        """Configure chaos settings for this transport instance."""
        self._chaos_enabled = enabled
        self._fault_type = fault_type
        self._probability = probability

    async def handle_async_request(
        self, request: httpx.Request, *args: Any, **kwargs: Any
    ) -> httpx.Response:
        if not self._chaos_enabled:
            return await super().handle_async_request(request, *args, **kwargs)

        if random.random() >= self._probability:
            return await super().handle_async_request(request, *args, **kwargs)

        _inject_chaos_span_attributes(self._fault_type)

        if self._fault_type == "rate-limit":
            raise httpx.HTTPStatusError(
                "Simulated HTTP 429: Too Many Requests",
                request=request,
                response=httpx.Response(429, request=request),
            )

        if self._fault_type == "timeout":
            delay = float(os.environ.get("CHAOS_TIMEOUT_DELAY", "5.0"))
            raise httpx.TimeoutException(
                f"Simulated stream timeout after {delay}s"
            )

        if self._fault_type == "semantic-corruption":
            return await self._handle_corrupted_stream(request, *args, **kwargs)

        return await super().handle_async_request(request, *args, **kwargs)

    async def _handle_corrupted_stream(
        self, request: httpx.Request, *args: Any, **kwargs: Any
    ) -> httpx.Response:
        """Get the response but corrupt a chunk in the middle."""
        response = await super().handle_async_request(request, *args, **kwargs)

        original_aiter = response.aiter_bytes

        async def corrupted_aiter(*aiter_args: Any, **aiter_kwargs: Any) -> Any:
            chunk_count = 0
            async for chunk in original_aiter(*aiter_args, **aiter_kwargs):
                chunk_count += 1
                if chunk_count == 2:
                    yield b"CORRUPTED_STREAM_CHUNK"
                else:
                    yield chunk

        response.aiter_bytes = corrupted_aiter
        return response
