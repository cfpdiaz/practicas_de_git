"""
test_metricas_rag.py - Suite de pruebas unitarias para rag/metricas_rag.py y leer_registros.py

Cubre:
1. test_medir_etapa_registra_milisegundos: Verifica que medir_etapa almacena un float >= 0.
2. test_registrar_consulta_genera_jsonl_valido: JSONL con 1 línea por llamada, deserializable, 6 claves exactas.
3. test_manejo_defensivo_tokens_none: Respuestas sin uso/usage_metadata no lanzan AttributeError y guardan tokens=null.
4. test_calculo_costo_usd: Valida tarifas con valores conocidos de prompt y completion tokens.
5. test_validar_registros_detecta_archivo_incompleto: pytest.raises si hay < 3 registros o faltan claves obligatorias.
"""

import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from leer_registros import CLAVES_OBLIGATORIAS as CLAVES_VALIDADOR, validar_registros
from rag.metricas_rag import (
    CLAVES_OBLIGATORIAS,
    _PRECIO_INPUT_POR_1K,
    _PRECIO_OUTPUT_POR_1K,
    _buscar_usage_en_dict,
    _extraer_tokens_y_costo,
    medir_etapa,
    registrar_consulta,
)


# ===========================================================================
# Fixtures y funciones auxiliares
# ===========================================================================

@pytest.fixture()
def jsonl_tmp(tmp_path: Path) -> Path:
    """Ruta temporal para el archivo JSONL de cada test."""
    return tmp_path / "test_registros.jsonl"


def _fn_recuperar_stub(pregunta: str, k: int):
    """Stub de recuperación: devuelve k documentos de prueba."""
    return [{"titulo": f"doc_{i}", "contenido": f"contenido {i}"} for i in range(k)]


def _fn_generar_con_usage(pregunta: str, docs):
    """Stub de generación: devuelve un dict con usage estándar."""
    return {
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }
    }


def _fn_generar_sin_usage(pregunta: str, docs):
    """Stub de generación: respuesta sin metadatos de tokens."""
    return {"choices": [{"message": {"content": "respuesta de prueba"}}]}


# ===========================================================================
# 1. test_medir_etapa_registra_milisegundos
# ===========================================================================

def test_medir_etapa_registra_milisegundos():
    """Verifica que medir_etapa almacena un valor float mayor o igual a 0 bajo la clave indicada."""
    tiempos = {}
    nombre_etapa = "embed_y_busqueda"

    with medir_etapa(tiempos, nombre_etapa):
        time.sleep(0.001)

    assert nombre_etapa in tiempos
    assert isinstance(tiempos[nombre_etapa], float)
    assert tiempos[nombre_etapa] >= 0.0


# ===========================================================================
# 2. test_registrar_consulta_genera_jsonl_valido
# ===========================================================================

def test_registrar_consulta_genera_jsonl_valido(jsonl_tmp: Path):
    """Ejecuta registrar_consulta con funciones simuladas.
    
    Verifica que el archivo .jsonl tenga una línea por llamada, que cada línea
    sea deserializable con json.loads y que contenga las 6 claves exactas:
    timestamp, pregunta, k, tiempos_ms, tiempo_total_ms y tokens.
    """
    pregunta_test = "¿Cómo funciona la arquitectura RAG?"
    k_test = 3

    registro_devuelto = registrar_consulta(
        pregunta=pregunta_test,
        fn_recuperar=_fn_recuperar_stub,
        fn_generar=_fn_generar_con_usage,
        k=k_test,
        ruta_salida=jsonl_tmp,
    )

    # 1. Verifica existencia del archivo
    assert jsonl_tmp.exists()

    # 2. Verifica una línea por llamada
    lineas = [l for l in jsonl_tmp.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lineas) == 1

    # 3. Deserializable con json.loads
    registro_leido = json.loads(lineas[0])
    assert isinstance(registro_leido, dict)

    # 4. 6 claves exactas en el registro
    claves_esperadas = {
        "timestamp",
        "pregunta",
        "k",
        "tiempos_ms",
        "tiempo_total_ms",
        "tokens",
    }
    assert set(registro_leido.keys()) == claves_esperadas
    assert registro_leido["pregunta"] == pregunta_test
    assert registro_leido["k"] == k_test

    # 5. Estructura interna de tiempos_ms
    tiempos = registro_leido["tiempos_ms"]
    assert "embed_y_busqueda" in tiempos
    assert "generacion" in tiempos
    assert isinstance(tiempos["embed_y_busqueda"], float)
    assert isinstance(tiempos["generacion"], float)
    assert isinstance(registro_leido["tiempo_total_ms"], float)
    assert registro_leido["tiempo_total_ms"] >= 0.0

    # 6. Estructura interna de tokens
    tokens = registro_leido["tokens"]
    assert tokens is not None
    assert tokens["prompt_tokens"] == 100
    assert tokens["completion_tokens"] == 50
    assert tokens["total_tokens"] == 150
    assert "costo_usd_estimado" in tokens or "costo_estimado_usd" in tokens


# ===========================================================================
# 3. test_manejo_defensivo_tokens_none
# ===========================================================================

def test_manejo_defensivo_tokens_none(jsonl_tmp: Path):
    """Simula una respuesta del modelo sin metadatos de uso.
    
    Confirma que registrar_consulta no lanza AttributeError y guarda "tokens": null en el JSONL.
    """
    # 1. Caso respuesta diccionario sin usage
    registro = registrar_consulta(
        pregunta="¿Consulta sin tokens?",
        fn_recuperar=_fn_recuperar_stub,
        fn_generar=_fn_generar_sin_usage,
        k=2,
        ruta_salida=jsonl_tmp,
    )
    assert registro["tokens"] is None

    lineas = [l for l in jsonl_tmp.read_text(encoding="utf-8").splitlines() if l.strip()]
    ultimo_registro = json.loads(lineas[-1])
    assert ultimo_registro["tokens"] is None

    # 2. Caso respuesta objeto estilo LangChain con usage_metadata = None
    obj_langchain_none = SimpleNamespace(usage_metadata=None)
    resultado_extractor = _extraer_tokens_y_costo(obj_langchain_none)
    assert resultado_extractor is None

    # 3. Caso respuesta None directa
    resultado_none = _extraer_tokens_y_costo(None)
    assert resultado_none is None


# ===========================================================================
# 4. test_calculo_costo_usd
# ===========================================================================

def test_calculo_costo_usd():
    """Valida con valores conocidos de prompt_tokens y completion_tokens que el costo coincide."""
    prompt_tokens = 1_000
    completion_tokens = 2_000

    resp = {
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
    }

    resultado = _extraer_tokens_y_costo(resp)
    assert resultado is not None

    costo_esperado = round(
        (prompt_tokens / 1_000) * _PRECIO_INPUT_POR_1K
        + (completion_tokens / 1_000) * _PRECIO_OUTPUT_POR_1K,
        8,
    )

    costo_obtenido = resultado.get("costo_estimado_usd")
    if costo_obtenido is None:
        costo_obtenido = resultado.get("costo_usd_estimado")

    assert costo_obtenido == pytest.approx(costo_esperado, rel=1e-6)


# ===========================================================================
# 5. test_validar_registros_detecta_archivo_incompleto
# ===========================================================================

def test_validar_registros_detecta_archivo_incompleto(tmp_path: Path):
    """Verifica con pytest.raises que leer_registros.validar_registros falla explícitamente si hay < 3 registros o faltan claves."""
    archivo_incompleto = tmp_path / "incompleto.jsonl"

    # Caso A: Archivo con solo 2 registros (< 3 registros requeridos)
    registro_valido = {
        "timestamp": "2026-11-20T04:00:00.000Z",
        "pregunta": "¿Pregunta prueba?",
        "k": 3,
        "tiempos_ms": {"embed_y_busqueda": 0.5, "generacion": 1.0},
        "tiempo_total_ms": 1.5,
        "tokens": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "costo_usd_estimado": 0.00001},
    }

    lineas_dos = [json.dumps(registro_valido) + "\n", json.dumps(registro_valido) + "\n"]
    archivo_incompleto.write_text("".join(lineas_dos), encoding="utf-8")

    with pytest.raises(ValueError, match="al menos 3 registros válidos"):
        validar_registros(archivo_incompleto, silencioso=True)

    # Caso B: Archivo con 3 registros pero a uno le falta una clave obligatoria (ej. 'timestamp')
    registro_invalido = {
        "pregunta": "¿Pregunta sin timestamp?",
        "k": 3,
        "tiempos_ms": {"embed_y_busqueda": 0.5, "generacion": 1.0},
        "tiempo_total_ms": 1.5,
        "tokens": None,
    }
    lineas_incompletas = [
        json.dumps(registro_valido) + "\n",
        json.dumps(registro_valido) + "\n",
        json.dumps(registro_invalido) + "\n",
    ]
    archivo_claves_faltantes = tmp_path / "faltan_claves.jsonl"
    archivo_claves_faltantes.write_text("".join(lineas_incompletas), encoding="utf-8")

    with pytest.raises(ValueError):
        validar_registros(archivo_claves_faltantes, silencioso=True)


# ===========================================================================
# Pruebas adicionales de robustez
# ===========================================================================

class TestRobustezAdicional:
    def test_medir_etapa_redondeo(self):
        tiempos = {}
        with medir_etapa(tiempos, "etapa"):
            pass
        assert tiempos["etapa"] == round(tiempos["etapa"], 2)

    def test_medir_etapa_no_suprime_excepcion(self):
        tiempos = {}
        with pytest.raises(RuntimeError):
            with medir_etapa(tiempos, "erronea"):
                raise RuntimeError("falla controlada")
        assert "erronea" in tiempos

    def test_buscar_usage_en_dict(self):
        directo = {"usage": {"prompt_tokens": 10}}
        anidado = {"data": {"usage": {"completion_tokens": 20}}}
        vacio = {"resultado": "ok"}
        assert _buscar_usage_en_dict(directo) is not None
        assert _buscar_usage_en_dict(anidado) is not None
        assert _buscar_usage_en_dict(vacio) is None

    def test_extraer_tokens_soporta_response_simulada(self):
        mock_sim = MagicMock()
        mock_sim.json.return_value = {
            "usage": {
                "prompt_tokens": 82,
                "completion_tokens": 36,
                "total_tokens": 118,
            }
        }
        del mock_sim.usage_metadata
        res = _extraer_tokens_y_costo(mock_sim)
        assert res is not None
        assert res["total_tokens"] == 118
