import os
import httpx
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from entropy.chaos_injector import (
    chaos_injectable,
    ChaosHttpTransport,
    RateLimitError,
    is_chaos_enabled,
    _corrupt_dict,
    _corrupt_string,
)


def setup_function():
    os.environ.pop("CHAOS_ENABLED", None)
    os.environ.pop("CHAOS_FAULT_TYPE", None)
    os.environ.pop("CHAOS_PROBABILITY", None)


def test_is_chaos_enabled_false_by_default():
    assert is_chaos_enabled() is False


def test_is_chaos_enabled_true():
    os.environ["CHAOS_ENABLED"] = "true"
    assert is_chaos_enabled() is True


def test_chaos_injectable_passthrough_when_disabled():
    os.environ["CHAOS_ENABLED"] = "false"

    @chaos_injectable
    def my_tool(x: int) -> int:
        return x * 2

    assert my_tool(5) == 10


@patch("random.random", return_value=0.1)
def test_chaos_injectable_timeout(mock_random):
    os.environ["CHAOS_ENABLED"] = "true"
    os.environ["CHAOS_FAULT_TYPE"] = "timeout"

    @chaos_injectable
    def my_tool():
        return "done"

    with pytest.raises(TimeoutError):
        my_tool()


@patch("random.random", return_value=0.1)
def test_chaos_injectable_rate_limit(mock_random):
    os.environ["CHAOS_ENABLED"] = "true"
    os.environ["CHAOS_FAULT_TYPE"] = "rate-limit"

    @chaos_injectable
    def my_tool():
        return "done"

    with pytest.raises(RateLimitError):
        my_tool()


@patch("random.random", return_value=0.1)
def test_chaos_injectable_semantic_corruption_dict(mock_random):
    os.environ["CHAOS_ENABLED"] = "true"
    os.environ["CHAOS_FAULT_TYPE"] = "semantic-corruption"

    @chaos_injectable
    def my_tool():
        return {"name": "Alice", "score": 100}

    result = my_tool()
    assert result["name"] == "ecilA"  # reversed
    assert result["score"] == -100  # negated


@patch("random.random", return_value=0.5)
def test_chaos_injectable_probability_skip(mock_random):
    os.environ["CHAOS_ENABLED"] = "true"
    os.environ["CHAOS_FAULT_TYPE"] = "timeout"
    os.environ["CHAOS_PROBABILITY"] = "0.3"

    @chaos_injectable
    def my_tool():
        return "ok"

    # random = 0.5, probability = 0.3, so 0.5 >= 0.3 -> skip
    assert my_tool() == "ok"


@patch("random.random", return_value=0.1)
def test_chaos_injectable_memory_poisoning(mock_random):
    os.environ["CHAOS_ENABLED"] = "true"
    os.environ["CHAOS_FAULT_TYPE"] = "memory-poisoning"

    @chaos_injectable
    def my_tool():
        return {"success": True, "data": {"name": "Alice", "status": "active"}}

    result = my_tool()
    assert result["data"]["name"] == "UNKNOWN"
    assert result["data"]["status"] == "corrupted"
    assert result["data"]["error"] == "memory_poisoned"


def test_corrupt_dict_reverses_strings():
    result = _corrupt_dict({"name": "hello"})
    assert result["name"] == "olleh"


def test_corrupt_dict_negates_numbers():
    result = _corrupt_dict({"count": 42})
    assert result["count"] == -42


def test_corrupt_string_reverses():
    result = _corrupt_string("hello")
    assert result == "olleh"


@pytest.mark.asyncio
async def test_chaos_http_transport_passthrough_when_disabled():
    transport = ChaosHttpTransport()
    transport.configure(enabled=False)

    mock_request = MagicMock(spec=httpx.Request)
    mock_response = MagicMock(spec=httpx.Response)

    with patch.object(
        httpx.AsyncHTTPTransport, "handle_async_request",
        new=AsyncMock(return_value=mock_response),
    ):
        result = await transport.handle_async_request(mock_request)
        assert result is not None


@pytest.mark.asyncio
@patch("random.random", return_value=0.1)
async def test_chaos_http_transport_corrupts_stream_with_args(mock_random):
    transport = ChaosHttpTransport()
    transport.configure(enabled=True, fault_type="semantic-corruption", probability=0.3)

    mock_request = MagicMock(spec=httpx.Request)
    mock_response = MagicMock(spec=httpx.Response)

    async def mock_aiter_bytes(chunk_size=None):
        yield b"chunk1"
        yield b"chunk2"
        yield b"chunk3"

    mock_response.aiter_bytes = mock_aiter_bytes

    with patch.object(
        httpx.AsyncHTTPTransport, "handle_async_request",
        new=AsyncMock(return_value=mock_response),
    ):
        res = await transport.handle_async_request(mock_request)
        
        # Verify it handles chunk_size argument successfully and does not throw TypeError
        chunks = []
        async for chunk in res.aiter_bytes(chunk_size=1024):
            chunks.append(chunk)

        assert chunks[0] == b"chunk1"
        assert chunks[1] == b"CORRUPTED_STREAM_CHUNK"
        assert chunks[2] == b"chunk3"
