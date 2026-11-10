"""
core.trazas - Registro de interacciones del agente en formato JSONL.

Cada ejecución del agente escribe una línea en ``trazas_agente.jsonl`` con el
timestamp, la entrada, la herramienta ejecutada, sus argumentos, una observación
y la respuesta final. Ver ``docs/limites_autonomia_agente.md``.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

ARCHIVO_TRAZAS = "trazas_agente.jsonl"


def registrar_traza(
    entrada: str,
    herramienta: str,
    argumentos: Optional[Dict[str, Any]] = None,
    observacion: str = "",
    respuesta_final: str = "",
    archivo: str = ARCHIVO_TRAZAS,
) -> None:
    """Añade una línea JSONL al archivo de trazas del agente."""
    linea = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entrada": entrada,
        "herramienta": herramienta,
        "argumentos": argumentos or {},
        "observacion": observacion,
        "respuesta_final": respuesta_final,
    }
    with open(archivo, "a", encoding="utf-8") as archivo_trazas:
        archivo_trazas.write(json.dumps(linea, ensure_ascii=False) + "\n")
