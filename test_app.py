"""Pruebas unitarias para ``core.api.obtener_datos_api`` (cliente modular).

La suite inyecta una ``ConfiguracionApp`` de prueba (sin depender de variables
globales) y reemplaza ``core.http_client.requests.request`` con
``unittest.mock``; nunca consume cuota ni realiza tráfico hacia el proveedor.

Contiene 6 pruebas: éxito HTTP 200 + contrato JSON, Timeout, HTTPError 429
(RateLimitExceeded), JSONDecodeError, ConnectionError y SchemaValidationError
(esquema y tipos de datos con ``isinstance``).
"""

import json
from unittest.mock import Mock, patch

import requests

from core.api import obtener_datos_api
from core.config import ConfiguracionApp


ENDPOINT_PRUEBA = "https://example.test/openai/v1/chat/completions"
CONTRATO_ESPERADO = ("resumen", "categoria", "prioridad")
PRIORIDADES_VALIDAS = ("alta", "media", "baja")


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


def payload_con_estructurado(estructurado):
    """Envuelve un dict estructurado en el formato de respuesta de la API."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(estructurado, ensure_ascii=False),
                },
                "finish_reason": "stop",
            }
        ],
    }


def test_obtener_datos_api_success_parses_structured_json_and_separates_prompts():
    """Una respuesta 200 se parsea y devuelve el contrato de datos en español."""
    estructurado_esperado = {
        "resumen": "CPU elevada",
        "categoria": "Infraestructura",
        "prioridad": "alta",
    }
    payload_api = payload_con_estructurado(estructurado_esperado)
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

    # Contrato de datos traducido al español: resumen, categoria y prioridad.
    assert set(result["structured_output"].keys()) == set(CONTRATO_ESPERADO)
    assert isinstance(result["structured_output"]["resumen"], str)
    assert isinstance(result["structured_output"]["categoria"], str)
    assert result["structured_output"]["prioridad"] in PRIORIDADES_VALIDAS

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


def test_esquema_invalido_o_tipos_incorrectos_returns_schema_validation_error():
    """El contrato rechaza JSON incompleto y tipos incorrectos (isinstance)."""
    casos_invalidos = [
        # 1) Faltan claves requeridas del contrato
        payload_con_estructurado({"resumen": "Solo hay resumen"}),
        # 2) `choices` no es una lista (isinstance falla)
        {"choices": "no-es-una-lista"},
        # 3) `content` no es una cadena de texto (isinstance falla)
        {"choices": [{"message": {"content": 12345}}]},
        # 4) El JSON de `content` no es un diccionario (isinstance falla)
        {"choices": [{"message": {"content": json.dumps(["no", "es", "dict"])}}]},
    ]

    for payload_invalido in casos_invalidos:
        response = crear_respuesta(payload=payload_invalido)
        with patch("core.http_client.requests.request", return_value=response):
            result = obtener_datos_api(
                endpoint=ENDPOINT_PRUEBA,
                config=crear_configuracion(),
            )

        assert result["success"] is False
        assert result["error_type"] == "SchemaValidationError"
