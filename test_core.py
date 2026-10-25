"""Suite exigente de pruebas unitarias para el paquete ``core``.

Cubre ramas no probadas en ``test_app.py``: configuración, simulación,
validación de esquema, catálogo de tareas y ramas de excepción del cliente HTTP.
"""

import json
import sys
from unittest.mock import Mock, patch

import pytest
import requests

from core.api import fetch_api_data
from core.config import AppConfig, load_config
from core.schemas import validate_api_response
from core.simulation import (
    _generate_simulated_structured,
    build_simulated_response,
    is_simulation_mode,
)
from core.tasks import build_task_definitions


TEST_ENDPOINT = "https://example.test/openai/v1/chat/completions"


def make_config(**overrides) -> AppConfig:
    values = dict(
        api_base_url="https://example.test/openai/v1",
        api_key="test-key-not-real",
        timeout_seconds=10.0,
        model_name="test-model",
        ssl_verify=True,
    )
    values.update(overrides)
    return AppConfig(**values)


def make_response_mock(status_code=200):
    response = Mock()
    response.status_code = status_code
    return response


# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #

class TestAppConfig:
    def test_is_trusted_url_relative_is_true(self):
        cfg = make_config()
        assert cfg.is_trusted_url("chat/completions", is_relative=True) is True

    def test_is_trusted_url_trusted_domain_is_true(self):
        cfg = make_config(trusted_domains=frozenset({"api.groq.com"}))
        assert cfg.is_trusted_url("https://api.groq.com/v1/x", is_relative=False) is True

    def test_is_trusted_url_base_host_match_is_true(self):
        cfg = make_config(api_base_url="https://example.test/openai/v1")
        assert cfg.is_trusted_url("https://example.test/other", is_relative=False) is True

    def test_is_trusted_url_untrusted_host_is_false(self):
        cfg = make_config()
        assert cfg.is_trusted_url("https://evil.example/x", is_relative=False) is False

    def test_is_trusted_url_no_hostname_is_false(self):
        cfg = make_config()
        assert cfg.is_trusted_url("not-a-valid-url", is_relative=False) is False


class TestLoadConfig:
    def test_defaults(self, monkeypatch):
        for name in ("API_BASE_URL", "API_KEY", "API_TIMEOUT", "AI_MODEL", "SSL_VERIFY"):
            monkeypatch.delenv(name, raising=False)
        cfg = load_config()
        assert cfg.api_base_url == "https://api.groq.com/openai/v1"
        assert cfg.api_key is None
        assert cfg.timeout_seconds == 10.0
        assert cfg.model_name == "llama-3.3-70b-versatile"
        assert cfg.ssl_verify is True

    def test_ssl_verify_false(self, monkeypatch):
        monkeypatch.setenv("SSL_VERIFY", "false")
        assert load_config().ssl_verify is False

    def test_ssl_verify_off_variant(self, monkeypatch):
        monkeypatch.setenv("SSL_VERIFY", "off")
        assert load_config().ssl_verify is False

    def test_api_key_empty_becomes_none(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "")
        assert load_config().api_key is None

    def test_base_url_trailing_slash_is_stripped(self, monkeypatch):
        monkeypatch.setenv("API_BASE_URL", "https://example.com/v1/")
        assert load_config().api_base_url == "https://example.com/v1"


# --------------------------------------------------------------------------- #
# Simulación
# --------------------------------------------------------------------------- #

class TestGenerateSimulatedStructured:
    def test_incidente_template(self):
        result = _generate_simulated_structured("x", required_keys={"resumen", "categoria", "prioridad"})
        assert result == {
            "resumen": "Sobrecarga crítica de CPU (98%) en el servidor de base de datos en producción afectando la latencia de los usuarios.",
            "categoria": "Infraestructura",
            "prioridad": "alta",
        }

    def test_sentimiento_template(self):
        result = _generate_simulated_structured("x", required_keys={"resumen", "sentimiento", "urgencia"})
        assert result["sentimiento"] == "negativo"
        assert result["urgencia"] == "alta"

    def test_logistica_template(self):
        result = _generate_simulated_structured(
            "x", required_keys={"numero_pedido", "destino", "estado_envio"}
        )
        assert result["numero_pedido"] == "ORD-98234"
        assert result["estado_envio"] == "en_transito"

    def test_arbitrary_keys_produce_placeholder_values(self):
        result = _generate_simulated_structured("x", required_keys={"foo", "bar"})
        assert result == {"foo": "valor_simulado_foo", "bar": "valor_simulado_bar"}

    def test_keyword_reclamo_detects_sentimiento(self):
        result = _generate_simulated_structured("El cliente eleva un reclamo grave")
        assert result["sentimiento"] == "negativo"

    def test_keyword_pedido_detects_logistica(self):
        result = _generate_simulated_structured("El pedido está en camino")
        assert result["estado_envio"] == "en_transito"

    def test_default_is_incidente(self):
        result = _generate_simulated_structured("")
        assert set(result) == {"resumen", "categoria", "prioridad"}


class TestIsSimulationMode:
    def test_placeholder_key_activates(self):
        assert is_simulation_mode(make_config(api_key="tu_groq_api_key_aqui"), "https://api.groq.com/v1", 10.0) is True

    def test_none_key_activates(self):
        assert is_simulation_mode(make_config(api_key=None), "https://api.groq.com/v1", 10.0) is True

    def test_real_key_deactivates(self):
        assert is_simulation_mode(make_config(api_key="gsk_real_key"), "https://api.groq.com/v1", 10.0) is False

    def test_httpbin_deactivates(self):
        assert is_simulation_mode(make_config(api_key=None), "https://httpbin.org/status/429", 10.0) is False

    def test_forced_short_timeout_deactivates(self):
        assert is_simulation_mode(make_config(api_key=None), "https://api.groq.com/v1", 0.001) is False


class TestBuildSimulatedResponse:
    def test_builds_full_response(self):
        result = build_simulated_response(
            config=make_config(),
            url="https://example.test/chat/completions",
            user_message="hola",
            required_keys={"resumen", "categoria", "prioridad"},
        )
        assert result["success"] is True
        assert result["status_code"] == 200
        assert result["data"]["model"] == "test-model"
        assert result["data"]["usage"]["total_tokens"] == 118
        assert set(result["structured_output"]) == {"resumen", "categoria", "prioridad"}


# --------------------------------------------------------------------------- #
# Validación de esquema
# --------------------------------------------------------------------------- #

class TestValidateApiResponse:
    def test_non_dict_data_is_rejected(self):
        result = validate_api_response(
            data=["no", "es", "dict"],
            response=make_response_mock(200),
            url="u",
            timestamp="t",
            required_keys=None,
            custom_payload_provided=False,
            custom_system_provided=False,
        )
        assert result["success"] is False
        assert result["error_type"] == "SchemaValidationError"

    def test_empty_choices_is_rejected(self):
        result = validate_api_response(
            data={"choices": []},
            response=make_response_mock(200),
            url="u",
            timestamp="t",
            required_keys=None,
            custom_payload_provided=False,
            custom_system_provided=False,
        )
        assert result["success"] is False

    def test_content_json_list_is_rejected(self):
        data = {"choices": [{"message": {"content": json.dumps(["a", "b"])}}]}
        result = validate_api_response(
            data=data,
            response=make_response_mock(200),
            url="u",
            timestamp="t",
            required_keys=None,
            custom_payload_provided=False,
            custom_system_provided=False,
        )
        assert result["success"] is False
        assert result["error_type"] == "SchemaValidationError"

    def test_invalid_priority_is_rejected(self):
        data = {"choices": [{"message": {"content": json.dumps(
            {"resumen": "x", "categoria": "y", "prioridad": "urgentisima"}
        )}}]}
        result = validate_api_response(
            data=data,
            response=make_response_mock(200),
            url="u",
            timestamp="t",
            required_keys=None,
            custom_payload_provided=False,
            custom_system_provided=False,
        )
        assert result["success"] is False
        assert "prioridad" in result["message"]

    def test_custom_payload_skips_required_keys_validation(self):
        # Con payload personalizado + instrucción personalizada no se exige el contrato por defecto.
        data = {"choices": [{"message": {"content": json.dumps({"lo": "que sea"})}}]}
        result = validate_api_response(
            data=data,
            response=make_response_mock(200),
            url="u",
            timestamp="t",
            required_keys=None,
            custom_payload_provided=True,
            custom_system_provided=True,
        )
        assert result["success"] is True


# --------------------------------------------------------------------------- #
# Ramas de excepción del cliente HTTP (vía fetch_api_data)
# --------------------------------------------------------------------------- #

class TestHttpClientErrorBranches:
    def test_generic_http_error(self):
        response = Mock()
        response.status_code = 500
        response.headers = {}
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Server Error", response=response
        )
        with patch("core.http_client.requests.request", return_value=response):
            result = fetch_api_data(endpoint=TEST_ENDPOINT, config=make_config())
        assert result["error_type"] == "HTTPError"
        assert result["status_code"] == 500

    def test_request_exception_fallback(self):
        with patch(
            "core.http_client.requests.request",
            side_effect=requests.exceptions.RequestException("boom"),
        ):
            result = fetch_api_data(endpoint=TEST_ENDPOINT, config=make_config())
        assert result["error_type"] == "RequestException"
        assert result["status_code"] is None

    def test_simulation_path_does_not_hit_network(self):
        with patch("core.http_client.requests.request") as request:
            result = fetch_api_data(
                endpoint=TEST_ENDPOINT,
                config=make_config(api_key=None),
            )
        request.assert_not_called()
        assert result["success"] is True
        assert result["status_code"] == 200

    def test_untrusted_host_does_not_attach_authorization(self):
        response = Mock()
        response.status_code = 200
        response.headers = {}
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": json.dumps(
                {"resumen": "x", "categoria": "y", "prioridad": "alta"}
            )}}]
        }
        with patch("core.http_client.requests.request", return_value=response) as request:
            fetch_api_data(endpoint="https://evil.example/v1", config=make_config())
        assert "Authorization" not in request.call_args.kwargs["headers"]


# --------------------------------------------------------------------------- #
# Catálogo de tareas
# --------------------------------------------------------------------------- #

class TestBuildTaskDefinitions:
    def test_aliases_resolve_correctly(self):
        defs = build_task_definitions()
        assert set(defs) == {
            "incidente_tecnico",
            "clasificar_incidente",
            "soporte",
            "analisis_sentimiento_soporte",
            "logistica",
            "extraccion_entidades_logistica",
        }
        assert defs["incidente_tecnico"]["required_keys"] == {"resumen", "categoria", "prioridad"}
        assert defs["soporte"]["required_keys"] == {"resumen", "sentimiento", "urgencia"}
        assert defs["logistica"]["required_keys"] == {"numero_pedido", "destino", "estado_envio"}
        assert defs["incidente_tecnico"]["prompt"] == defs["clasificar_incidente"]["prompt"]
        assert defs["soporte"]["prompt"] == defs["analisis_sentimiento_soporte"]["prompt"]
        assert defs["logistica"]["prompt"] == defs["extraccion_entidades_logistica"]["prompt"]


# --------------------------------------------------------------------------- #
# Cobertura de ramas adicionales de validación / simulación / config
# --------------------------------------------------------------------------- #

def test_schema_first_choice_not_dict_is_rejected():
    data = {"choices": ["no-es-dict"]}
    result = validate_api_response(data, make_response_mock(200), "u", "t", None, False, False)
    assert result["success"] is False
    assert result["error_type"] == "SchemaValidationError"


def test_schema_message_not_dict_is_rejected():
    data = {"choices": [{"message": "no-es-dict"}]}
    result = validate_api_response(data, make_response_mock(200), "u", "t", None, False, False)
    assert result["success"] is False
    assert result["error_type"] == "SchemaValidationError"


def test_schema_empty_content_is_rejected():
    data = {"choices": [{"message": {"content": ""}}]}
    result = validate_api_response(data, make_response_mock(200), "u", "t", None, False, False)
    assert result["success"] is False
    assert result["error_type"] == "SchemaValidationError"


def test_schema_non_json_content_is_rejected():
    data = {"choices": [{"message": {"content": "esto no es un json válido"}}]}
    result = validate_api_response(data, make_response_mock(200), "u", "t", None, False, False)
    assert result["success"] is False
    assert result["error_type"] == "SchemaValidationError"


def test_simulation_scans_payload_messages_for_keywords():
    result = _generate_simulated_structured(
        "",
        payload={"messages": [{"role": "user", "content": "quiero elevar un reclamo formal"}]},
    )
    assert result["sentimiento"] == "negativo"


def test_module_level_is_trusted_url(monkeypatch):
    import importlib

    # `import core.config as x` devuelve el AppConfig (sombreado en core/__init__),
    # por eso se usa importlib para obtener el módulo real.
    config_module = importlib.import_module("core.config")
    monkeypatch.setattr(config_module, "config", make_config(api_base_url="https://example.test/openai/v1"))
    assert config_module.is_trusted_url("https://example.test/x", is_relative=False) is True
    assert config_module.is_trusted_url("https://evil.example/x", is_relative=False) is False


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def test_create_parser_defaults():
    from core.cli import create_parser

    args = create_parser().parse_args([])
    assert args.endpoint == "chat/completions"
    assert args.prompt is None
    assert args.task is None
    assert args.test_exceptions is False


def test_create_parser_full_args():
    from core.cli import create_parser

    args = create_parser().parse_args(
        ["--endpoint", "x", "--prompt", "hola", "--task", "soporte", "--test-exceptions"]
    )
    assert args.endpoint == "x"
    assert args.prompt == "hola"
    assert args.task == "soporte"
    assert args.test_exceptions is True


def test_main_test_exceptions_dispatches_run_tests(monkeypatch):
    import core.cli as cli

    calls = []
    monkeypatch.setattr(cli, "run_tests", lambda: calls.append(True))
    monkeypatch.setattr(sys, "argv", ["app.py", "--test-exceptions"])
    cli.main()
    assert calls == [True]


def test_main_task_dispatches_fetch_api_data(monkeypatch):
    import core.cli as cli

    captured = {}

    def fake_fetch(**kwargs):
        captured.update(kwargs)
        return {"success": True}

    monkeypatch.setattr(cli, "fetch_api_data", fake_fetch)
    monkeypatch.setattr(sys, "argv", ["app.py", "--task", "soporte"])
    cli.main()

    assert captured["endpoint"] == "chat/completions"
    assert captured["required_keys"] == {"resumen", "sentimiento", "urgencia"}
    assert "3 días" in captured["prompt"]
