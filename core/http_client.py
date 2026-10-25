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

from core.config import AppConfig
from core.schemas import validate_api_response

DEFAULT_USER_MESSAGE = (
    "El servidor de base de datos en producción está experimentando una sobrecarga "
    "crítica de CPU (98%) y los clientes reportan tiempos de respuesta muy lentos. "
    "Por favor analiza la situación y clasifica el incidente."
)

DEFAULT_SYSTEM_INSTRUCTION = (
    "Eres un asistente de IA especializado en análisis y clasificación de incidentes técnicos. "
    "Debes responder EXCLUSIVAMENTE con un objeto JSON válido con la siguiente estructura exacta: "
    '{"resumen": "string", "categoria": "string", "prioridad": "alta|media|baja"}. '
    "No incluyas explicaciones, etiquetas markdown ni texto adicional fuera del JSON."
)


class HttpClient:
    """Cliente HTTP para consumo de API de IA Generativa."""

    def __init__(self, config: AppConfig):
        self.config = config

    def fetch(
        self,
        endpoint: str = "chat/completions",
        method: str = "POST",
        prompt: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        verify_ssl: Optional[bool] = None,
        system_instruction: Optional[str] = None,
        required_keys: Optional[set[str]] = None,
    ) -> Dict[str, Any]:
        """
        Realiza una petición HTTP y devuelve una respuesta estructurada.

        No gestiona el modo simulación: ese chequeo ocurre antes de instanciar el cliente.
        """
        effective_timeout = timeout if timeout is not None else self.config.timeout_seconds
        effective_verify = verify_ssl if verify_ssl is not None else self.config.ssl_verify
        is_relative = not endpoint.startswith(("http://", "https://"))
        url = f"{self.config.api_base_url}/{endpoint.lstrip('/')}" if is_relative else endpoint

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "ProyectoEntornoVirtual-AI/1.0",
        }
        if self.config.api_key and self.config.is_trusted_url(url, is_relative):
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        custom_payload_provided = payload is not None
        custom_system_provided = system_instruction is not None
        user_message = prompt or DEFAULT_USER_MESSAGE

        # Construir payload por defecto para API de IA Generativa si no se proporciona uno
        if payload is None and method.upper() == "POST":
            system_content = system_instruction or DEFAULT_SYSTEM_INSTRUCTION
            payload = {
                "model": self.config.model_name,
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_message},
                ],
                "response_format": {"type": "json_object"},
            }

        current_timestamp = datetime.now(timezone.utc).isoformat()
        response: Optional[requests.Response] = None

        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=payload,
                headers=headers,
                timeout=effective_timeout,
                verify=effective_verify,
            )

            # Dispara HTTPError para códigos de estado 4xx y 5xx
            response.raise_for_status()

            # Decodificación de la respuesta JSON del servidor
            data = response.json()

            return validate_api_response(
                data=data,
                response=response,
                url=url,
                timestamp=current_timestamp,
                required_keys=required_keys,
                custom_payload_provided=custom_payload_provided,
                custom_system_provided=custom_system_provided,
            )

        except Timeout as err:
            return {
                "success": False,
                "status": "error",
                "error_type": "Timeout",
                "status_code": None,
                "url": url,
                "timestamp": current_timestamp,
                "message": f"La petición excedió el tiempo límite ({effective_timeout} segundos).",
                "details": str(err),
            }

        except HTTPError as err:
            status_code = response.status_code if response is not None else None
            if status_code == 429:
                retry_after = response.headers.get("Retry-After") if response is not None else None
                return {
                    "success": False,
                    "status": "error",
                    "error_type": "RateLimitExceeded",
                    "status_code": 429,
                    "url": url,
                    "timestamp": current_timestamp,
                    "retry_after_seconds": retry_after,
                    "message": "Límite de tasa de peticiones alcanzado (HTTP 429 Too Many Requests).",
                    "details": str(err),
                }

            return {
                "success": False,
                "status": "error",
                "error_type": "HTTPError",
                "status_code": status_code,
                "url": url,
                "timestamp": current_timestamp,
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
                "timestamp": current_timestamp,
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
                "timestamp": current_timestamp,
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
                "timestamp": current_timestamp,
                "message": "Ocurrió una excepción general de requests al procesar la petición.",
                "details": str(err),
            }
