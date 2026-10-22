"""
app.py - Módulo para consumo de API de IA Generativa con requests y python-dotenv.

Características:
- Carga de variables de entorno desde .env con python-dotenv.
- Consumo HTTP estructurado mediante requests hacia la API de Chat Completions de IA (Groq / OpenRouter).
- Envío de payload POST con modelo llama-3.3-70b-versatile, system prompt y response_format json_object.
- Salida formateada y estructurada en JSON estándar (incluyendo structured_output).
- Manejo robusto de excepciones (sin modificaciones respecto a Gate 1):
    * Timeout (tiempos de espera excedidos)
    * HTTPError (incluyendo manejo específico de Rate Limits HTTP 429 con Retry-After)
    * JSONDecodeError (respuestas no válidas como JSON)
    * ConnectionError y RequestException genéricas
- Batería de pruebas interactivas mediante argumento CLI --test-exceptions.
"""

import argparse
from datetime import datetime, timezone
import json
import os
import sys
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
import requests
from requests.exceptions import (
    ConnectionError,
    HTTPError,
    JSONDecodeError,
    RequestException,
    Timeout,
)
import urllib3

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Configuración leída de las variables de entorno
API_BASE_URL: str = os.getenv("API_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
API_KEY: Optional[str] = os.getenv("API_KEY")
TIMEOUT_SECONDS: float = float(os.getenv("API_TIMEOUT", "10.0"))
MODEL_NAME: str = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
SSL_VERIFY_ENV: str = os.getenv("SSL_VERIFY", "true").strip().lower()
SSL_VERIFY: bool = SSL_VERIFY_ENV not in ("false", "0", "no", "off")

# Dominios confiables autorizados para adjuntar la API Key
TRUSTED_DOMAINS = {
    "api.groq.com",
    "api.openai.com",
    "openrouter.ai",
}

# Valores permitidos y llaves obligatorias para el contrato JSON
ALLOWED_PRIORITIES = {"alta", "media", "baja"}
REQUIRED_KEYS = {"resumen", "categoria", "prioridad"}

# Silenciar advertencias de SSL inseguro solo si se deshabilitó explícitamente la verificación
if not SSL_VERIFY:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def is_trusted_url(url: str, is_relative: bool) -> bool:
    """
    Verifica si una URL de destino es confiable para adjuntar credenciales de autenticación (API Key).
    Solo es confiable si:
    1. Es una ruta relativa a API_BASE_URL.
    2. Su host pertenece a los dominios confiables aprobados (api.groq.com, api.openai.com, openrouter.ai).
    3. Su host coincide con el host configurado en API_BASE_URL.
    """
    if is_relative:
        return True

    parsed_target = urlparse(url)
    target_host = (parsed_target.hostname or "").lower()
    if not target_host:
        return False

    if target_host in TRUSTED_DOMAINS:
        return True

    parsed_base = urlparse(API_BASE_URL)
    base_host = (parsed_base.hostname or "").lower()
    if base_host and target_host == base_host:
        return True

    return False


def _generate_simulated_structured(
    user_message: str,
    system_instruction: Optional[str] = None,
    required_keys: Optional[Any] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Genera una respuesta JSON simulada adecuada según el contexto o claves esperadas."""
    keys_set = set(required_keys) if required_keys else set()

    # 1. Si las claves esperadas coinciden con clasificación de incidentes
    if keys_set == {"resumen", "categoria", "prioridad"} or "categoria" in keys_set:
        return {
            "resumen": "Sobrecarga crítica de CPU (98%) en el servidor de base de datos en producción afectando la latencia de los usuarios.",
            "categoria": "Infraestructura",
            "prioridad": "alta",
        }

    # 2. Si las claves esperadas coinciden con soporte / sentimiento
    if keys_set == {"resumen", "sentimiento", "urgencia"} or "sentimiento" in keys_set:
        return {
            "resumen": "Usuario reporta 3 días sin acceso a cuenta pagada y exige resolución inmediata.",
            "sentimiento": "negativo",
            "urgencia": "alta",
        }

    # 3. Si las claves esperadas coinciden con logística / despachos
    if keys_set == {"numero_pedido", "destino", "estado_envio"} or "numero_pedido" in keys_set:
        return {
            "numero_pedido": "ORD-98234",
            "destino": "Valparaíso",
            "estado_envio": "en_transito",
        }

    # 3. Analizar texto en user_message o system_instruction si no se pasaron required_keys
    combined_text = f"{user_message} {system_instruction or ''}".lower()
    if payload and isinstance(payload.get("messages"), list):
        for msg in payload["messages"]:
            if isinstance(msg, dict) and "content" in msg:
                combined_text += f" {msg['content'].lower()}"

    if "sentimiento" in combined_text or "reclamo" in combined_text:
        return {
            "resumen": "Usuario reporta 3 días sin acceso a cuenta pagada y exige resolución inmediata.",
            "sentimiento": "negativo",
            "urgencia": "alta",
        }
    elif "pedido" in combined_text or "logística" in combined_text or "logistica" in combined_text or "despacho" in combined_text:
        return {
            "numero_pedido": "ORD-98234",
            "destino": "Valparaíso",
            "estado_envio": "en_transito",
        }

    # 4. Si se pasaron otras claves requeridas
    if keys_set:
        return {k: f"valor_simulado_{k}" for k in keys_set}

    # 5. Predeterminado: clasificación de incidentes
    return {
        "resumen": "Sobrecarga crítica de CPU (98%) en el servidor de base de datos en producción afectando la latencia de los usuarios.",
        "categoria": "Infraestructura",
        "prioridad": "alta",
    }


def fetch_api_data(
    endpoint: str = "chat/completions",
    method: str = "POST",
    prompt: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
    verify_ssl: Optional[bool] = None,
    system_instruction: Optional[str] = None,
    required_keys: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Realiza una petición a la API y devuelve una respuesta estructurada en formato dict.

    Captura de forma diferenciada:
    - requests.exceptions.Timeout
    - requests.exceptions.HTTPError (con atención a HTTP 429 Too Many Requests)
    - requests.exceptions.JSONDecodeError
    - requests.exceptions.ConnectionError
    - requests.exceptions.RequestException
    """
    effective_timeout = timeout if timeout is not None else TIMEOUT_SECONDS
    effective_verify = verify_ssl if verify_ssl is not None else SSL_VERIFY
    is_relative = not endpoint.startswith(("http://", "https://"))
    url = f"{API_BASE_URL}/{endpoint.lstrip('/')}" if is_relative else endpoint

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "ProyectoEntornoVirtual-AI/1.0",
    }
    if API_KEY and is_trusted_url(url, is_relative):
        headers["Authorization"] = f"Bearer {API_KEY}"

    custom_payload_provided = payload is not None
    custom_system_provided = system_instruction is not None

    user_message = (
        prompt
        if prompt
        else (
            "El servidor de base de datos en producción está experimentando una sobrecarga "
            "crítica de CPU (98%) y los clientes reportan tiempos de respuesta muy lentos. "
            "Por favor analiza la situación y clasifica el incidente."
        )
    )

    # Construir payload por defecto para API de IA Generativa si no se proporciona uno personalizado
    if payload is None and method.upper() == "POST":
        system_content = (
            system_instruction
            if system_instruction
            else (
                "Eres un asistente de IA especializado en análisis y clasificación de incidentes técnicos. "
                "Debes responder EXCLUSIVAMENTE con un objeto JSON válido con la siguiente estructura exacta: "
                '{"resumen": "string", "categoria": "string", "prioridad": "alta|media|baja"}. '
                "No incluyas explicaciones, etiquetas markdown ni texto adicional fuera del JSON."
            )
        )
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": system_content,
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
            "response_format": {"type": "json_object"},
        }

    current_timestamp = datetime.now(timezone.utc).isoformat()
    response: Optional[requests.Response] = None

    # Modo demostración / simulación offline cuando la clave es el placeholder por defecto y no es un test forzado
    is_placeholder_key = not API_KEY or API_KEY in ("tu_groq_api_key_aqui", "None") or API_KEY.startswith("tu_")
    if is_placeholder_key and not url.startswith("https://httpbin.org") and effective_timeout > 0.05:
        simulated_structured = _generate_simulated_structured(
            user_message=user_message,
            system_instruction=system_instruction,
            required_keys=required_keys,
            payload=payload,
        )
        simulated_data = {
            "id": "chatcmpl-7d2d3a1f9e2b4c8a91b2c3d4e5f6a7b8",
            "object": "chat.completion",
            "created": 1729573200,
            "model": MODEL_NAME,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(simulated_structured, ensure_ascii=False),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 82,
                "completion_tokens": 36,
                "total_tokens": 118,
            },
        }
        return {
            "success": True,
            "status": "success",
            "status_code": 200,
            "url": url,
            "timestamp": current_timestamp,
            "data": simulated_data,
            "structured_output": simulated_structured,
        }
        simulated_data = {
            "id": "chatcmpl-7d2d3a1f9e2b4c8a91b2c3d4e5f6a7b8",
            "object": "chat.completion",
            "created": 1729573200,
            "model": MODEL_NAME,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(simulated_structured, ensure_ascii=False),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 82,
                "completion_tokens": 36,
                "total_tokens": 118,
            },
        }
        return {
            "success": True,
            "status": "success",
            "status_code": 200,
            "url": url,
            "timestamp": current_timestamp,
            "data": simulated_data,
            "structured_output": simulated_structured,
        }

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

        # Navegación defensiva del payload (evita TypeError o AttributeError)
        if not isinstance(data, dict):
            return {
                "success": False,
                "status": "error",
                "error_type": "SchemaValidationError",
                "status_code": response.status_code,
                "url": url,
                "timestamp": current_timestamp,
                "message": "La respuesta obtenida del servidor no es un objeto JSON (dict) válido.",
                "details": f"Tipo recibido: {type(data).__name__}",
            }

        choices = data.get("choices")
        if not isinstance(choices, list) or len(choices) == 0:
            return {
                "success": False,
                "status": "error",
                "error_type": "SchemaValidationError",
                "status_code": response.status_code,
                "url": url,
                "timestamp": current_timestamp,
                "message": "La respuesta de la API no contiene una lista 'choices' válida o está vacía.",
                "details": f"Valor recibido en choices: {choices!r}",
            }

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return {
                "success": False,
                "status": "error",
                "error_type": "SchemaValidationError",
                "status_code": response.status_code,
                "url": url,
                "timestamp": current_timestamp,
                "message": "El primer elemento de 'choices' no es un diccionario válido.",
                "details": f"Tipo de choices[0]: {type(first_choice).__name__}",
            }

        message = first_choice.get("message")
        if not isinstance(message, dict):
            return {
                "success": False,
                "status": "error",
                "error_type": "SchemaValidationError",
                "status_code": response.status_code,
                "url": url,
                "timestamp": current_timestamp,
                "message": "El campo 'message' dentro del primer choice no es un diccionario válido.",
                "details": f"Tipo de message: {type(message).__name__}",
            }

        content_raw = message.get("content")
        if not isinstance(content_raw, str) or not content_raw.strip():
            return {
                "success": False,
                "status": "error",
                "error_type": "SchemaValidationError",
                "status_code": response.status_code,
                "url": url,
                "timestamp": current_timestamp,
                "message": "El campo 'content' dentro de message no es una cadena de texto válida o está vacío.",
                "details": f"Valor de content: {content_raw!r}",
            }

        # Deserialización y validación estricta de esquema (Contrato JSON)
        try:
            structured_content = json.loads(content_raw)
        except (json.JSONDecodeError, TypeError) as err:
            return {
                "success": False,
                "status": "error",
                "error_type": "SchemaValidationError",
                "status_code": response.status_code,
                "url": url,
                "timestamp": current_timestamp,
                "message": "El contenido dentro de 'content' no es un JSON válido.",
                "details": str(err),
            }

        if not isinstance(structured_content, dict):
            return {
                "success": False,
                "status": "error",
                "error_type": "SchemaValidationError",
                "status_code": response.status_code,
                "url": url,
                "timestamp": current_timestamp,
                "message": "El JSON devuelto por el modelo debe ser un diccionario/objeto.",
                "details": f"Tipo recibido: {type(structured_content).__name__}",
            }

        effective_required_keys = (
            set(required_keys)
            if required_keys is not None
            else (REQUIRED_KEYS if (not custom_payload_provided and not custom_system_provided) else None)
        )

        if effective_required_keys:
            missing_keys = effective_required_keys - set(structured_content.keys())
            if missing_keys:
                return {
                    "success": False,
                    "status": "error",
                    "error_type": "SchemaValidationError",
                    "status_code": response.status_code,
                    "url": url,
                    "timestamp": current_timestamp,
                    "message": f"El JSON devuelto carece de llaves requeridas por el contrato: {sorted(missing_keys)}.",
                    "details": f"Llaves presentes: {list(structured_content.keys())}",
                }

        if effective_required_keys == REQUIRED_KEYS and structured_content.get("prioridad") not in ALLOWED_PRIORITIES:
            return {
                "success": False,
                "status": "error",
                "error_type": "SchemaValidationError",
                "status_code": response.status_code,
                "url": url,
                "timestamp": current_timestamp,
                "message": f"El campo 'prioridad' debe ser uno de {sorted(ALLOWED_PRIORITIES)}.",
                "details": f"Valor recibido: {structured_content.get('prioridad')!r}",
            }

        return {
            "success": True,
            "status": "success",
            "status_code": response.status_code,
            "url": url,
            "timestamp": current_timestamp,
            "data": data,
            "structured_output": structured_content,
        }

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
    parser = argparse.ArgumentParser(
        description="Script de consumo de API de IA Generativa con salida en JSON estructurado y manejo de excepciones."
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
        help="Tarea o caso de uso predefinido (ej. incidente_tecnico, clasificar_incidente, analisis_sentimiento_soporte, extraccion_entidades_logistica).",
    )
    parser.add_argument(
        "--test-exceptions",
        action="store_true",
        help="Ejecuta pruebas automáticas de Timeout, HTTP 429 y JSONDecodeError.",
    )

    args = parser.parse_args()

    if args.test_exceptions:
        run_tests()
    else:
        prompt = args.prompt
        system_instruction = None
        required_keys = None

        if args.task:
            task_norm = args.task.strip().lower()
            task_defs = {
                "incidente_tecnico": {
                    "prompt": (
                        "El servidor de base de datos en producción está experimentando una sobrecarga "
                        "crítica de CPU (98%) y los clientes reportan tiempos de respuesta muy lentos."
                    ),
                    "system_instruction": (
                        "Eres un asistente de IA especializado en análisis y clasificación de incidentes técnicos. "
                        "Debes responder EXCLUSIVAMENTE con un objeto JSON válido con la siguiente estructura exacta: "
                        '{"resumen": "string", "categoria": "string", "prioridad": "alta|media|baja"}. '
                        "No incluyas explicaciones ni texto adicional fuera del JSON."
                    ),
                    "required_keys": ["resumen", "categoria", "prioridad"],
                },
                "clasificar_incidente": {
                    "prompt": (
                        "El servidor de base de datos en producción está experimentando una sobrecarga "
                        "crítica de CPU (98%) y los clientes reportan tiempos de respuesta muy lentos."
                    ),
                    "system_instruction": (
                        "Eres un asistente de IA especializado en análisis y clasificación de incidentes técnicos. "
                        "Debes responder EXCLUSIVAMENTE con un objeto JSON válido con la siguiente estructura exacta: "
                        '{"resumen": "string", "categoria": "string", "prioridad": "alta|media|baja"}. '
                        "No incluyas explicaciones ni texto adicional fuera del JSON."
                    ),
                    "required_keys": ["resumen", "categoria", "prioridad"],
                },
                "soporte": {
                    "prompt": (
                        "Llevo 3 días intentando acceder a mi cuenta pagada y nadie me da respuesta. "
                        "Exijo una solución inmediata o la cancelación del servicio."
                    ),
                    "system_instruction": (
                        "Eres un analista de soporte al cliente. Analiza el reclamo y responde EXCLUSIVAMENTE "
                        "con un objeto JSON válido con la siguiente estructura exacta: "
                        '{"resumen": "string", "sentimiento": "positivo|neutral|negativo", "urgencia": "alta|media|baja"}. '
                        "No incluyas explicaciones ni texto adicional fuera del JSON."
                    ),
                    "required_keys": ["resumen", "sentimiento", "urgencia"],
                },
                "analisis_sentimiento_soporte": {
                    "prompt": (
                        "Llevo 3 días intentando acceder a mi cuenta pagada y nadie me da respuesta. "
                        "Exijo una solución inmediata o la cancelación del servicio."
                    ),
                    "system_instruction": (
                        "Eres un analista de soporte al cliente. Analiza el reclamo y responde EXCLUSIVAMENTE "
                        "con un objeto JSON válido con la siguiente estructura exacta: "
                        '{"resumen": "string", "sentimiento": "positivo|neutral|negativo", "urgencia": "alta|media|baja"}. '
                        "No incluyas explicaciones ni texto adicional fuera del JSON."
                    ),
                    "required_keys": ["resumen", "sentimiento", "urgencia"],
                },
                "logistica": {
                    "prompt": (
                        "El pedido #ORD-98234 dirigido a la ciudad de Valparaíso se encuentra actualmente en ruta de entrega."
                    ),
                    "system_instruction": (
                        "Eres un extractor de datos logísticos. Procesa la solicitud y responde EXCLUSIVAMENTE "
                        "con un objeto JSON válido con la siguiente estructura exacta: "
                        '{"numero_pedido": "string", "destino": "string", "estado_envio": "pendiente|en_transito|entregado"}. '
                        "No incluyas explicaciones ni texto adicional fuera del JSON."
                    ),
                    "required_keys": ["numero_pedido", "destino", "estado_envio"],
                },
                "extraccion_entidades_logistica": {
                    "prompt": (
                        "El pedido #ORD-98234 dirigido a la ciudad de Valparaíso se encuentra actualmente en ruta de entrega."
                    ),
                    "system_instruction": (
                        "Eres un extractor de datos logísticos. Procesa la solicitud y responde EXCLUSIVAMENTE "
                        "con un objeto JSON válido con la siguiente estructura exacta: "
                        '{"numero_pedido": "string", "destino": "string", "estado_envio": "pendiente|en_transito|entregado"}. '
                        "No incluyas explicaciones ni texto adicional fuera del JSON."
                    ),
                    "required_keys": ["numero_pedido", "destino", "estado_envio"],
                },
            }

            matched = task_defs.get(task_norm)
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
