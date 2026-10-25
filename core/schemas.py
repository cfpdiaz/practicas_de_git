"""
core.schemas - Contratos JSON y validación de la respuesta de la API.

Encapsula la navegación defensiva del payload y la validación del contrato
JSON, devolviendo diccionarios de resultado listos para serializar.
"""

import json
from typing import Any, Dict, Optional

# Valores permitidos y llaves obligatorias para el contrato JSON
ALLOWED_PRIORITIES = {"alta", "media", "baja"}
REQUIRED_KEYS = {"resumen", "categoria", "prioridad"}


def validate_api_response(
    data: Any,
    response: Any,
    url: str,
    timestamp: str,
    required_keys: Optional[set[str]],
    custom_payload_provided: bool,
    custom_system_provided: bool,
) -> Dict[str, Any]:
    """
    Valida la estructura de la respuesta de la API y el contrato JSON.

    Args:
        data: Respuesta JSON ya parseada (dict esperado).
        response: Objeto response de requests (para status_code).
        url: URL consultada.
        timestamp: Marca de tiempo ISO de la petición.
        required_keys: Claves requeridas por el contrato (opcional).
        custom_payload_provided: True si se envió un payload personalizado.
        custom_system_provided: True si se envió una instrucción de sistema personalizada.

    Returns:
        Dict de resultado ("success" True/False y campos asociados).
    """
    if not isinstance(data, dict):
        return {
            "success": False,
            "status": "error",
            "error_type": "SchemaValidationError",
            "status_code": response.status_code,
            "url": url,
            "timestamp": timestamp,
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
            "timestamp": timestamp,
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
            "timestamp": timestamp,
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
            "timestamp": timestamp,
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
            "timestamp": timestamp,
            "message": "El campo 'content' dentro de message no es una cadena de texto válida o está vacío.",
            "details": f"Valor de content: {content_raw!r}",
        }

    try:
        structured_content = json.loads(content_raw)
    except (json.JSONDecodeError, TypeError) as err:
        return {
            "success": False,
            "status": "error",
            "error_type": "SchemaValidationError",
            "status_code": response.status_code,
            "url": url,
            "timestamp": timestamp,
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
            "timestamp": timestamp,
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
                "timestamp": timestamp,
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
            "timestamp": timestamp,
            "message": f"El campo 'prioridad' debe ser uno de {sorted(ALLOWED_PRIORITIES)}.",
            "details": f"Valor recibido: {structured_content.get('prioridad')!r}",
        }

    return {
        "success": True,
        "status": "success",
        "status_code": response.status_code,
        "url": url,
        "timestamp": timestamp,
        "data": data,
        "structured_output": structured_content,
    }
