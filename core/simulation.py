"""
core.simulation - Modo simulación offline (placeholder key).

Genera respuestas simuladas cuando la API Key es un placeholder por defecto,
evitando llamadas de red reales.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.config import ConfiguracionApp


def _generar_estructurado_simulado(
    mensaje_usuario: str,
    instruccion_sistema: Optional[str] = None,
    claves_requeridas: Optional[set[str]] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Genera una respuesta JSON simulada adecuada según el contexto o claves esperadas."""
    conjunto_claves = set(claves_requeridas) if claves_requeridas else set()

    # 1. Si las claves esperadas coinciden con clasificación de incidentes
    if conjunto_claves == {"resumen", "categoria", "prioridad"} or "categoria" in conjunto_claves:
        return {
            "resumen": "Sobrecarga crítica de CPU (98%) en el servidor de base de datos en producción afectando la latencia de los usuarios.",
            "categoria": "Infraestructura",
            "prioridad": "alta",
        }

    # 2. Si las claves esperadas coinciden con soporte / sentimiento
    if conjunto_claves == {"resumen", "sentimiento", "urgencia"} or "sentimiento" in conjunto_claves:
        return {
            "resumen": "Usuario reporta 3 días sin acceso a cuenta pagada y exige resolución inmediata.",
            "sentimiento": "negativo",
            "urgencia": "alta",
        }

    # 3. Si las claves esperadas coinciden con logística / despachos
    if conjunto_claves == {"numero_pedido", "destino", "estado_envio"} or "numero_pedido" in conjunto_claves:
        return {
            "numero_pedido": "ORD-98234",
            "destino": "Valparaíso",
            "estado_envio": "en_transito",
        }

    # 4. Analizar texto en mensaje_usuario o instruccion_sistema si no se pasaron claves_requeridas
    texto_combinado = f"{mensaje_usuario} {instruccion_sistema or ''}".lower()
    if payload and isinstance(payload.get("messages"), list):
        for msg in payload["messages"]:
            if isinstance(msg, dict) and "content" in msg:
                texto_combinado += f" {msg['content'].lower()}"

    if "sentimiento" in texto_combinado or "reclamo" in texto_combinado:
        return {
            "resumen": "Usuario reporta 3 días sin acceso a cuenta pagada y exige resolución inmediata.",
            "sentimiento": "negativo",
            "urgencia": "alta",
        }
    elif "pedido" in texto_combinado or "logística" in texto_combinado or "logistica" in texto_combinado or "despacho" in texto_combinado:
        return {
            "numero_pedido": "ORD-98234",
            "destino": "Valparaíso",
            "estado_envio": "en_transito",
        }

    # 5. Si se pasaron otras claves requeridas
    if conjunto_claves:
        return {k: f"valor_simulado_{k}" for k in conjunto_claves}

    # 6. Predeterminado: clasificación de incidentes
    return {
        "resumen": "Sobrecarga crítica de CPU (98%) en el servidor de base de datos en producción afectando la latencia de los usuarios.",
        "categoria": "Infraestructura",
        "prioridad": "alta",
    }


def es_modo_simulacion(config: ConfiguracionApp, url: str, timeout: float) -> bool:
    """
    Determina si debe usarse el modo simulación.

    Activa cuando la API Key es un placeholder por defecto, la URL no apunta a
    httpbin.org (usado en la batería de excepciones) y el timeout no es forzado.
    """
    key = config.clave_api
    es_placeholder = not key or key in ("tu_groq_api_key_aqui", "None") or key.startswith("tu_")
    return es_placeholder and not url.startswith("https://httpbin.org") and timeout > 0.05


def construir_respuesta_simulada(
    config: ConfiguracionApp,
    url: str,
    mensaje_usuario: str,
    instruccion_sistema: Optional[str] = None,
    claves_requeridas: Optional[set[str]] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construye una respuesta completa simulada (compatible con el flujo normal)."""
    estructurado_simulado = _generar_estructurado_simulado(
        mensaje_usuario=mensaje_usuario,
        instruccion_sistema=instruccion_sistema,
        claves_requeridas=claves_requeridas,
        payload=payload,
    )

    marca_tiempo_actual = datetime.now(timezone.utc).isoformat()
    datos_simulados = {
        "id": "chatcmpl-7d2d3a1f9e2b4c8a91b2c3d4e5f6a7b8",
        "object": "chat.completion",
        "created": 1729573200,
        "model": config.nombre_modelo,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(estructurado_simulado, ensure_ascii=False),
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
        "timestamp": marca_tiempo_actual,
        "data": datos_simulados,
        "structured_output": estructurado_simulado,
    }
