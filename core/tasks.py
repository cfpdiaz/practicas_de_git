"""
core.tasks - Catálogo de tareas predefinidas.

Carga las tareas desde prompts/banco.py (fuente de verdad) y proporciona el
mapeo de alias CLI a definiciones listas para usar.
"""

from typing import Any, Dict

from prompts.banco import BANCO_DE_PROMPTS

# Mapeo de alias CLI -> nombre interno en prompts/banco.py
_TASK_ALIASES = {
    "incidente_tecnico": "clasificar_incidente",
    "clasificar_incidente": "clasificar_incidente",
    "soporte": "analisis_sentimiento_soporte",
    "analisis_sentimiento_soporte": "analisis_sentimiento_soporte",
    "logistica": "extraccion_entidades_logistica",
    "extraccion_entidades_logistica": "extraccion_entidades_logistica",
}

_BANCO_MAP = {item["nombre"]: item for item in BANCO_DE_PROMPTS}


def build_task_definitions() -> Dict[str, Dict[str, Any]]:
    """Construye las definiciones de tareas desde prompts/banco.py (fuente de verdad)."""
    return {
        alias: {
            "prompt": _BANCO_MAP[name]["ejemplo_entrada"],
            "system_instruction": _BANCO_MAP[name]["system_instruction"],
            "required_keys": set(_BANCO_MAP[name]["claves_esperadas"]),
        }
        for alias, name in _TASK_ALIASES.items()
    }
