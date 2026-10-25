"""
core.cli - Interfaz de línea de comandos.

Parsea argumentos y coordina la ejecución (tareas, prompt directo y batería
de excepciones).
"""

import argparse
import json
import sys

from core.api import fetch_api_data
from core.tasks import build_task_definitions


def create_parser() -> argparse.ArgumentParser:
    """Crea el parser de argumentos de la CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Script de consumo de API de IA Generativa con salida en JSON estructurado "
            "y manejo de excepciones."
        )
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default="chat/completions",
        help="Endpoint a consultar (por defecto: chat/completions relativo a API_BASE_URL o URL absoluta).",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Texto de entrada para análisis por el modelo de IA.",
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help=(
            "Tarea o caso de uso predefinido (ej. incidente_tecnico, clasificar_incidente, "
            "analisis_sentimiento_soporte, extraccion_entidades_logistica)."
        ),
    )
    parser.add_argument(
        "--test-exceptions",
        action="store_true",
        help="Ejecuta pruebas automáticas de Timeout, HTTP 429 y JSONDecodeError.",
    )
    return parser


def run_tests() -> None:
    """Ejecuta una batería de comprobaciones para demostrar cada excepción solicitada."""
    print("=== MODO DE PRUEBA DE EXCEPCIONES ===", file=sys.stderr)

    scenarios = [
        (
            "1. Petición estándar hacia endpoint de IA (200 OK con structured_output)",
            lambda: fetch_api_data("chat/completions"),
        ),
        (
            "2. Manejo de Timeout (forzado con timeout=0.001)",
            lambda: fetch_api_data("chat/completions", timeout=0.001),
        ),
        (
            "3. Manejo de Rate Limit HTTP 429",
            lambda: fetch_api_data("https://httpbin.org/status/429", method="GET"),
        ),
        (
            "4. Manejo de JSONDecodeError (endpoint que devuelve HTML plano)",
            lambda: fetch_api_data("https://httpbin.org/html", method="GET"),
        ),
    ]

    for title, call in scenarios:
        print(f"\n--- {title} ---", file=sys.stderr)
        res = call()
        print(json.dumps(res, indent=2, ensure_ascii=False))


def main() -> None:
    """Punto de entrada principal de la CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if args.test_exceptions:
        run_tests()
        return

    prompt = args.prompt
    system_instruction = None
    required_keys = None

    if args.task:
        task_norm = args.task.strip().lower()
        matched = build_task_definitions().get(task_norm)
        if matched:
            prompt = args.prompt or matched["prompt"]
            system_instruction = matched["system_instruction"]
            required_keys = matched["required_keys"]

    result = fetch_api_data(
        endpoint=args.endpoint,
        prompt=prompt,
        system_instruction=system_instruction,
        required_keys=required_keys,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
