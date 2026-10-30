"""Suite exigente de pruebas unitarias para el paquete ``core``.

Cubre ramas no probadas en ``test_app.py``: configuración, simulación,
validación de esquema, catálogo de tareas y ramas de excepción del cliente HTTP.
"""

import json
import sys
from unittest.mock import Mock, patch

import pytest
import requests

from core.api import obtener_datos_api
from core.config import ConfiguracionApp, cargar_configuracion
from core.schemas import validar_respuesta_api
from core.simulation import (
    _generar_estructurado_simulado,
    construir_respuesta_simulada,
    es_modo_simulacion,
)
from core.tasks import construir_definiciones_tareas


ENDPOINT_PRUEBA = "https://example.test/openai/v1/chat/completions"


def crear_configuracion(**overrides) -> ConfiguracionApp:
    values = dict(
        url_base_api="https://example.test/openai/v1",
        clave_api="test-key-not-real",
        segundos_timeout=10.0,
        nombre_modelo="test-model",
        verificar_ssl=True,
    )
    values.update(overrides)
    return ConfiguracionApp(**values)


def crear_respuesta_mock(status_code=200, payload=None):
    response = Mock()
    response.status_code = status_code
    if payload is not None:
        response.json.return_value = payload
    return response


# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #

class TestConfiguracionApp:
    def test_es_url_confiable_relative_is_true(self):
        cfg = crear_configuracion()
        assert cfg.es_url_confiable("chat/completions", es_relativa=True) is True

    def test_es_url_confiable_trusted_domain_is_true(self):
        cfg = crear_configuracion(dominios_confiables=frozenset({"api.groq.com"}))
        assert cfg.es_url_confiable("https://api.groq.com/v1/x", es_relativa=False) is True

    def test_es_url_confiable_base_host_match_is_true(self):
        cfg = crear_configuracion(url_base_api="https://example.test/openai/v1")
        assert cfg.es_url_confiable("https://example.test/other", es_relativa=False) is True

    def test_es_url_confiable_untrusted_host_is_false(self):
        cfg = crear_configuracion()
        assert cfg.es_url_confiable("https://evil.example/x", es_relativa=False) is False

    def test_es_url_confiable_no_hostname_is_false(self):
        cfg = crear_configuracion()
        assert cfg.es_url_confiable("not-a-valid-url", es_relativa=False) is False


class TestCargarConfiguracion:
    def test_defaults(self, monkeypatch):
        for name in ("API_BASE_URL", "API_KEY", "API_TIMEOUT", "AI_MODEL", "SSL_VERIFY"):
            monkeypatch.delenv(name, raising=False)
        cfg = cargar_configuracion()
        assert cfg.url_base_api == "https://api.groq.com/openai/v1"
        assert cfg.clave_api is None
        assert cfg.segundos_timeout == 10.0
        assert cfg.nombre_modelo == "llama-3.3-70b-versatile"
        assert cfg.verificar_ssl is True

    def test_verificar_ssl_false(self, monkeypatch):
        monkeypatch.setenv("SSL_VERIFY", "false")
        assert cargar_configuracion().verificar_ssl is False

    def test_verificar_ssl_off_variant(self, monkeypatch):
        monkeypatch.setenv("SSL_VERIFY", "off")
        assert cargar_configuracion().verificar_ssl is False

    def test_clave_api_empty_becomes_none(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "")
        assert cargar_configuracion().clave_api is None

    def test_url_base_trailing_slash_is_stripped(self, monkeypatch):
        monkeypatch.setenv("API_BASE_URL", "https://example.com/v1/")
        assert cargar_configuracion().url_base_api == "https://example.com/v1"


# --------------------------------------------------------------------------- #
# Simulación
# --------------------------------------------------------------------------- #

class TestGenerarEstructuradoSimulado:
    def test_incidente_template(self):
        result = _generar_estructurado_simulado("x", claves_requeridas={"resumen", "categoria", "prioridad"})
        assert result == {
            "resumen": "Sobrecarga crítica de CPU (98%) en el servidor de base de datos en producción afectando la latencia de los usuarios.",
            "categoria": "Infraestructura",
            "prioridad": "alta",
        }

    def test_sentimiento_template(self):
        result = _generar_estructurado_simulado("x", claves_requeridas={"resumen", "sentimiento", "urgencia"})
        assert result["sentimiento"] == "negativo"
        assert result["urgencia"] == "alta"

    def test_logistica_template(self):
        result = _generar_estructurado_simulado(
            "x", claves_requeridas={"numero_pedido", "destino", "estado_envio"}
        )
        assert result["numero_pedido"] == "ORD-98234"
        assert result["estado_envio"] == "en_transito"

    def test_arbitrary_keys_produce_placeholder_values(self):
        result = _generar_estructurado_simulado("x", claves_requeridas={"foo", "bar"})
        assert result == {"foo": "valor_simulado_foo", "bar": "valor_simulado_bar"}

    def test_keyword_reclamo_detects_sentimiento(self):
        result = _generar_estructurado_simulado("El cliente eleva un reclamo grave")
        assert result["sentimiento"] == "negativo"

    def test_keyword_pedido_detects_logistica(self):
        result = _generar_estructurado_simulado("El pedido está en camino")
        assert result["estado_envio"] == "en_transito"

    def test_default_is_incidente(self):
        result = _generar_estructurado_simulado("")
        assert set(result) == {"resumen", "categoria", "prioridad"}


class TestEsModoSimulacion:
    def test_placeholder_key_activates(self):
        assert es_modo_simulacion(crear_configuracion(clave_api="tu_groq_clave_api_aqui"), "https://api.groq.com/v1", 10.0) is True

    def test_none_key_activates(self):
        assert es_modo_simulacion(crear_configuracion(clave_api=None), "https://api.groq.com/v1", 10.0) is True

    def test_real_key_deactivates(self):
        assert es_modo_simulacion(crear_configuracion(clave_api="gsk_real_key"), "https://api.groq.com/v1", 10.0) is False

    def test_httpbin_deactivates(self):
        assert es_modo_simulacion(crear_configuracion(clave_api=None), "https://httpbin.org/status/429", 10.0) is False

    def test_forced_short_timeout_deactivates(self):
        assert es_modo_simulacion(crear_configuracion(clave_api=None), "https://api.groq.com/v1", 0.001) is False


class TestConstruirRespuestaSimulada:
    def test_builds_full_response(self):
        result = construir_respuesta_simulada(
            config=crear_configuracion(),
            url="https://example.test/chat/completions",
            mensaje_usuario="hola",
            claves_requeridas={"resumen", "categoria", "prioridad"},
        )
        assert result["success"] is True
        assert result["status_code"] == 200
        assert result["data"]["model"] == "test-model"
        assert result["data"]["usage"]["total_tokens"] == 118
        assert set(result["structured_output"]) == {"resumen", "categoria", "prioridad"}


# --------------------------------------------------------------------------- #
# Validación de esquema
# --------------------------------------------------------------------------- #

class TestValidarRespuestaApi:
    def test_non_dict_data_is_rejected(self):
        result = validar_respuesta_api(
            data=["no", "es", "dict"],
            response=crear_respuesta_mock(200),
            url="u",
            timestamp="t",
            claves_requeridas=None,
            payload_personalizado=False,
            sistema_personalizado=False,
        )
        assert result["success"] is False
        assert result["error_type"] == "SchemaValidationError"

    def test_empty_choices_is_rejected(self):
        result = validar_respuesta_api(
            data={"choices": []},
            response=crear_respuesta_mock(200),
            url="u",
            timestamp="t",
            claves_requeridas=None,
            payload_personalizado=False,
            sistema_personalizado=False,
        )
        assert result["success"] is False

    def test_content_json_list_is_rejected(self):
        data = {"choices": [{"message": {"content": json.dumps(["a", "b"])}}]}
        result = validar_respuesta_api(
            data=data,
            response=crear_respuesta_mock(200),
            url="u",
            timestamp="t",
            claves_requeridas=None,
            payload_personalizado=False,
            sistema_personalizado=False,
        )
        assert result["success"] is False
        assert result["error_type"] == "SchemaValidationError"

    def test_invalid_priority_is_rejected(self):
        data = {"choices": [{"message": {"content": json.dumps(
            {"resumen": "x", "categoria": "y", "prioridad": "urgentisima"}
        )}}]}
        result = validar_respuesta_api(
            data=data,
            response=crear_respuesta_mock(200),
            url="u",
            timestamp="t",
            claves_requeridas=None,
            payload_personalizado=False,
            sistema_personalizado=False,
        )
        assert result["success"] is False
        assert "prioridad" in result["message"]

    def test_custom_payload_skips_claves_requeridas_validation(self):
        # Con payload personalizado + instrucción personalizada no se exige el contrato por defecto.
        data = {"choices": [{"message": {"content": json.dumps({"lo": "que sea"})}}]}
        result = validar_respuesta_api(
            data=data,
            response=crear_respuesta_mock(200),
            url="u",
            timestamp="t",
            claves_requeridas=None,
            payload_personalizado=True,
            sistema_personalizado=True,
        )
        assert result["success"] is True


# --------------------------------------------------------------------------- #
# Ramas de excepción del cliente HTTP (vía obtener_datos_api)
# --------------------------------------------------------------------------- #

class TestClienteHttpRamasError:
    def test_generic_http_error(self):
        response = Mock()
        response.status_code = 500
        response.headers = {}
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Server Error", response=response
        )
        with patch("core.http_client.requests.request", return_value=response):
            result = obtener_datos_api(endpoint=ENDPOINT_PRUEBA, config=crear_configuracion())
        assert result["error_type"] == "HTTPError"
        assert result["status_code"] == 500

    def test_request_exception_fallback(self):
        with patch(
            "core.http_client.requests.request",
            side_effect=requests.exceptions.RequestException("boom"),
        ):
            result = obtener_datos_api(endpoint=ENDPOINT_PRUEBA, config=crear_configuracion())
        assert result["error_type"] == "RequestException"
        assert result["status_code"] is None

    def test_simulation_path_does_not_hit_network(self):
        with patch("core.http_client.requests.request") as request:
            result = obtener_datos_api(
                endpoint=ENDPOINT_PRUEBA,
                config=crear_configuracion(clave_api=None),
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
            obtener_datos_api(endpoint="https://evil.example/v1", config=crear_configuracion())
        assert "Authorization" not in request.call_args.kwargs["headers"]


# --------------------------------------------------------------------------- #
# Catálogo de tareas
# --------------------------------------------------------------------------- #

class TestConstruirDefinicionesTareas:
    def test_aliases_resolve_correctly(self):
        defs = construir_definiciones_tareas()
        assert set(defs) == {
            "incidente_tecnico",
            "clasificar_incidente",
            "soporte",
            "analisis_sentimiento_soporte",
            "logistica",
            "extraccion_entidades_logistica",
        }
        assert defs["incidente_tecnico"]["claves_requeridas"] == {"resumen", "categoria", "prioridad"}
        assert defs["soporte"]["claves_requeridas"] == {"resumen", "sentimiento", "urgencia"}
        assert defs["logistica"]["claves_requeridas"] == {"numero_pedido", "destino", "estado_envio"}
        assert defs["incidente_tecnico"]["prompt"] == defs["clasificar_incidente"]["prompt"]
        assert defs["soporte"]["prompt"] == defs["analisis_sentimiento_soporte"]["prompt"]
        assert defs["logistica"]["prompt"] == defs["extraccion_entidades_logistica"]["prompt"]


# --------------------------------------------------------------------------- #
# Cobertura de ramas adicionales de validación / simulación / config
# --------------------------------------------------------------------------- #

def test_schema_first_choice_not_dict_is_rejected():
    data = {"choices": ["no-es-dict"]}
    result = validar_respuesta_api(data, crear_respuesta_mock(200), "u", "t", None, False, False)
    assert result["success"] is False
    assert result["error_type"] == "SchemaValidationError"


def test_schema_message_not_dict_is_rejected():
    data = {"choices": [{"message": "no-es-dict"}]}
    result = validar_respuesta_api(data, crear_respuesta_mock(200), "u", "t", None, False, False)
    assert result["success"] is False
    assert result["error_type"] == "SchemaValidationError"


def test_schema_empty_content_is_rejected():
    data = {"choices": [{"message": {"content": ""}}]}
    result = validar_respuesta_api(data, crear_respuesta_mock(200), "u", "t", None, False, False)
    assert result["success"] is False
    assert result["error_type"] == "SchemaValidationError"


def test_schema_non_json_content_is_rejected():
    data = {"choices": [{"message": {"content": "esto no es un json válido"}}]}
    result = validar_respuesta_api(data, crear_respuesta_mock(200), "u", "t", None, False, False)
    assert result["success"] is False
    assert result["error_type"] == "SchemaValidationError"


def test_simulation_scans_payload_messages_for_keywords():
    result = _generar_estructurado_simulado(
        "",
        payload={"messages": [{"role": "user", "content": "quiero elevar un reclamo formal"}]},
    )
    assert result["sentimiento"] == "negativo"


def test_module_level_es_url_confiable(monkeypatch):
    import importlib

    # `import core.config as x` devuelve el ConfiguracionApp (sombreado en core/__init__),
    # por eso se usa importlib para obtener el módulo real.
    config_module = importlib.import_module("core.config")
    monkeypatch.setattr(config_module, "config", crear_configuracion(url_base_api="https://example.test/openai/v1"))
    assert config_module.es_url_confiable("https://example.test/x", es_relativa=False) is True
    assert config_module.es_url_confiable("https://evil.example/x", es_relativa=False) is False


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def test_crear_analizador_defaults():
    from core.cli import crear_analizador

    argumentos = crear_analizador().parse_args([])
    assert argumentos.endpoint == "chat/completions"
    assert argumentos.prompt is None
    assert argumentos.task is None
    assert argumentos.test_exceptions is False


def test_crear_analizador_full_args():
    from core.cli import crear_analizador

    argumentos = crear_analizador().parse_args(
        ["--endpoint", "x", "--prompt", "hola", "--task", "soporte", "--test-exceptions"]
    )
    assert argumentos.endpoint == "x"
    assert argumentos.prompt == "hola"
    assert argumentos.task == "soporte"
    assert argumentos.test_exceptions is True


def test_main_test_exceptions_dispatches_ejecutar_pruebas(monkeypatch):
    import core.cli as cli

    calls = []
    monkeypatch.setattr(cli, "ejecutar_pruebas", lambda: calls.append(True))
    monkeypatch.setattr(sys, "argv", ["app.py", "--test-exceptions"])
    cli.main()
    assert calls == [True]


def test_main_task_dispatches_obtener_datos_api(monkeypatch):
    import core.cli as cli

    captured = {}

    def fake_fetch(**kwargs):
        captured.update(kwargs)
        return {"success": True}

    monkeypatch.setattr(cli, "obtener_datos_api", fake_fetch)
    monkeypatch.setattr(sys, "argv", ["app.py", "--task", "soporte"])
    cli.main()

    assert captured["endpoint"] == "chat/completions"
    assert captured["claves_requeridas"] == {"resumen", "sentimiento", "urgencia"}
    assert "3 días" in captured["prompt"]


# --------------------------------------------------------------------------- #
# Pruebas: armar_peticion, enviar_peticion, extraer_texto
# --------------------------------------------------------------------------- #

class TestFuncionesApi:
    """Valida armar_peticion, enviar_peticion y extraer_texto de punta a punta."""

    def test_armar_peticion_estructura_y_desempaquetado(self):
        from core.api import armar_peticion

        cfg = crear_configuracion(clave_api="clave-prueba", nombre_modelo="mi-modelo-ia")
        peticion = armar_peticion(
            prompt="Consulta técnica",
            instruccion_sistema="Eres un bot útil",
            config=cfg,
        )

        # Acceso por atributos
        assert peticion.url == "https://example.test/openai/v1/chat/completions"
        assert peticion.headers["Authorization"] == "Bearer clave-prueba"
        assert peticion.payload["model"] == "mi-modelo-ia"
        assert peticion.payload["response_format"] == {"type": "json_object"}
        assert peticion.payload["messages"][0] == {"role": "system", "content": "Eres un bot útil"}
        assert peticion.payload["messages"][1] == {"role": "user", "content": "Consulta técnica"}

        # Acceso por clave y desempaquetado tupla
        assert peticion["url"] == peticion.url
        assert peticion["headers"] == peticion.headers
        assert peticion["payload"] == peticion.payload
        u, h, p = peticion
        assert u == peticion.url
        assert h == peticion.headers
        assert p == peticion.payload

    def test_enviar_peticion_en_simulacion_devuelve_simulated_response(self):
        from core.api import armar_peticion, enviar_peticion

        cfg = crear_configuracion(clave_api="tu_groq_clave_api_aqui")
        peticion = armar_peticion(prompt="Simulación", config=cfg)
        resp = enviar_peticion(peticion, config=cfg)

        assert resp.status_code == 200
        data = resp.json()
        assert "choices" in data
        assert len(data["choices"]) > 0

    def test_enviar_peticion_con_mock_de_red(self):
        from core.api import armar_peticion, enviar_peticion

        mock_resp = crear_respuesta_mock(
            200,
            payload={
                "choices": [{"message": {"role": "assistant", "content": '{"ok": true}'}}]
            },
        )
        cfg = crear_configuracion(clave_api="clave-real-para-mock")
        peticion = armar_peticion(prompt="Hola mock", config=cfg)

        with patch("core.api.requests.request", return_value=mock_resp) as mock_req:
            resp = enviar_peticion(peticion, config=cfg)
            assert resp.status_code == 200
            assert mock_req.call_count == 1

    def test_extraer_texto_desde_response_y_dict(self):
        from core.api import extraer_texto

        # Desde objeto Response mock
        mock_resp = crear_respuesta_mock(
            200,
            payload={
                "choices": [{"message": {"role": "assistant", "content": "Texto extraído exitosamente"}}]
            },
        )
        assert extraer_texto(mock_resp) == "Texto extraído exitosamente"

        # Desde diccionario puro
        data_dict = {
            "choices": [{"message": {"role": "assistant", "content": "Desde diccionario"}}]
        }
        assert extraer_texto(data_dict) == "Desde diccionario"

    def test_extraer_texto_desde_simulated_response_y_errores(self):
        from core.api import RespuestaSimulada, extraer_texto

        sim = RespuestaSimulada(
            data={"choices": [{"message": {"content": "Respuesta simulada"}}]}
        )
        assert extraer_texto(sim) == "Respuesta simulada"

        with pytest.raises(TypeError):
            extraer_texto(12345)

        with pytest.raises(ValueError):
            extraer_texto({"vacio": True})

    def test_flujo_punta_a_punta(self):
        from core.api import armar_peticion, enviar_peticion, extraer_texto

        cfg = crear_configuracion(clave_api="tu_groq_clave_api_aqui")
        req = armar_peticion(prompt="Verifica flujo punta a punta", config=cfg)
        resp = enviar_peticion(req, config=cfg)
        texto = extraer_texto(resp)

        assert isinstance(texto, str)
        assert len(texto) > 0
        parsed = json.loads(texto)
        assert isinstance(parsed, dict)

    def test_peticion_and_simulated_response_helpers(self):
        from core.api import Peticion, RespuestaSimulada

        p = Peticion("https://example.test", {"H": "1"}, {"k": "v"})
        assert p.json == {"k": "v"}
        assert p.get("url") == "https://example.test"
        assert p.get("inexistente", 99) == 99
        assert p.como_diccionario()["url"] == "https://example.test"
        with pytest.raises(KeyError):
            _ = p["inexistente"]

        sim = RespuestaSimulada({"clave": "valor"}, status_code=200)
        sim.raise_for_status()
        assert "RespuestaSimulada [200]" in repr(sim)

    def test_enviar_peticion_input_variants(self):
        from core.api import enviar_peticion

        cfg = crear_configuracion(clave_api="tu_groq_clave_api_aqui")

        # Entrada como dict
        resp_dict = enviar_peticion(
            {"url": "https://api.groq.com/openai/v1/chat/completions", "payload": {}},
            config=cfg,
        )
        assert resp_dict.status_code == 200

        # Entrada como URL string
        resp_str = enviar_peticion("https://api.groq.com/openai/v1/chat/completions", config=cfg)
        assert resp_str.status_code == 200

        # Entrada sin argumentos (usa defaults)
        resp_default = enviar_peticion(config=cfg)
        assert resp_default.status_code == 200

    def test_extraer_texto_variants(self):
        from core.api import extraer_texto

        # String con JSON válido
        assert extraer_texto('{"choices": [{"message": {"content": "desde json str"}}]}') == "desde json str"

        # String plano
        assert extraer_texto("texto plano de prueba") == "texto plano de prueba"

        # Dict con text
        assert extraer_texto({"text": "contenido directo"}) == "contenido directo"

        # Dict con structured_output
        assert extraer_texto({"structured_output": {"resultado": 1}}) == '{"resultado": 1}'

        # Response con json corrupto
        mock_bad = Mock()
        mock_bad.json.side_effect = json.JSONDecodeError("err", "doc", 0)
        with pytest.raises(ValueError):
            extraer_texto(mock_bad)

