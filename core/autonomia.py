"""
core.autonomia - Matriz de autonomía del agente.

Define, en código, el nivel de riesgo de cada acción antes de ejecutarla:

- **Bajo (ejecución directa):** lectura de datos, formateo de texto y consultas
  a la API de solo lectura.
- **Medio (registro en trazas):** modificación de variables locales de estado o
  de la memoria de contexto.
- **Alto (requiere aprobación):** eliminación de archivos, llamadas a servicios
  externos destructivos y cambios persistentes.

La función ``ejecutar_con_autonomia`` es la barrera única que aplica esta matriz
antes de ejecutar cualquier acción. Además, **registra en la traza estructurada**
cada decisión, cada llamada a herramienta y cada resultado de aprobación, para
cumplir con el requisito de auditoría. Ver ``docs/limites_autonomia_agente.md``.
"""

import json
from enum import Enum
from typing import Any, Callable, Dict


class NivelRiesgo(str, Enum):
    """Nivel de riesgo de una acción del agente."""

    BAJO = "bajo"
    MEDIO = "medio"
    ALTO = "alto"


# Matriz de autonomía: nombre de la acción -> nivel de riesgo.
MATRIZ_AUTONOMIA: Dict[str, NivelRiesgo] = {
    # --- Bajo riesgo: ejecución directa ----------------------------------
    "armar_peticion": NivelRiesgo.BAJO,            # formatea/construye la petición
    "enviar_peticion": NivelRiesgo.BAJO,           # consulta de solo lectura a la API
    "extraer_texto": NivelRiesgo.BAJO,             # formateo/parseo de texto
    "obtener_datos_api": NivelRiesgo.BAJO,         # consulta de solo lectura a la API
    "validar_respuesta_api": NivelRiesgo.BAJO,     # lectura/validación de la respuesta
    "construir_respuesta_simulada": NivelRiesgo.BAJO,  # formateo (simulación offline)
    "construir_definiciones_tareas": NivelRiesgo.BAJO,  # lectura del catálogo de tareas
    # --- Medio riesgo: registro en trazas ---------------------------------
    "registrar_traza": NivelRiesgo.MEDIO,          # modifica el estado local (traza)
    # --- Alto riesgo: requiere aprobación humana --------------------------
    "ejecutar_pruebas": NivelRiesgo.ALTO,          # cambio persistente (registro_resultados.json)
    "test_consistencia": NivelRiesgo.ALTO,         # cambio persistente (registro_resultados.json)
    # Ejemplos de acciones ALTO que se agregarían en el futuro:
    #   "eliminar_archivos": NivelRiesgo.ALTO,
    #   "llamada_externa_destructiva": NivelRiesgo.ALTO,
}


def nivel_de_accion(accion: str) -> NivelRiesgo:
    """Devuelve el nivel de riesgo de una acción (ALTO por defecto, conservador)."""
    return MATRIZ_AUTONOMIA.get(accion, NivelRiesgo.ALTO)


def requiere_aprobacion(accion: str) -> bool:
    """True si la acción es de riesgo alto y necesita aprobación humana."""
    return nivel_de_accion(accion) == NivelRiesgo.ALTO


def requiere_traza(accion: str) -> bool:
    """True si la acción modifica estado y debe quedar registrada en la traza."""
    return nivel_de_accion(accion) in (NivelRiesgo.MEDIO, NivelRiesgo.ALTO)


def _resumen(resultado: Any) -> str:
    """Resumen compacto del resultado de una acción para la traza."""
    try:
        return json.dumps(resultado, ensure_ascii=False, default=str)[:500]
    except (TypeError, ValueError):
        return str(resultado)[:200]


def ejecutar_con_autonomia(accion: str, funcion: Callable[..., Any], *args, **kwargs) -> Any:
    """
    Ejecuta ``funcion`` aplicando la matriz de autonomía de ``accion``.

    Comportamiento por nivel:
    - Bajo: ejecución directa.
    - Medio: ejecución + registro en trazas.
    - Alto: aprobación humana previa; si se rechaza devuelve ``AprobacionDenegada``
      y no ejecuta la acción; si se aprueba, ejecuta.

    Auditoría: toda decisión de aprobación y toda llamada a herramienta queda
    registrada en ``trazas_agente.jsonl`` (independientemente del nivel de riesgo).
    """
    from core.trazas import registrar_traza

    nivel = nivel_de_accion(accion)

    if nivel == NivelRiesgo.ALTO:
        from core.seguridad import esperar_aprobacion

        aprobado = esperar_aprobacion(
            f"La acción '{accion}' es de riesgo ALTO (cambio persistente/destructivo)."
        )
        registrar_traza(
            entrada=f"acción: {accion}",
            herramienta=accion,
            argumentos={
                "nivel_riesgo": nivel.value,
                "resultado_aprobacion": "aprobada" if aprobado else "denegada",
            },
            observacion="Decisión de aprobación humana.",
            respuesta_final="aprobada" if aprobado else "denegada",
        )
        if not aprobado:
            return {
                "success": False,
                "status": "error",
                "error_type": "AprobacionDenegada",
                "status_code": None,
                "url": None,
                "message": f"La acción '{accion}' fue rechazada por el operador humano.",
            }

    resultado = funcion(*args, **kwargs)

    registrar_traza(
        entrada=f"acción: {accion}",
        herramienta=accion,
        argumentos={"nivel_riesgo": nivel.value},
        observacion="Herramienta ejecutada.",
        respuesta_final=_resumen(resultado),
    )

    return resultado
