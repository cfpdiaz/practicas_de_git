"""
core.cli - Interfaz de línea de comandos.

Parsea argumentos y coordina la ejecución (tareas, prompt directo y batería
de excepciones).
"""

import argparse
import json
import sys

from core.api import obtener_datos_api
from core.tasks import construir_definiciones_tareas


def crear_analizador() -> argparse.ArgumentParser:
    """Crea el analizador de argumentos de la CLI."""
    analizador = argparse.ArgumentParser(
        description=(
            "Script de consumo de API de IA Generativa con salida en JSON estructurado "
            "y manejo de excepciones."
        )
    )
    analizador.add_argument(
        "--endpoint",
        type=str,
        default="chat/completions",
        help="Endpoint a consultar (por defecto: chat/completions relativo a API_BASE_URL o URL absoluta).",
    )
    analizador.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Texto de entrada para análisis por el modelo de IA.",
    )
    analizador.add_argument(
        "--task",
        type=str,
        default=None,
        help=(
            "Tarea o caso de uso predefinido (ej. incidente_tecnico, clasificar_incidente, "
            "analisis_sentimiento_soporte, extraccion_entidades_logistica)."
        ),
    )
    analizador.add_argument(
        "--test-exceptions",
        action="store_true",
        help="Ejecuta pruebas automáticas de Timeout, HTTP 429 y JSONDecodeError.",
    )
    return analizador


def ejecutar_pruebas() -> None:
    """Ejecuta una batería de comprobaciones para demostrar cada excepción solicitada."""
    print("=== MODO DE PRUEBA DE EXCEPCIONES ===", file=sys.stderr)

    escenarios = [
        (
            "1. Petición estándar hacia endpoint de IA (200 OK con structured_output)",
            lambda: obtener_datos_api("chat/completions"),
        ),
        (
            "2. Manejo de Timeout (forzado con timeout=0.001)",
            lambda: obtener_datos_api("chat/completions", timeout=0.001),
        ),
        (
            "3. Manejo de Rate Limit HTTP 429",
            lambda: obtener_datos_api("https://httpbin.org/status/429", method="GET"),
        ),
        (
            "4. Manejo de JSONDecodeError (endpoint que devuelve HTML plano)",
            lambda: obtener_datos_api("https://httpbin.org/html", method="GET"),
        ),
    ]

    for title, call in escenarios:
        print(f"\n--- {title} ---", file=sys.stderr)
        res = call()
        print(json.dumps(res, indent=2, ensure_ascii=False))


def main() -> None:
    """Punto de entrada principal de la CLI."""
    analizador = crear_analizador()
    argumentos = analizador.parse_args()

    if argumentos.test_exceptions:
        ejecutar_pruebas()
        return

    prompt = argumentos.prompt
    instruccion_sistema = None
    claves_requeridas = None

    if argumentos.task:
        tarea_normalizada = argumentos.task.strip().lower()
        coincidencia = construir_definiciones_tareas().get(tarea_normalizada)
        if coincidencia:
            prompt = argumentos.prompt or coincidencia["prompt"]
            instruccion_sistema = coincidencia["instruccion_sistema"]
            claves_requeridas = coincidencia["claves_requeridas"]

    result = obtener_datos_api(
        endpoint=argumentos.endpoint,
        prompt=prompt,
        instruccion_sistema=instruccion_sistema,
        claves_requeridas=claves_requeridas,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
