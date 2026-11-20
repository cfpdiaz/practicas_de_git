"""
test_metricas_rag.py - Suite de pruebas unitarias para rag/metricas_rag.py

Cubre:
- medir_etapa: registro de ms, clave correcta, no excepción, bloques anidados.
- _extraer_tokens_y_costo: 5 formatos de entrada + caso None defensivo.
- registrar_consulta: escritura JSONL, 6 claves, acumulación por append.
- _buscar_usage_en_dict: formato directo y anidado.
"""

import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from rag.metricas_rag import (
    CLAVES_OBLIGATORIAS,
    _buscar_usage_en_dict,
    _extraer_tokens_y_costo,
    medir_etapa,
    registrar_consulta,
)


# ===========================================================================
# Fixtures auxiliares
# ===========================================================================

@pytest.fixture()
def jsonl_tmp(tmp_path: Path) -> Path:
    """Ruta temporal para el archivo JSONL de cada test."""
    return tmp_path / "test_registros.jsonl"


def _fn_recuperar_ok(pregunta: str, k: int):
    """Stub de recuperación: devuelve k documentos ficticios."""
    return [{"titulo": f"doc_{i}", "contenido": f"contenido {i}"} for i in range(k)]


def _fn_generar_dict(pregunta: str, docs):
    """Stub de generación: devuelve un dict con usage directo."""
    return {
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 20,
            "total_tokens": 70,
        }
    }


def _fn_generar_sin_tokens(pregunta: str, docs):
    """Stub de generación: respuesta sin usage alguno."""
    return {"choices": [{"message": {"content": "ok"}}]}


# ===========================================================================
# Tests: medir_etapa
# ===========================================================================

class TestMedirEtapa:
    def test_registra_clave_en_diccionario(self):
        tiempos = {}
        with medir_etapa(tiempos, "mi_etapa"):
            pass
        assert "mi_etapa" in tiempos

    def test_valor_es_float_positivo(self):
        tiempos = {}
        with medir_etapa(tiempos, "etapa"):
            time.sleep(0.001)
        assert isinstance(tiempos["etapa"], float)
        assert tiempos["etapa"] >= 0.0

    def test_valor_en_milisegundos_no_segundos(self):
        """Duerme 10 ms: el valor debe estar en [5, 500] ms, no en segundos."""
        tiempos = {}
        with medir_etapa(tiempos, "etapa_ms"):
            time.sleep(0.010)
        assert 5.0 <= tiempos["etapa_ms"] <= 500.0

    def test_redondea_a_dos_decimales(self):
        tiempos = {}
        with medir_etapa(tiempos, "e"):
            pass
        valor = tiempos["e"]
        assert valor == round(valor, 2)

    def test_no_suprime_excepcion_del_bloque(self):
        tiempos = {}
        with pytest.raises(ValueError, match="boom"):
            with medir_etapa(tiempos, "con_error"):
                raise ValueError("boom")
        # La clave SÍ debe registrarse aunque hubo excepción (finally)
        assert "con_error" in tiempos

    def test_bloques_anidados_registran_claves_independientes(self):
        tiempos = {}
        with medir_etapa(tiempos, "externa"):
            with medir_etapa(tiempos, "interna"):
                pass
        assert "externa" in tiempos
        assert "interna" in tiempos
        assert tiempos["externa"] >= tiempos["interna"]

    def test_sobrescribe_clave_preexistente(self):
        tiempos = {"repetida": 999.99}
        with medir_etapa(tiempos, "repetida"):
            pass
        assert tiempos["repetida"] != 999.99


# ===========================================================================
# Tests: _extraer_tokens_y_costo
# ===========================================================================

class TestExtraerTokensYCosto:
    def test_formato_respuesta_simulada_json(self):
        """RespuestaSimulada / requests.Response con .json() y usage directo."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "usage": {
                "prompt_tokens": 80,
                "completion_tokens": 40,
                "total_tokens": 120,
            }
        }
        # Eliminar usage_metadata para forzar rama .json()
        del mock_resp.usage_metadata
        resultado = _extraer_tokens_y_costo(mock_resp)
        assert resultado is not None
        assert resultado["prompt_tokens"] == 80
        assert resultado["completion_tokens"] == 40
        assert resultado["total_tokens"] == 120
        assert isinstance(resultado["costo_usd_estimado"], float)
        assert resultado["costo_usd_estimado"] > 0

    def test_formato_dict_usage_directo(self):
        """Dict con clave 'usage' directa (formato obtener_datos_api)."""
        resp = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            }
        }
        resultado = _extraer_tokens_y_costo(resp)
        assert resultado is not None
        assert resultado["prompt_tokens"] == 100
        assert resultado["completion_tokens"] == 50
        assert resultado["total_tokens"] == 150

    def test_formato_dict_usage_anidado_en_data(self):
        """Dict con usage anidado en data.usage (wrapping de obtener_datos_api)."""
        resp = {
            "data": {
                "usage": {
                    "prompt_tokens": 60,
                    "completion_tokens": 30,
                    "total_tokens": 90,
                }
            }
        }
        resultado = _extraer_tokens_y_costo(resp)
        assert resultado is not None
        assert resultado["total_tokens"] == 90

    def test_formato_langchain_usage_metadata(self):
        """Objeto con atributo usage_metadata (estilo LangChain)."""
        obj = SimpleNamespace(
            usage_metadata={
                "input_tokens": 70,
                "output_tokens": 30,
                "total_tokens": 100,
            }
        )
        resultado = _extraer_tokens_y_costo(obj)
        assert resultado is not None
        assert resultado["prompt_tokens"] == 70
        assert resultado["completion_tokens"] == 30
        assert resultado["total_tokens"] == 100

    def test_retorna_none_sin_datos_de_uso(self):
        """Objeto sin ningún dato de usage → debe retornar None, no lanzar."""
        resultado = _extraer_tokens_y_costo({"choices": [{"message": {"content": "ok"}}]})
        assert resultado is None

    def test_retorna_none_con_none_directo(self):
        """None como entrada → no lanza AttributeError."""
        resultado = _extraer_tokens_y_costo(None)
        assert resultado is None

    def test_retorna_none_con_string(self):
        """String arbitrario → no lanza, retorna None."""
        resultado = _extraer_tokens_y_costo("texto sin estructura")
        assert resultado is None

    def test_costo_usd_calculado_correctamente(self):
        """Verifica la fórmula: prompt*0.00059/1K + completion*0.00079/1K."""
        resp = {
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 1000,
                "total_tokens": 2000,
            }
        }
        resultado = _extraer_tokens_y_costo(resp)
        assert resultado is not None
        esperado = round(1.0 * 0.00059 + 1.0 * 0.00079, 8)
        assert resultado["costo_usd_estimado"] == pytest.approx(esperado, rel=1e-6)

    def test_tokens_cero_no_lanza(self):
        """Tokens en 0 → costo 0.0, sin ZeroDivisionError."""
        resp = {
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        }
        resultado = _extraer_tokens_y_costo(resp)
        assert resultado is not None
        assert resultado["costo_usd_estimado"] == 0.0


# ===========================================================================
# Tests: _buscar_usage_en_dict
# ===========================================================================

class TestBuscarUsageEnDict:
    def test_encuentra_usage_directo(self):
        data = {"usage": {"prompt_tokens": 10, "total_tokens": 10}}
        assert _buscar_usage_en_dict(data) is not None

    def test_encuentra_usage_anidado_en_data(self):
        data = {"data": {"usage": {"completion_tokens": 5, "total_tokens": 5}}}
        assert _buscar_usage_en_dict(data) is not None

    def test_retorna_none_sin_usage(self):
        data = {"choices": [], "model": "test"}
        assert _buscar_usage_en_dict(data) is None

    def test_retorna_none_si_usage_no_es_dict(self):
        data = {"usage": "no-es-dict"}
        assert _buscar_usage_en_dict(data) is None


# ===========================================================================
# Tests: registrar_consulta
# ===========================================================================

class TestRegistrarConsulta:
    def test_crea_archivo_jsonl(self, jsonl_tmp: Path):
        registrar_consulta(
            pregunta="¿test?",
            fn_recuperar=_fn_recuperar_ok,
            fn_generar=_fn_generar_dict,
            k=2,
            ruta_salida=jsonl_tmp,
        )
        assert jsonl_tmp.exists()

    def test_escribe_exactamente_una_linea(self, jsonl_tmp: Path):
        registrar_consulta(
            pregunta="¿test?",
            fn_recuperar=_fn_recuperar_ok,
            fn_generar=_fn_generar_dict,
            k=2,
            ruta_salida=jsonl_tmp,
        )
        lineas = [l for l in jsonl_tmp.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lineas) == 1

    def test_acumula_lineas_en_modo_append(self, jsonl_tmp: Path):
        for _ in range(3):
            registrar_consulta(
                pregunta="¿acumulación?",
                fn_recuperar=_fn_recuperar_ok,
                fn_generar=_fn_generar_dict,
                k=1,
                ruta_salida=jsonl_tmp,
            )
        lineas = [l for l in jsonl_tmp.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lineas) == 3

    def test_registro_es_json_valido(self, jsonl_tmp: Path):
        registrar_consulta(
            pregunta="¿json válido?",
            fn_recuperar=_fn_recuperar_ok,
            fn_generar=_fn_generar_dict,
            k=2,
            ruta_salida=jsonl_tmp,
        )
        linea = jsonl_tmp.read_text(encoding="utf-8").strip()
        registro = json.loads(linea)
        assert isinstance(registro, dict)

    def test_registro_contiene_6_claves_obligatorias(self, jsonl_tmp: Path):
        registrar_consulta(
            pregunta="¿claves?",
            fn_recuperar=_fn_recuperar_ok,
            fn_generar=_fn_generar_dict,
            k=2,
            ruta_salida=jsonl_tmp,
        )
        registro = json.loads(jsonl_tmp.read_text(encoding="utf-8").strip())
        for clave in CLAVES_OBLIGATORIAS:
            assert clave in registro, f"Clave faltante: {clave}"

    def test_timestamp_formato_iso8601_utc(self, jsonl_tmp: Path):
        """El timestamp debe terminar en Z y tener formato básico ISO 8601."""
        registrar_consulta(
            pregunta="¿timestamp?",
            fn_recuperar=_fn_recuperar_ok,
            fn_generar=_fn_generar_dict,
            k=1,
            ruta_salida=jsonl_tmp,
        )
        registro = json.loads(jsonl_tmp.read_text(encoding="utf-8").strip())
        ts = registro["timestamp"]
        assert isinstance(ts, str)
        assert ts.endswith("Z"), f"Timestamp sin Z: {ts!r}"
        assert "T" in ts, f"Timestamp sin separador T: {ts!r}"

    def test_k_registrado_correctamente(self, jsonl_tmp: Path):
        registrar_consulta(
            pregunta="¿k=5?",
            fn_recuperar=_fn_recuperar_ok,
            fn_generar=_fn_generar_dict,
            k=5,
            ruta_salida=jsonl_tmp,
        )
        registro = json.loads(jsonl_tmp.read_text(encoding="utf-8").strip())
        assert registro["k"] == 5

    def test_tiempos_ms_contiene_ambas_etapas(self, jsonl_tmp: Path):
        registrar_consulta(
            pregunta="¿etapas?",
            fn_recuperar=_fn_recuperar_ok,
            fn_generar=_fn_generar_dict,
            k=2,
            ruta_salida=jsonl_tmp,
        )
        registro = json.loads(jsonl_tmp.read_text(encoding="utf-8").strip())
        tiempos = registro["tiempos_ms"]
        assert "embed_y_busqueda" in tiempos
        assert "generacion" in tiempos
        assert isinstance(tiempos["embed_y_busqueda"], float)
        assert isinstance(tiempos["generacion"], float)

    def test_tiempo_total_ms_es_positivo(self, jsonl_tmp: Path):
        registrar_consulta(
            pregunta="¿total?",
            fn_recuperar=_fn_recuperar_ok,
            fn_generar=_fn_generar_dict,
            k=2,
            ruta_salida=jsonl_tmp,
        )
        registro = json.loads(jsonl_tmp.read_text(encoding="utf-8").strip())
        assert registro["tiempo_total_ms"] >= 0.0

    def test_tokens_none_cuando_no_hay_usage(self, jsonl_tmp: Path):
        """Si fn_generar no retorna usage, tokens debe ser None (no error)."""
        registrar_consulta(
            pregunta="¿sin tokens?",
            fn_recuperar=_fn_recuperar_ok,
            fn_generar=_fn_generar_sin_tokens,
            k=1,
            ruta_salida=jsonl_tmp,
        )
        registro = json.loads(jsonl_tmp.read_text(encoding="utf-8").strip())
        assert "tokens" in registro
        assert registro["tokens"] is None

    def test_tokens_contiene_costo_cuando_hay_usage(self, jsonl_tmp: Path):
        registrar_consulta(
            pregunta="¿con costo?",
            fn_recuperar=_fn_recuperar_ok,
            fn_generar=_fn_generar_dict,
            k=2,
            ruta_salida=jsonl_tmp,
        )
        registro = json.loads(jsonl_tmp.read_text(encoding="utf-8").strip())
        tokens = registro["tokens"]
        assert tokens is not None
        assert "costo_usd_estimado" in tokens
        assert tokens["costo_usd_estimado"] >= 0.0

    def test_retorno_coincide_con_linea_escrita(self, jsonl_tmp: Path):
        """El dict retornado por registrar_consulta debe ser idéntico al JSON escrito."""
        retorno = registrar_consulta(
            pregunta="¿retorno?",
            fn_recuperar=_fn_recuperar_ok,
            fn_generar=_fn_generar_dict,
            k=2,
            ruta_salida=jsonl_tmp,
        )
        escrito = json.loads(jsonl_tmp.read_text(encoding="utf-8").strip())
        assert retorno == escrito

    def test_crea_directorio_si_no_existe(self, tmp_path: Path):
        """Si el directorio padre no existe, debe crearlo automáticamente."""
        ruta = tmp_path / "subdir" / "nuevo" / "registros.jsonl"
        registrar_consulta(
            pregunta="¿mkdir?",
            fn_recuperar=_fn_recuperar_ok,
            fn_generar=_fn_generar_dict,
            k=1,
            ruta_salida=ruta,
        )
        assert ruta.exists()
