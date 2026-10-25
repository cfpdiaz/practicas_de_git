"""
core.api - API pública de alto nivel.

`fetch_api_data` coordina el modo simulación y el cliente HTTP, y acepta una
configuración inyectable para facilitar el testing sin variables globales.
"""

from typing import Any, Dict, Optional

from core.config import AppConfig, config as default_config
from core.http_client import DEFAULT_USER_MESSAGE, HttpClient
from core.simulation import build_simulated_response, is_simulation_mode


def fetch_api_data(
    endpoint: str = "chat/completions",
    method: str = "POST",
    prompt: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
    verify_ssl: Optional[bool] = None,
    system_instruction: Optional[str] = None,
    required_keys: Optional[set[str]] = None,
    config: Optional[AppConfig] = None,
) -> Dict[str, Any]:
    """
    Realiza una petición a la API y devuelve una respuesta estructurada.

    Args:
        endpoint: Endpoint a consultar (relativo o URL absoluta).
        method: Método HTTP.
        prompt: Texto de entrada para el modelo.
        params: Query parameters.
        payload: Payload personalizado.
        timeout: Timeout en segundos.
        verify_ssl: Verificar certificado SSL.
        system_instruction: Instrucción de sistema personalizada.
        required_keys: Claves requeridas para validación del contrato.
        config: Configuración inyectable (por defecto usa la global).

    Returns:
        Dict con respuesta estructurada.
    """
    cfg = config or default_config

    effective_timeout = timeout if timeout is not None else cfg.timeout_seconds
    is_relative = not endpoint.startswith(("http://", "https://"))
    url = f"{cfg.api_base_url}/{endpoint.lstrip('/')}" if is_relative else endpoint
    user_message = prompt or DEFAULT_USER_MESSAGE

    # Modo simulación offline cuando la clave es un placeholder por defecto
    if is_simulation_mode(cfg, url, effective_timeout):
        return build_simulated_response(
            config=cfg,
            url=url,
            user_message=user_message,
            system_instruction=system_instruction,
            required_keys=required_keys,
            payload=payload,
        )

    return HttpClient(cfg).fetch(
        endpoint=endpoint,
        method=method,
        prompt=prompt,
        params=params,
        payload=payload,
        timeout=timeout,
        verify_ssl=verify_ssl,
        system_instruction=system_instruction,
        required_keys=required_keys,
    )
