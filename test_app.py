"""Pruebas unitarias para ``core.api.obtener_datos_api``.

La suite inyecta una ``ConfiguracionApp`` de prueba (sin depender de variables globales)
y reemplaza ``core.http_client.requests.request`` con ``unittest.mock``; nunca
consume cuota ni realiza tráfico hacia el proveedor de IA.
"""

import json
from unittest.mock import Mock, patch

import requests

from core.api import obtener_datos_api
from core.config import ConfiguracionApp


ENDPOINT_PRUEBA = "https://example.test/openai/v1/chat/completions"


def crear_configuracion(**overrides) -> ConfiguracionApp:
    """Construye una configuración de prueba con valores determinísticos."""
    values = dict(
        url_base_api="https://example.test/openai/v1",
        clave_api="test-key-not-real",
        segundos_timeout=10.0,
        nombre_modelo="test-model",
        verificar_ssl=True,
    )
    values.update(overrides)
    return ConfiguracionApp(**values)


def crear_respuesta(*, status_code=200, payload=None):
    """Construye una respuesta mínima compatible con la función bajo prueba."""
    response = Mock()
    response.status_code = status_code
    response.headers = {}
    response.raise_for_status.return_value = None
    if payload is not None:
        response.json.return_value = payload
    return response


def test_obtener_datos_api_success_parses_structured_json_and_separates_prompts():
    """Una respuesta 200 se parsea y conserva roles system/user por separado."""
    estructurado_esperado = {
        "resumen": "CPU elevada",
        "categoria": "Infraestructura",
        "prioridad": "alta",
    }
    payload_api = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(estructurado_esperado),
                },
                "finish_reason": "stop",
            }
        ],
    }
    response = crear_respuesta(payload=payload_api)

    with patch("core.http_client.requests.request", return_value=response) as request:
        result = obtener_datos_api(
            endpoint=ENDPOINT_PRUEBA,
            prompt="Analiza el incidente de CPU.",
            timeout=3.5,
            config=crear_configuracion(),
        )

    assert result["success"] is True
    assert result["status_code"] == 200
    assert result["data"] == payload_api
    assert result["structured_output"] == estructurado_esperado

    request.assert_called_once()
    kwargs_llamada = request.call_args.kwargs
    assert kwargs_llamada["method"] == "POST"
    assert kwargs_llamada["url"] == ENDPOINT_PRUEBA
    assert kwargs_llamada["timeout"] == 3.5
    assert kwargs_llamada["verify"] is True
    assert kwargs_llamada["headers"]["Authorization"] == "Bearer test-key-not-real"
    assert kwargs_llamada["json"]["response_format"] == {"type": "json_object"}
    assert [message["role"] for message in kwargs_llamada["json"]["messages"]] == [
        "system",
        "user",
    ]
    assert kwargs_llamada["json"]["messages"][1]["content"] == "Analiza el incidente de CPU."


def test_obtener_datos_api_timeout_is_returned_as_error():
    """Un timeout de requests se encapsula y no se propaga al llamador."""
    with patch(
        "core.http_client.requests.request",
        side_effect=requests.exceptions.Timeout("read timed out"),
    ) as request:
        result = obtener_datos_api(
            endpoint=ENDPOINT_PRUEBA,
            timeout=1.25,
            config=crear_configuracion(),
        )

    assert result["success"] is False
    assert result["error_type"] == "Timeout"
    assert result["status_code"] is None
    assert result["details"] == "read timed out"
    request.assert_called_once()


def test_obtener_datos_api_rate_limit_includes_retry_after_header():
    """HTTP 429 se clasifica como RateLimitExceeded y expone Retry-After."""
    response = crear_respuesta(status_code=429)
    response.headers = {"Retry-After": "60"}
    response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "429 Too Many Requests", response=response
    )

    with patch("core.http_client.requests.request", return_value=response) as request:
        result = obtener_datos_api(endpoint=ENDPOINT_PRUEBA, config=crear_configuracion())

    assert result["success"] is False
    assert result["error_type"] == "RateLimitExceeded"
    assert result["status_code"] == 429
    assert result["retry_after_seconds"] == "60"
    request.assert_called_once()


def test_obtener_datos_api_invalid_json_returns_json_decode_error():
    """Un cuerpo HTML/no parseable devuelve un error JSONDecodeError."""
    response = crear_respuesta(status_code=200)
    response.json.side_effect = requests.exceptions.JSONDecodeError(
        "Expecting value", "<html>not-json</html>", 0
    )

    with patch("core.http_client.requests.request", return_value=response) as request:
        result = obtener_datos_api(endpoint=ENDPOINT_PRUEBA, config=crear_configuracion())

    assert result["success"] is False
    assert result["error_type"] == "JSONDecodeError"
    assert result["status_code"] == 200
    assert "Expecting value" in result["details"]
    request.assert_called_once()


def test_obtener_datos_api_connection_error_is_returned():
    """Una falla DNS/red se captura como ConnectionError."""
    with patch(
        "core.http_client.requests.request",
        side_effect=requests.exceptions.ConnectionError("DNS failure"),
    ) as request:
        result = obtener_datos_api(endpoint=ENDPOINT_PRUEBA, config=crear_configuracion())

    assert result["success"] is False
    assert result["error_type"] == "ConnectionError"
    assert result["status_code"] is None
    assert result["details"] == "DNS failure"
    request.assert_called_once()


def test_valid_json_without_claves_requeridas_is_rejected():
    """El contrato debe rechazar JSON válido pero incompleto."""
    payload_incompleto = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({"resumen": "Solo hay resumen"}),
                }
            }
        ]
    }
    response = crear_respuesta(payload=payload_incompleto)

    with patch("core.http_client.requests.request", return_value=response):
        result = obtener_datos_api(endpoint=ENDPOINT_PRUEBA, config=crear_configuracion())

    # Esta aserción documenta el comportamiento esperado del contrato.
    assert result["success"] is False
    assert result["error_type"] == "SchemaValidationError"
