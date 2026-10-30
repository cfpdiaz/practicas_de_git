"""
core - Núcleo modular para consumo de API de IA Generativa.

Módulos:
- config: Configuración inmutable e inyectable.
- schemas: Contratos JSON y validación de respuestas.
- simulation: Modo demo/simulación offline.
- http_client: Cliente HTTP con manejo de excepciones.
- api: API pública de alto nivel y funciones del curso.
- tasks: Catálogo de tareas desde prompts/banco.py.
- cli: Interfaz de línea de comandos.
"""

from core.config import ConfiguracionApp, cargar_configuracion, config, es_url_confiable
from core.schemas import PRIORIDADES_PERMITIDAS, CLAVES_REQUERIDAS, validar_respuesta_api
from core.simulation import construir_respuesta_simulada, es_modo_simulacion
from core.http_client import ClienteHttp
from core.api import (
    Peticion,
    RespuestaSimulada,
    armar_peticion,
    enviar_peticion,
    extraer_texto,
    obtener_datos_api,
)
from core.tasks import construir_definiciones_tareas
from core.cli import crear_analizador, ejecutar_pruebas, main

__all__ = [
    "ConfiguracionApp",
    "cargar_configuracion",
    "config",
    "es_url_confiable",
    "PRIORIDADES_PERMITIDAS",
    "CLAVES_REQUERIDAS",
    "validar_respuesta_api",
    "construir_respuesta_simulada",
    "es_modo_simulacion",
    "ClienteHttp",
    "Peticion",
    "RespuestaSimulada",
    "armar_peticion",
    "enviar_peticion",
    "extraer_texto",
    "obtener_datos_api",
    "construir_definiciones_tareas",
    "crear_analizador",
    "ejecutar_pruebas",
    "main",
]
