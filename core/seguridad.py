"""
core.seguridad - Control de aprobación humana para acciones de riesgo.

Provee ``esperar_aprobacion``, una barrera de confirmación con límite de tiempo
que las herramientas de riesgo alto (o con impacto económico) deben invocar
antes de ejecutarse.

Comportamiento:
- Si la variable de entorno ``AUTORIZAR_ALTO`` está activa, autoriza (para
  auditorías/CI automatizadas).
- Si no hay terminal interactiva, deniega de forma segura (sin colgar ni romper).
- Con terminal interactiva, pide confirmación con límite de tiempo.

Ver ``docs/limites_autonomia_agente.md``.
"""

import os
import select
import sys


def esperar_aprobacion(mensaje: str, segundos_timeout: float = 30.0) -> bool:
    """
    Pide confirmación humana antes de ejecutar una acción de riesgo.

    Args:
        mensaje: descripción de la acción que requiere aprobación.
        segundos_timeout: tiempo máximo de espera (0 o negativo = sin límite).

    Returns:
        True si se aprueba (respuesta afirmativa o ``AUTORIZAR_ALTO`` activa);
        False si se rechaza, expira el tiempo o no hay terminal interactiva.
    """
    print(f"[APROBACIÓN REQUERIDA] {mensaje}")

    # Autorización explícita para entornos automatizados (CI/auditoría).
    if os.getenv("AUTORIZAR_ALTO", "").strip().lower() in ("1", "true", "yes", "si", "sí"):
        print("Autorización automática activada (AUTORIZAR_ALTO).")
        return True

    # Entorno no interactivo: denegar por defecto (fail-safe).
    if not sys.stdin.isatty():
        print("Sin terminal interactiva: acción rechazada por defecto.")
        return False

    print("Escribe 'si' para aprobar o cualquier otra cosa para rechazar:")

    try:
        if segundos_timeout > 0:
            listo, _, _ = select.select([sys.stdin], [], [], segundos_timeout)
            if not listo:
                print("Tiempo agotado: acción rechazada por inactividad.")
                return False
        respuesta = input()
    except (OSError, ValueError):
        # select() no aplica a stdin en esta plataforma (p. ej. Windows): input directo.
        respuesta = input()
    except EOFError:
        return False

    return (respuesta or "").strip().lower() in ("si", "sí", "s", "yes", "y")
