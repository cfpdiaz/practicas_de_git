"""
core.api - API pública de alto nivel y funciones de consumo.

Provee las funciones requeridas por la rúbrica del curso:
- `armar_peticion`: Construye cabeceras, URL y cuerpo JSON (separando roles system/user).
- `enviar_peticion`: Realiza la llamada HTTP (o simulación defensiva offline).
- `extraer_texto`: Obtiene el texto generado navegando la respuesta de la API.
- `fetch_api_data`: Fachada integrada con validación de contrato y resiliencia.
"""

import json
from typing import Any, Dict, Optional

import requests

from core.config import AppConfig, config as default_config
from core.http_client import (
    DEFAULT_SYSTEM_INSTRUCTION,
    DEFAULT_USER_MESSAGE,
    HttpClient,
)
from core.simulation import build_simulated_response, is_simulation_mode


class Peticion(tuple):
    """
    Estructura inmutable de petición HTTP.

    Permite acceso por atributo (p.url, p.headers, p.payload), por clave
    (p['url'], p['headers'], p['payload']) y desempaquetado posicional
    (url, headers, payload = p).
    """

    def __new__(cls, url: str, headers: Dict[str, str], payload: Dict[str, Any]):
        return super().__new__(cls, (url, headers, payload))

    @property
    def url(self) -> str:
        return self[0]

    @property
    def headers(self) -> Dict[str, str]:
        return self[1]

    @property
    def payload(self) -> Dict[str, Any]:
        return self[2]

    @property
    def json(self) -> Dict[str, Any]:
        return self[2]

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, int):
            return super().__getitem__(item)
        if item == "url":
            return self[0]
        if item == "headers":
            return self[1]
        if item in ("payload", "json"):
            return self[2]
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default

    def as_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "headers": self.headers,
            "payload": self.payload,
            "json": self.payload,
        }


class RespuestaSimulada:
    """Objeto de respuesta compatible con requests.Response para modo offline."""

    def __init__(self, data: Dict[str, Any], status_code: int = 200, url: str = ""):
        self._data = data
        self.status_code = status_code
        self.url = url
        self.headers = {"Content-Type": "application/json"}
        self.text = json.dumps(data, ensure_ascii=False)

    def json(self) -> Dict[str, Any]:
        return self._data

    def raise_for_status(self) -> None:
        pass

    def __repr__(self) -> str:
        return f"<RespuestaSimulada [{self.status_code}]>"


def armar_peticion(
    prompt: Optional[str] = None,
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
    endpoint: str = "chat/completions",
    forzar_json: bool = True,
    config: Optional[AppConfig] = None,
) -> Peticion:
    """
    Construye y estructura la petición HTTP para la API de IA Generativa.

    Separa el mensaje del sistema del mensaje de usuario en 'messages', configura
    las cabeceras seguras (anti-exfiltración de API Key) y define la salida estructurada.

    Args:
        prompt: Mensaje del usuario (o DEFAULT_USER_MESSAGE si es None).
        system_instruction: Instrucción de sistema (o DEFAULT_SYSTEM_INSTRUCTION).
        model: Nombre del modelo a utilizar.
        endpoint: Endpoint relativo o absoluto.
        forzar_json: Si fuerza salida JSON ({"type": "json_object"}).
        config: Configuración inyectable (por defecto usa la global).

    Returns:
        Objeto Peticion accesible como tupla (url, headers, payload) o diccionario.
    """
    cfg = config or default_config
    effective_prompt = prompt or DEFAULT_USER_MESSAGE
    effective_system = system_instruction or DEFAULT_SYSTEM_INSTRUCTION
    effective_model = model or cfg.model_name

    is_relative = not endpoint.startswith(("http://", "https://"))
    url = f"{cfg.api_base_url}/{endpoint.lstrip('/')}" if is_relative else endpoint

    headers: Dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "ProyectoEntornoVirtual-AI/1.0",
    }
    if cfg.api_key and cfg.is_trusted_url(url, is_relative):
        headers["Authorization"] = f"Bearer {cfg.api_key}"

    payload: Dict[str, Any] = {
        "model": effective_model,
        "messages": [
            {"role": "system", "content": effective_system},
            {"role": "user", "content": effective_prompt},
        ],
    }
    if forzar_json:
        payload["response_format"] = {"type": "json_object"}

    return Peticion(url=url, headers=headers, payload=payload)


def enviar_peticion(
    peticion_or_url: Any = None,
    headers: Optional[Dict[str, str]] = None,
    payload: Optional[Dict[str, Any]] = None,
    method: str = "POST",
    timeout: Optional[float] = None,
    verify_ssl: Optional[bool] = None,
    config: Optional[AppConfig] = None,
) -> Any:
    """
    Envía la petición HTTP construida hacia la API de IA Generativa.

    Acepta un objeto Peticion/dict, o argumentos posicionales (url, headers, payload).
    En modo simulación (clave por defecto en entorno de prueba sin saldo), retorna
    una RespuestaSimulada sin realizar peticiones de red reales.

    Args:
        peticion_or_url: Objeto Peticion, dict o URL string.
        headers: Cabeceras HTTP (si se pasan argumentos posicionales).
        payload: Cuerpo JSON de la petición.
        method: Método HTTP (por defecto POST).
        timeout: Timeout en segundos.
        verify_ssl: Si verifica certificados SSL.
        config: Configuración inyectable.

    Returns:
        Objeto Response de requests (o RespuestaSimulada en modo offline).
    """
    cfg = config or default_config

    if isinstance(peticion_or_url, (tuple, Peticion)) and len(peticion_or_url) >= 3:
        url = peticion_or_url[0]
        req_headers = peticion_or_url[1] if headers is None else headers
        req_payload = peticion_or_url[2] if payload is None else payload
    elif isinstance(peticion_or_url, dict):
        url = peticion_or_url.get("url", f"{cfg.api_base_url}/chat/completions")
        req_headers = peticion_or_url.get("headers", {}) if headers is None else headers
        req_payload = (
            peticion_or_url.get("payload") or peticion_or_url.get("json", {})
        ) if payload is None else payload
    elif isinstance(peticion_or_url, str):
        url = peticion_or_url
        req_headers = headers or {}
        req_payload = payload or {}
    else:
        default_req = armar_peticion(config=cfg)
        url = default_req.url
        req_headers = headers or default_req.headers
        req_payload = payload or default_req.payload

    effective_timeout = timeout if timeout is not None else cfg.timeout_seconds
    effective_verify = verify_ssl if verify_ssl is not None else cfg.ssl_verify

    # Modo simulación offline cuando la clave es un placeholder por defecto
    if is_simulation_mode(cfg, url, effective_timeout):
        user_message = DEFAULT_USER_MESSAGE
        if isinstance(req_payload, dict) and isinstance(req_payload.get("messages"), list):
            for msg in req_payload["messages"]:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    user_message = msg.get("content", user_message)
                    break
        sim_result = build_simulated_response(
            config=cfg,
            url=url,
            user_message=user_message,
            payload=req_payload,
        )
        return RespuestaSimulada(data=sim_result["data"], status_code=200, url=url)

    return requests.request(
        method=method,
        url=url,
        headers=req_headers,
        json=req_payload,
        timeout=effective_timeout,
        verify=effective_verify,
    )


def extraer_texto(respuesta: Any) -> str:
    """
    Extrae el contenido de texto generado desde la respuesta de la API.

    Acepta un objeto Response de requests, una RespuestaSimulada o un diccionario
    con la estructura de OpenAI/Groq (o la devuelta por fetch_api_data).

    Args:
        respuesta: Objeto response o diccionario con la respuesta.

    Returns:
        Cadena con el texto generado por el modelo.
    """
    if hasattr(respuesta, "json"):
        try:
            data = respuesta.json()
        except Exception as err:
            raise ValueError(f"No se pudo decodificar JSON de la respuesta: {err}") from err
    elif isinstance(respuesta, dict):
        data = respuesta
    elif isinstance(respuesta, str):
        try:
            data = json.loads(respuesta)
        except Exception:
            return respuesta
    else:
        raise TypeError(f"Tipo de respuesta no soportado: {type(respuesta).__name__}")

    # Si viene empaquetado en el formato devuelto por fetch_api_data
    if "data" in data and isinstance(data["data"], dict) and "choices" in data["data"]:
        data = data["data"]

    choices = data.get("choices")
    if isinstance(choices, list) and len(choices) > 0:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message")
            if isinstance(message, dict) and "content" in message:
                content = message["content"]
                if isinstance(content, str):
                    return content

    if "structured_output" in data:
        return json.dumps(data["structured_output"], ensure_ascii=False)

    if "text" in data and isinstance(data["text"], str):
        return data["text"]

    raise ValueError("No se pudo extraer texto: la respuesta no contiene 'choices[0].message.content'.")


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
