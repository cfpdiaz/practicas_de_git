"""
core.simulation - Modo simulación offline (placeholder key).

Genera respuestas simuladas cuando la API Key es un placeholder por defecto,
evitando llamadas de red reales.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.config import AppConfig


def _generate_simulated_structured(
    user_message: str,
    system_instruction: Optional[str] = None,
    required_keys: Optional[set[str]] = None,
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

    # 4. Analizar texto en user_message o system_instruction si no se pasaron required_keys
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

    # 5. Si se pasaron otras claves requeridas
    if keys_set:
        return {k: f"valor_simulado_{k}" for k in keys_set}

    # 6. Predeterminado: clasificación de incidentes
    return {
        "resumen": "Sobrecarga crítica de CPU (98%) en el servidor de base de datos en producción afectando la latencia de los usuarios.",
        "categoria": "Infraestructura",
        "prioridad": "alta",
    }


def is_simulation_mode(config: AppConfig, url: str, timeout: float) -> bool:
    """
    Determina si debe usarse el modo simulación.

    Activa cuando la API Key es un placeholder por defecto, la URL no apunta a
    httpbin.org (usado en la batería de excepciones) y el timeout no es forzado.
    """
    key = config.api_key
    is_placeholder = not key or key in ("tu_groq_api_key_aqui", "None") or key.startswith("tu_")
    return is_placeholder and not url.startswith("https://httpbin.org") and timeout > 0.05


def build_simulated_response(
    config: AppConfig,
    url: str,
    user_message: str,
    system_instruction: Optional[str] = None,
    required_keys: Optional[set[str]] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construye una respuesta completa simulada (compatible con el flujo normal)."""
    simulated_structured = _generate_simulated_structured(
        user_message=user_message,
        system_instruction=system_instruction,
        required_keys=required_keys,
        payload=payload,
    )

    current_timestamp = datetime.now(timezone.utc).isoformat()
    simulated_data = {
        "id": "chatcmpl-7d2d3a1f9e2b4c8a91b2c3d4e5f6a7b8",
        "object": "chat.completion",
        "created": 1729573200,
        "model": config.model_name,
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
