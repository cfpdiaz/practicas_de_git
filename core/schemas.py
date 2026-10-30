"""
core.schemas - Contratos JSON y validación de la respuesta de la API.

Encapsula la navegación defensiva del payload y la validación del contrato
JSON, devolviendo diccionarios de resultado listos para serializar.
"""

import json
from typing import Any, Dict, Optional

# Valores permitidos y llaves obligatorias para el contrato JSON
PRIORIDADES_PERMITIDAS = {"alta", "media", "baja"}
CLAVES_REQUERIDAS = {"resumen", "categoria", "prioridad"}


def validar_respuesta_api(
    data: Any,
    response: Any,
    url: str,
    timestamp: str,
    claves_requeridas: Optional[set[str]],
    payload_personalizado: bool,
    sistema_personalizado: bool,
) -> Dict[str, Any]:
    """
    Valida la estructura de la respuesta de la API y el contrato JSON.

    Args:
        data: Respuesta JSON ya parseada (dict esperado).
        response: Objeto response de requests (para status_code).
        url: URL consultada.
        timestamp: Marca de tiempo ISO de la petición.
        claves_requeridas: Claves requeridas por el contrato (opcional).
        payload_personalizado: True si se envió un payload personalizado.
        sistema_personalizado: True si se envió una instrucción de sistema personalizada.

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

    primera_opcion = choices[0]
    if not isinstance(primera_opcion, dict):
        return {
            "success": False,
            "status": "error",
            "error_type": "SchemaValidationError",
            "status_code": response.status_code,
            "url": url,
            "timestamp": timestamp,
            "message": "El primer elemento de 'choices' no es un diccionario válido.",
            "details": f"Tipo de choices[0]: {type(primera_opcion).__name__}",
        }

    message = primera_opcion.get("message")
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

    contenido_crudo = message.get("content")
    if not isinstance(contenido_crudo, str) or not contenido_crudo.strip():
        return {
            "success": False,
            "status": "error",
            "error_type": "SchemaValidationError",
            "status_code": response.status_code,
            "url": url,
            "timestamp": timestamp,
            "message": "El campo 'content' dentro de message no es una cadena de texto válida o está vacío.",
            "details": f"Valor de content: {contenido_crudo!r}",
        }

    try:
        contenido_estructurado = json.loads(contenido_crudo)
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

    if not isinstance(contenido_estructurado, dict):
        return {
            "success": False,
            "status": "error",
            "error_type": "SchemaValidationError",
            "status_code": response.status_code,
            "url": url,
            "timestamp": timestamp,
            "message": "El JSON devuelto por el modelo debe ser un diccionario/objeto.",
            "details": f"Tipo recibido: {type(contenido_estructurado).__name__}",
        }

    claves_requeridas_efectivas = (
        set(claves_requeridas)
        if claves_requeridas is not None
        else (CLAVES_REQUERIDAS if (not payload_personalizado and not sistema_personalizado) else None)
    )

    if claves_requeridas_efectivas:
        claves_faltantes = claves_requeridas_efectivas - set(contenido_estructurado.keys())
        if claves_faltantes:
            return {
                "success": False,
                "status": "error",
                "error_type": "SchemaValidationError",
                "status_code": response.status_code,
                "url": url,
                "timestamp": timestamp,
                "message": f"El JSON devuelto carece de llaves requeridas por el contrato: {sorted(claves_faltantes)}.",
                "details": f"Llaves presentes: {list(contenido_estructurado.keys())}",
            }

    if claves_requeridas_efectivas == CLAVES_REQUERIDAS and contenido_estructurado.get("prioridad") not in PRIORIDADES_PERMITIDAS:
        return {
            "success": False,
            "status": "error",
            "error_type": "SchemaValidationError",
            "status_code": response.status_code,
            "url": url,
            "timestamp": timestamp,
            "message": f"El campo 'prioridad' debe ser uno de {sorted(PRIORIDADES_PERMITIDAS)}.",
            "details": f"Valor recibido: {contenido_estructurado.get('prioridad')!r}",
        }

    return {
        "success": True,
        "status": "success",
        "status_code": response.status_code,
        "url": url,
        "timestamp": timestamp,
        "data": data,
        "structured_output": contenido_estructurado,
    }
