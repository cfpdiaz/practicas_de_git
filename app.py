"""
app.py - Punto de entrada compatible hacia atrás y funciones del curso.

La lógica vive en el paquete `core` (arquitectura modular). Este módulo
mantiene la interfaz pública original (`obtener_datos_api`, `es_url_confiable`,
`ejecutar_pruebas`, `main`), las funciones de la rúbrica del curso (`armar_peticion`,
`enviar_peticion`, `extraer_texto`) y las variables globales derivadas de la
configuración para no romper a los consumidores existentes.
"""

from core.config import config, ConfiguracionApp, cargar_configuracion, es_url_confiable
from core.api import (
    obtener_datos_api,
    armar_peticion,
    enviar_peticion,
    extraer_texto,
    Peticion,
    RespuestaSimulada,
)
from core.schemas import PRIORIDADES_PERMITIDAS, CLAVES_REQUERIDAS
from core.tasks import construir_definiciones_tareas
from core.cli import ejecutar_pruebas, main

# Variables globales derivadas de la configuración (compatibilidad hacia atrás)
URL_BASE_API = config.url_base_api
CLAVE_API = config.clave_api
SEGUNDOS_TIMEOUT = config.segundos_timeout
NOMBRE_MODELO = config.nombre_modelo
VERIFICAR_SSL = config.verificar_ssl
DOMINIOS_CONFIABLES = config.dominios_confiables

__all__ = [
    "ConfiguracionApp",
    "cargar_configuracion",
    "config",
    "es_url_confiable",
    "obtener_datos_api",
    "armar_peticion",
    "enviar_peticion",
    "extraer_texto",
    "Peticion",
    "RespuestaSimulada",
    "ejecutar_pruebas",
    "main",
    "construir_definiciones_tareas",
    "PRIORIDADES_PERMITIDAS",
    "CLAVES_REQUERIDAS",
    "URL_BASE_API",
    "CLAVE_API",
    "SEGUNDOS_TIMEOUT",
    "NOMBRE_MODELO",
    "VERIFICAR_SSL",
    "DOMINIOS_CONFIABLES",
]


if __name__ == "__main__":
    main()
