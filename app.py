"""
app.py - Punto de entrada compatible hacia atrás y funciones del curso.

La lógica vive en el paquete `core` (arquitectura modular). Este módulo
mantiene la interfaz pública original (`fetch_api_data`, `is_trusted_url`,
`run_tests`, `main`), las funciones de la rúbrica del curso (`armar_peticion`,
`enviar_peticion`, `extraer_texto`) y las variables globales derivadas de la
configuración para no romper a los consumidores existentes.
"""

from core.config import config, AppConfig, load_config, is_trusted_url
from core.api import (
    fetch_api_data,
    armar_peticion,
    enviar_peticion,
    extraer_texto,
    Peticion,
    SimulatedResponse,
)
from core.schemas import ALLOWED_PRIORITIES, REQUIRED_KEYS
from core.tasks import build_task_definitions
from core.cli import run_tests, main

# Variables globales derivadas de la configuración (compatibilidad hacia atrás)
API_BASE_URL = config.api_base_url
API_KEY = config.api_key
TIMEOUT_SECONDS = config.timeout_seconds
MODEL_NAME = config.model_name
SSL_VERIFY = config.ssl_verify
TRUSTED_DOMAINS = config.trusted_domains

__all__ = [
    "AppConfig",
    "load_config",
    "config",
    "is_trusted_url",
    "fetch_api_data",
    "armar_peticion",
    "enviar_peticion",
    "extraer_texto",
    "Peticion",
    "SimulatedResponse",
    "run_tests",
    "main",
    "build_task_definitions",
    "ALLOWED_PRIORITIES",
    "REQUIRED_KEYS",
    "API_BASE_URL",
    "API_KEY",
    "TIMEOUT_SECONDS",
    "MODEL_NAME",
    "SSL_VERIFY",
    "TRUSTED_DOMAINS",
]


if __name__ == "__main__":
    main()
