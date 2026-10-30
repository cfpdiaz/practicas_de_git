"""
core.tasks - Catálogo de tareas predefinidas.

Carga las tareas desde prompts/banco.py (fuente de verdad) y proporciona el
mapeo de alias CLI a definiciones listas para usar.
"""

from typing import Any, Dict

from prompts.banco import BANCO_DE_PROMPTS

# Mapeo de alias CLI -> nombre interno en prompts/banco.py
_ALIAS_TAREAS = {
    "incidente_tecnico": "clasificar_incidente",
    "clasificar_incidente": "clasificar_incidente",
    "soporte": "analisis_sentimiento_soporte",
    "analisis_sentimiento_soporte": "analisis_sentimiento_soporte",
    "logistica": "extraccion_entidades_logistica",
    "extraccion_entidades_logistica": "extraccion_entidades_logistica",
}

_MAPA_BANCO = {item["nombre"]: item for item in BANCO_DE_PROMPTS}


def construir_definiciones_tareas() -> Dict[str, Dict[str, Any]]:
    """Construye las definiciones de tareas desde prompts/banco.py (fuente de verdad)."""
    return {
        alias: {
            "prompt": _MAPA_BANCO[name]["ejemplo_entrada"],
            "instruccion_sistema": _MAPA_BANCO[name]["instruccion_sistema"],
            "claves_requeridas": set(_MAPA_BANCO[name]["claves_esperadas"]),
        }
        for alias, name in _ALIAS_TAREAS.items()
    }
