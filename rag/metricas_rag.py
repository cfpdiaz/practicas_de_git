"""
rag.metricas_rag - Medición de latencia y costo estimado para flujos RAG.

Provee:
- ``medir_etapa``: context manager que registra duración en ms con perf_counter.
- ``_extraer_tokens_y_costo``: extracción defensiva de tokens y costo USD.
- ``registrar_consulta``: orquesta las etapas RAG y persiste métricas en JSONL.
"""

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional


# ---------------------------------------------------------------------------
# Precios por 1 000 tokens (USD) para openai/gpt-oss-120b / groq llama-3.3
# Se usa como estimación orientativa; ajustar si se usa otro modelo.
# ---------------------------------------------------------------------------
_PRECIO_INPUT_POR_1K: float = 0.00059   # prompt tokens
_PRECIO_OUTPUT_POR_1K: float = 0.00079  # completion tokens


# ---------------------------------------------------------------------------
# context manager: medir_etapa
# ---------------------------------------------------------------------------

@contextmanager
def medir_etapa(
    tiempos: Dict[str, float],
    nombre_etapa: str,
) -> Generator[None, None, None]:
    """Mide la duración de un bloque de código y la almacena en ``tiempos``.

    Usa ``time.perf_counter()`` para alta resolución.  El valor registrado es
    la duración en **milisegundos**, redondeado a 2 decimales.

    Args:
        tiempos: Diccionario mutable donde se escribe ``tiempos[nombre_etapa]``.
        nombre_etapa: Clave que identifica la etapa dentro del diccionario.

    Yields:
        Control al bloque ``with``.
    """
    inicio: float = time.perf_counter()
    try:
        yield
    finally:
        fin: float = time.perf_counter()
        tiempos[nombre_etapa] = round((fin - inicio) * 1_000, 2)


# ---------------------------------------------------------------------------
# Extracción defensiva de tokens y costo
# ---------------------------------------------------------------------------

def _extraer_tokens_y_costo(
    respuesta: Any,
) -> Optional[Dict[str, Any]]:
    """Extrae métricas de tokens y calcula el costo estimado en USD.

    Soporta múltiples formatos de respuesta:
    - Objetos estilo LangChain con ``usage_metadata`` (dict con
      ``input_tokens``, ``output_tokens``, ``total_tokens``).
    - Diccionarios devueltos por ``core/api.py``: clave ``usage`` directa o
      anidada en ``data.usage`` con ``prompt_tokens``, ``completion_tokens``,
      ``total_tokens``.
    - Objetos con ``.json()`` (``requests.Response``, ``RespuestaSimulada``).

    Returns:
        Diccionario con claves ``prompt_tokens``, ``completion_tokens``,
        ``total_tokens`` y ``costo_usd_estimado``, o ``None`` si no hay datos.
    """
    usage: Optional[Dict[str, Any]] = None

    # -- 1. Objetos con usage_metadata (estilo LangChain) --------------------
    usage_metadata = getattr(respuesta, "usage_metadata", None)
    if usage_metadata is not None:
        if isinstance(usage_metadata, dict):
            prompt = usage_metadata.get("input_tokens", 0) or 0
            completion = usage_metadata.get("output_tokens", 0) or 0
            total = usage_metadata.get("total_tokens", prompt + completion) or 0
            usage = {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": total,
            }

    # -- 2. Objetos con .json() (requests.Response / RespuestaSimulada) ------
    if usage is None and callable(getattr(respuesta, "json", None)):
        try:
            data = respuesta.json()
        except Exception:
            data = {}
        if isinstance(data, dict):
            usage = _buscar_usage_en_dict(data)

    # -- 3. Diccionarios directos (retorno de obtener_datos_api) -------------
    if usage is None and isinstance(respuesta, dict):
        usage = _buscar_usage_en_dict(respuesta)

    if usage is None:
        return None

    prompt_t: int = int(usage.get("prompt_tokens") or 0)
    completion_t: int = int(usage.get("completion_tokens") or 0)
    total_t: int = int(usage.get("total_tokens") or (prompt_t + completion_t))

    costo_usd: float = round(
        (prompt_t / 1_000) * _PRECIO_INPUT_POR_1K
        + (completion_t / 1_000) * _PRECIO_OUTPUT_POR_1K,
        8,
    )

    return {
        "prompt_tokens": prompt_t,
        "completion_tokens": completion_t,
        "total_tokens": total_t,
        "costo_usd_estimado": costo_usd,
        "costo_estimado_usd": costo_usd,
    }


def _buscar_usage_en_dict(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Busca el sub-diccionario ``usage`` dentro de un dict de respuesta API."""
    # Formato directo: {"usage": {"prompt_tokens": ...}}
    if "usage" in data and isinstance(data["usage"], dict):
        u = data["usage"]
        if "prompt_tokens" in u or "completion_tokens" in u or "total_tokens" in u:
            return u

    # Formato envuelto: {"data": {"usage": {...}}}
    inner_data = data.get("data")
    if isinstance(inner_data, dict) and "usage" in inner_data:
        u = inner_data["usage"]
        if isinstance(u, dict) and (
            "prompt_tokens" in u or "completion_tokens" in u or "total_tokens" in u
        ):
            return u

    return None


# ---------------------------------------------------------------------------
# Registro de consulta RAG
# ---------------------------------------------------------------------------

CLAVES_OBLIGATORIAS: tuple[str, ...] = (
    "timestamp",
    "pregunta",
    "k",
    "tiempos_ms",
    "tiempo_total_ms",
    "tokens",
)

_RUTA_SALIDA_DEFAULT = Path("registros_latencia_costo.jsonl")


def registrar_consulta(
    pregunta: str,
    fn_recuperar: Callable[[str, int], List[Any]],
    fn_generar: Callable[[str, List[Any]], Any],
    k: int = 3,
    ruta_salida: Path = _RUTA_SALIDA_DEFAULT,
) -> Dict[str, Any]:
    """Ejecuta un pipeline RAG de dos etapas y registra métricas en JSONL.

    Mide por separado:
    - ``embed_y_busqueda``: tiempo de recuperación de documentos.
    - ``generacion``: tiempo de llamada al LLM.
    - ``tiempo_total_ms``: suma de ambas etapas.

    Escribe **una línea JSON** por ejecución en ``ruta_salida`` con exactamente
    las claves: ``timestamp``, ``pregunta``, ``k``, ``tiempos_ms``,
    ``tiempo_total_ms``, ``tokens``.

    Args:
        pregunta: Consulta del usuario.
        fn_recuperar: Callable(pregunta, k) → lista de documentos relevantes.
        fn_generar: Callable(pregunta, documentos) → respuesta del LLM (cualquier
                    tipo que soporte ``_extraer_tokens_y_costo``).
        k: Número de documentos a recuperar.
        ruta_salida: Path del archivo ``.jsonl`` de salida.

    Returns:
        El diccionario de registro escrito en disco.
    """
    tiempos: Dict[str, float] = {}
    inicio_total: float = time.perf_counter()

    # -- Etapa 1: recuperación -----------------------------------------------
    with medir_etapa(tiempos, "embed_y_busqueda"):
        documentos: List[Any] = fn_recuperar(pregunta, k)

    # -- Etapa 2: generación --------------------------------------------------
    respuesta_llm: Any
    with medir_etapa(tiempos, "generacion"):
        respuesta_llm = fn_generar(pregunta, documentos)

    # -- Tiempo total ---------------------------------------------------------
    tiempo_total_ms: float = round((time.perf_counter() - inicio_total) * 1_000, 2)

    # -- Métricas de tokens ---------------------------------------------------
    tokens: Optional[Dict[str, Any]] = _extraer_tokens_y_costo(respuesta_llm)

    # -- Construcción del registro --------------------------------------------
    registro: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "pregunta": pregunta,
        "k": k,
        "tiempos_ms": {
            "embed_y_busqueda": tiempos.get("embed_y_busqueda", 0.0),
            "generacion": tiempos.get("generacion", 0.0),
        },
        "tiempo_total_ms": tiempo_total_ms,
        "tokens": tokens,
    }

    # -- Escritura en JSONL (una línea por ejecución) -------------------------
    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with ruta_salida.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(registro, ensure_ascii=False) + "\n")

    return registro
