"""Pruebas unitarias aisladas para ``app.fetch_api_data``.

Todas las peticiones HTTP se reemplazan con ``unittest.mock``; la suite nunca
consume cuota ni realiza tráfico hacia el proveedor de IA.
"""

import json
from unittest.mock import Mock, patch

import pytest
import requests

import app


TEST_ENDPOINT = "https://example.test/openai/v1/chat/completions"


@pytest.fixture(autouse=True)
def use_test_configuration(monkeypatch):
    """Evita el modo demo; cada prueba parchea explícitamente la petición HTTP."""
    monkeypatch.setattr(app, "API_KEY", "test-key-not-real")
    monkeypatch.setattr(app, "API_BASE_URL", "https://example.test/openai/v1")
    monkeypatch.setattr(app, "MODEL_NAME", "test-model")
    monkeypatch.setattr(app, "SSL_VERIFY", True)


def make_response(*, status_code=200, payload=None):
    """Construye una respuesta mínima compatible con la función bajo prueba."""
    response = Mock()
    response.status_code = status_code
    response.headers = {}
    response.raise_for_status.return_value = None
    if payload is not None:
        response.json.return_value = payload
    return response


def test_fetch_api_data_success_parses_structured_json_and_separates_prompts():
    """Una respuesta 200 se parsea y conserva roles system/user por separado."""
    expected_structured = {
        "resumen": "CPU elevada",
        "categoria": "Infraestructura",
        "prioridad": "alta",
    }
    api_payload = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(expected_structured),
                },
                "finish_reason": "stop",
            }
        ],
    }
    response = make_response(payload=api_payload)

    with patch("app.requests.request", return_value=response) as request:
        result = app.fetch_api_data(
            endpoint=TEST_ENDPOINT,
            prompt="Analiza el incidente de CPU.",
            timeout=3.5,
        )

    assert result["success"] is True
    assert result["status_code"] == 200
    assert result["data"] == api_payload
    assert result["structured_output"] == expected_structured

    request.assert_called_once()
    call_kwargs = request.call_args.kwargs
    assert call_kwargs["method"] == "POST"
    assert call_kwargs["url"] == TEST_ENDPOINT
    assert call_kwargs["timeout"] == 3.5
    assert call_kwargs["verify"] is True
    assert call_kwargs["headers"]["Authorization"] == "Bearer test-key-not-real"
    assert call_kwargs["json"]["response_format"] == {"type": "json_object"}
    assert [message["role"] for message in call_kwargs["json"]["messages"]] == [
        "system",
        "user",
    ]
    assert call_kwargs["json"]["messages"][1]["content"] == "Analiza el incidente de CPU."


def test_fetch_api_data_timeout_is_returned_as_error():
    """Un timeout de requests se encapsula y no se propaga al llamador."""
    with patch(
        "app.requests.request",
        side_effect=requests.exceptions.Timeout("read timed out"),
    ) as request:
        result = app.fetch_api_data(endpoint=TEST_ENDPOINT, timeout=1.25)

    assert result["success"] is False
    assert result["error_type"] == "Timeout"
    assert result["status_code"] is None
    assert result["details"] == "read timed out"
    request.assert_called_once()


def test_fetch_api_data_rate_limit_includes_retry_after_header():
    """HTTP 429 se clasifica como RateLimitExceeded y expone Retry-After."""
    response = make_response(status_code=429)
    response.headers = {"Retry-After": "60"}
    response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "429 Too Many Requests", response=response
    )

    with patch("app.requests.request", return_value=response) as request:
        result = app.fetch_api_data(endpoint=TEST_ENDPOINT)

    assert result["success"] is False
    assert result["error_type"] == "RateLimitExceeded"
    assert result["status_code"] == 429
    assert result["retry_after_seconds"] == "60"
    request.assert_called_once()


def test_fetch_api_data_invalid_json_returns_json_decode_error():
    """Un cuerpo HTML/no parseable devuelve un error JSONDecodeError."""
    response = make_response(status_code=200)
    response.json.side_effect = requests.exceptions.JSONDecodeError(
        "Expecting value", "<html>not-json</html>", 0
    )

    with patch("app.requests.request", return_value=response) as request:
        result = app.fetch_api_data(endpoint=TEST_ENDPOINT)

    assert result["success"] is False
    assert result["error_type"] == "JSONDecodeError"
    assert result["status_code"] == 200
    assert "Expecting value" in result["details"]
    request.assert_called_once()


def test_fetch_api_data_connection_error_is_returned():
    """Una falla DNS/red se captura como ConnectionError."""
    with patch(
        "app.requests.request",
        side_effect=requests.exceptions.ConnectionError("DNS failure"),
    ) as request:
        result = app.fetch_api_data(endpoint=TEST_ENDPOINT)

    assert result["success"] is False
    assert result["error_type"] == "ConnectionError"
    assert result["status_code"] is None
    assert result["details"] == "DNS failure"
    request.assert_called_once()


def test_valid_json_without_required_keys_is_rejected():
    """El contrato debe rechazar JSON válido pero incompleto."""
    incomplete_payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({"resumen": "Solo hay resumen"}),
                }
            }
        ]
    }
    response = make_response(payload=incomplete_payload)

    with patch("app.requests.request", return_value=response):
        result = app.fetch_api_data(endpoint=TEST_ENDPOINT)

    # Esta aserción documenta el comportamiento esperado del contrato.
    assert result["success"] is False
    assert result["error_type"] == "SchemaValidationError"
