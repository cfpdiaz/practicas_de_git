"""
core.http_client - Cliente HTTP con manejo estructurado de excepciones.

Encapsula la construcción de URL/headers/payload, la petición HTTP vía requests
y la traducción de excepciones a diccionarios de resultado.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
from requests.exceptions import (
    ConnectionError,
    HTTPError,
    JSONDecodeError,
    RequestException,
    Timeout,
)

from core.config import ConfiguracionApp
from core.schemas import validar_respuesta_api

MENSAJE_USUARIO_POR_DEFECTO = (
    "El servidor de base de datos en producción está experimentando una sobrecarga "
    "crítica de CPU (98%) y los clientes reportan tiempos de respuesta muy lentos. "
    "Por favor analiza la situación y clasifica el incidente."
)

INSTRUCCION_SISTEMA_POR_DEFECTO = (
    "Eres un asistente de IA especializado en análisis y clasificación de incidentes técnicos. "
    "Debes responder EXCLUSIVAMENTE con un objeto JSON válido con la siguiente estructura exacta: "
    '{"resumen": "string", "categoria": "string", "prioridad": "alta|media|baja"}. '
    "No incluyas explicaciones, etiquetas markdown ni texto adicional fuera del JSON."
)


class ClienteHttp:
    """Cliente HTTP para consumo de API de IA Generativa."""

    def __init__(self, config: ConfiguracionApp):
        self.config = config

    def enviar(
        self,
        endpoint: str = "chat/completions",
        method: str = "POST",
        prompt: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        verificar_ssl: Optional[bool] = None,
        instruccion_sistema: Optional[str] = None,
        claves_requeridas: Optional[set[str]] = None,
    ) -> Dict[str, Any]:
        """
        Realiza una petición HTTP y devuelve una respuesta estructurada.

        No gestiona el modo simulación: ese chequeo ocurre antes de instanciar el cliente.
        """
        timeout_efectivo = timeout if timeout is not None else self.config.segundos_timeout
        verificacion_efectiva = verificar_ssl if verificar_ssl is not None else self.config.verificar_ssl
        es_relativa = not endpoint.startswith(("http://", "https://"))
        url = f"{self.config.url_base_api}/{endpoint.lstrip('/')}" if es_relativa else endpoint

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "ProyectoEntornoVirtual-AI/1.0",
        }
        if self.config.clave_api and self.config.es_url_confiable(url, es_relativa):
            headers["Authorization"] = f"Bearer {self.config.clave_api}"

        payload_personalizado = payload is not None
        sistema_personalizado = instruccion_sistema is not None
        mensaje_usuario = prompt or MENSAJE_USUARIO_POR_DEFECTO

        # Construir payload por defecto para API de IA Generativa si no se proporciona uno
        if payload is None and method.upper() == "POST":
            contenido_sistema = instruccion_sistema or INSTRUCCION_SISTEMA_POR_DEFECTO
            payload = {
                "model": self.config.nombre_modelo,
                "messages": [
                    {"role": "system", "content": contenido_sistema},
                    {"role": "user", "content": mensaje_usuario},
                ],
                "response_format": {"type": "json_object"},
            }

        marca_tiempo_actual = datetime.now(timezone.utc).isoformat()
        response: Optional[requests.Response] = None

        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=payload,
                headers=headers,
                timeout=timeout_efectivo,
                verify=verificacion_efectiva,
            )

            # Dispara HTTPError para códigos de estado 4xx y 5xx
            response.raise_for_status()

            # Decodificación de la respuesta JSON del servidor
            data = response.json()

            return validar_respuesta_api(
                data=data,
                response=response,
                url=url,
                timestamp=marca_tiempo_actual,
                claves_requeridas=claves_requeridas,
                payload_personalizado=payload_personalizado,
                sistema_personalizado=sistema_personalizado,
            )

        except Timeout as err:
            return {
                "success": False,
                "status": "error",
                "error_type": "Timeout",
                "status_code": None,
                "url": url,
                "timestamp": marca_tiempo_actual,
                "message": f"La petición excedió el tiempo límite ({timeout_efectivo} segundos).",
                "details": str(err),
            }

        except HTTPError as err:
            status_code = response.status_code if response is not None else None
            if status_code == 429:
                reintentar_despues = response.headers.get("Retry-After") if response is not None else None
                return {
                    "success": False,
                    "status": "error",
                    "error_type": "RateLimitExceeded",
                    "status_code": 429,
                    "url": url,
                    "timestamp": marca_tiempo_actual,
                    "retry_after_seconds": reintentar_despues,
                    "message": "Límite de tasa de peticiones alcanzado (HTTP 429 Too Many Requests).",
                    "details": str(err),
                }

            return {
                "success": False,
                "status": "error",
                "error_type": "HTTPError",
                "status_code": status_code,
                "url": url,
                "timestamp": marca_tiempo_actual,
                "message": f"Error en la respuesta HTTP: {status_code}.",
                "details": str(err),
            }

        except (JSONDecodeError, json.JSONDecodeError) as err:
            status_code = response.status_code if response is not None else None
            return {
                "success": False,
                "status": "error",
                "error_type": "JSONDecodeError",
                "status_code": status_code,
                "url": url,
                "timestamp": marca_tiempo_actual,
                "message": "La respuesta obtenida del servidor no contiene una estructura JSON válida.",
                "details": str(err),
            }

        except ConnectionError as err:
            return {
                "success": False,
                "status": "error",
                "error_type": "ConnectionError",
                "status_code": None,
                "url": url,
                "timestamp": marca_tiempo_actual,
                "message": "Error de conexión: No se pudo conectar con el host de destino.",
                "details": str(err),
            }

        except RequestException as err:
            return {
                "success": False,
                "status": "error",
                "error_type": "RequestException",
                "status_code": None,
                "url": url,
                "timestamp": marca_tiempo_actual,
                "message": "Ocurrió una excepción general de requests al procesar la petición.",
                "details": str(err),
            }
