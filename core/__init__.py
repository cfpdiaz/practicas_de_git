"""
core - Núcleo modular para consumo de API de IA Generativa.

Módulos:
- config: Configuración inmutable e inyectable.
- schemas: Contratos JSON y validación de respuestas.
- simulation: Modo demo/simulación offline.
- http_client: Cliente HTTP con manejo de excepciones.
- api: API pública de alto nivel.
- tasks: Catálogo de tareas desde prompts/banco.py.
- cli: Interfaz de línea de comandos.
"""

from core.config import AppConfig, load_config, config, is_trusted_url
from core.schemas import ALLOWED_PRIORITIES, REQUIRED_KEYS, validate_api_response
from core.simulation import build_simulated_response, is_simulation_mode
from core.http_client import HttpClient
from core.api import fetch_api_data
from core.tasks import build_task_definitions
from core.cli import create_parser, run_tests, main

__all__ = [
    "AppConfig",
    "load_config",
    "config",
    "is_trusted_url",
    "ALLOWED_PRIORITIES",
    "REQUIRED_KEYS",
    "validate_api_response",
    "build_simulated_response",
    "is_simulation_mode",
    "HttpClient",
    "fetch_api_data",
    "build_task_definitions",
    "create_parser",
    "run_tests",
    "main",
]
