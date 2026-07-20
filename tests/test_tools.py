from entropy.tools import mock_db_lookup, mock_api_call, format_response


def test_mock_db_lookup_found():
    result = mock_db_lookup("C001")
    assert result["success"] is True
    assert result["data"]["name"] == "Alice"


def test_mock_db_lookup_not_found():
    result = mock_db_lookup("C999")
    assert result["success"] is False
    assert "error" in result


def test_mock_api_call_success():
    result = mock_api_call("process-payment", {})
    assert result["success"] is True
    assert result["data"]["transaction_id"] == "TXN-12345"


def test_mock_api_call_unknown():
    result = mock_api_call("nonexistent", {})
    assert result["success"] is False


def test_format_response_standard():
    data = {"success": True, "data": {"key": "value"}}
    output = format_response(data, "standard")
    assert "key" in output
    assert "value" in output
