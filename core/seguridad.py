"""
core.seguridad - Control de aprobación humana para acciones de riesgo.

Provee ``esperar_aprobacion``, una barrera de confirmación con límite de tiempo
que las herramientas de riesgo alto (o con impacto económico) deben invocar
antes de ejecutarse. Ver ``docs/limites_autonomia_agente.md``.
"""

import select
import sys


def esperar_aprobacion(mensaje: str, timeout_segundos: float = 30.0) -> bool:
    """
    Pide confirmación humana antes de ejecutar una acción de riesgo.

    Args:
        mensaje: descripción de la acción que requiere aprobación.
        timeout_segundos: tiempo máximo de espera (0 o negativo = sin límite).

    Returns:
        True si la respuesta es afirmativa; False si es negativa o si expira
        el tiempo de espera.
    """
    print(f"[APROBACIÓN REQUERIDA] {mensaje}")
    print("Escribe 'si' para aprobar o cualquier otra cosa para rechazar:")

    try:
        if sys.stdin.isatty() and timeout_segundos > 0:
            listo, _, _ = select.select([sys.stdin], [], [], timeout_segundos)
            if not listo:
                print("Tiempo agotado: acción rechazada por inactividad.")
                return False
        respuesta = input()
    except (OSError, ValueError):
        # select() no aplica a stdin en esta plataforma (p. ej. Windows):
        # se espera la respuesta sin límite de tiempo.
        respuesta = input()

    return (respuesta or "").strip().lower() in ("si", "sí", "s", "yes", "y")
