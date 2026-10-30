"""
core.api - API pública de alto nivel y funciones de consumo.

Provee las funciones requeridas por la rúbrica del curso:
- `armar_peticion`: Construye cabeceras, URL y cuerpo JSON (separando roles system/user).
- `enviar_peticion`: Realiza la llamada HTTP (o simulación defensiva offline).
- `extraer_texto`: Obtiene el texto generado navegando la respuesta de la API.
- `obtener_datos_api`: Fachada integrada con validación de contrato y resiliencia.
"""

import json
from typing import Any, Dict, Optional

import requests

from core.config import ConfiguracionApp, config as default_config
from core.http_client import (
    INSTRUCCION_SISTEMA_POR_DEFECTO,
    MENSAJE_USUARIO_POR_DEFECTO,
    ClienteHttp,
)
from core.simulation import construir_respuesta_simulada, es_modo_simulacion


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

    def como_diccionario(self) -> Dict[str, Any]:
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
    instruccion_sistema: Optional[str] = None,
    model: Optional[str] = None,
    endpoint: str = "chat/completions",
    forzar_json: bool = True,
    config: Optional[ConfiguracionApp] = None,
) -> Peticion:
    """
    Construye y estructura la petición HTTP para la API de IA Generativa.

    Separa el mensaje del sistema del mensaje de usuario en 'messages', configura
    las cabeceras seguras (anti-exfiltración de API Key) y define la salida estructurada.

    Args:
        prompt: Mensaje del usuario (o MENSAJE_USUARIO_POR_DEFECTO si es None).
        instruccion_sistema: Instrucción de sistema (o INSTRUCCION_SISTEMA_POR_DEFECTO).
        model: Nombre del modelo a utilizar.
        endpoint: Endpoint relativo o absoluto.
        forzar_json: Si fuerza salida JSON ({"type": "json_object"}).
        config: Configuración inyectable (por defecto usa la global).

    Returns:
        Objeto Peticion accesible como tupla (url, headers, payload) o diccionario.
    """
    cfg = config or default_config
    prompt_efectivo = prompt or MENSAJE_USUARIO_POR_DEFECTO
    sistema_efectivo = instruccion_sistema or INSTRUCCION_SISTEMA_POR_DEFECTO
    modelo_efectivo = model or cfg.nombre_modelo

    es_relativa = not endpoint.startswith(("http://", "https://"))
    url = f"{cfg.url_base_api}/{endpoint.lstrip('/')}" if es_relativa else endpoint

    headers: Dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "ProyectoEntornoVirtual-AI/1.0",
    }
    if cfg.clave_api and cfg.es_url_confiable(url, es_relativa):
        headers["Authorization"] = f"Bearer {cfg.clave_api}"

    payload: Dict[str, Any] = {
        "model": modelo_efectivo,
        "messages": [
            {"role": "system", "content": sistema_efectivo},
            {"role": "user", "content": prompt_efectivo},
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
    verificar_ssl: Optional[bool] = None,
    config: Optional[ConfiguracionApp] = None,
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
        verificar_ssl: Si verifica certificados SSL.
        config: Configuración inyectable.

    Returns:
        Objeto Response de requests (o RespuestaSimulada en modo offline).
    """
    cfg = config or default_config

    if isinstance(peticion_or_url, (tuple, Peticion)) and len(peticion_or_url) >= 3:
        url = peticion_or_url[0]
        cabeceras_peticion = peticion_or_url[1] if headers is None else headers
        payload_peticion = peticion_or_url[2] if payload is None else payload
    elif isinstance(peticion_or_url, dict):
        url = peticion_or_url.get("url", f"{cfg.url_base_api}/chat/completions")
        cabeceras_peticion = peticion_or_url.get("headers", {}) if headers is None else headers
        payload_peticion = (
            peticion_or_url.get("payload") or peticion_or_url.get("json", {})
        ) if payload is None else payload
    elif isinstance(peticion_or_url, str):
        url = peticion_or_url
        cabeceras_peticion = headers or {}
        payload_peticion = payload or {}
    else:
        peticion_defecto = armar_peticion(config=cfg)
        url = peticion_defecto.url
        cabeceras_peticion = headers or peticion_defecto.headers
        payload_peticion = payload or peticion_defecto.payload

    timeout_efectivo = timeout if timeout is not None else cfg.segundos_timeout
    verificacion_efectiva = verificar_ssl if verificar_ssl is not None else cfg.verificar_ssl

    # Modo simulación offline cuando la clave es un placeholder por defecto
    if es_modo_simulacion(cfg, url, timeout_efectivo):
        mensaje_usuario = MENSAJE_USUARIO_POR_DEFECTO
        if isinstance(payload_peticion, dict) and isinstance(payload_peticion.get("messages"), list):
            for msg in payload_peticion["messages"]:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    mensaje_usuario = msg.get("content", mensaje_usuario)
                    break
        sim_result = construir_respuesta_simulada(
            config=cfg,
            url=url,
            mensaje_usuario=mensaje_usuario,
            payload=payload_peticion,
        )
        return RespuestaSimulada(data=sim_result["data"], status_code=200, url=url)

    return requests.request(
        method=method,
        url=url,
        headers=cabeceras_peticion,
        json=payload_peticion,
        timeout=timeout_efectivo,
        verify=verificacion_efectiva,
    )


def extraer_texto(respuesta: Any) -> str:
    """
    Extrae el contenido de texto generado desde la respuesta de la API.

    Acepta un objeto Response de requests, una RespuestaSimulada o un diccionario
    con la estructura de OpenAI/Groq (o la devuelta por obtener_datos_api).

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

    # Si viene empaquetado en el formato devuelto por obtener_datos_api
    if "data" in data and isinstance(data["data"], dict) and "choices" in data["data"]:
        data = data["data"]

    choices = data.get("choices")
    if isinstance(choices, list) and len(choices) > 0:
        primera_opcion = choices[0]
        if isinstance(primera_opcion, dict):
            message = primera_opcion.get("message")
            if isinstance(message, dict) and "content" in message:
                content = message["content"]
                if isinstance(content, str):
                    return content

    if "structured_output" in data:
        return json.dumps(data["structured_output"], ensure_ascii=False)

    if "text" in data and isinstance(data["text"], str):
        return data["text"]

    raise ValueError("No se pudo extraer texto: la respuesta no contiene 'choices[0].message.content'.")


def obtener_datos_api(
    endpoint: str = "chat/completions",
    method: str = "POST",
    prompt: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
    verificar_ssl: Optional[bool] = None,
    instruccion_sistema: Optional[str] = None,
    claves_requeridas: Optional[set[str]] = None,
    config: Optional[ConfiguracionApp] = None,
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
        verificar_ssl: Verificar certificado SSL.
        instruccion_sistema: Instrucción de sistema personalizada.
        claves_requeridas: Claves requeridas para validación del contrato.
        config: Configuración inyectable (por defecto usa la global).

    Returns:
        Dict con respuesta estructurada.
    """
    cfg = config or default_config

    timeout_efectivo = timeout if timeout is not None else cfg.segundos_timeout
    es_relativa = not endpoint.startswith(("http://", "https://"))
    url = f"{cfg.url_base_api}/{endpoint.lstrip('/')}" if es_relativa else endpoint
    mensaje_usuario = prompt or MENSAJE_USUARIO_POR_DEFECTO

    # Modo simulación offline cuando la clave es un placeholder por defecto
    if es_modo_simulacion(cfg, url, timeout_efectivo):
        return construir_respuesta_simulada(
            config=cfg,
            url=url,
            mensaje_usuario=mensaje_usuario,
            instruccion_sistema=instruccion_sistema,
            claves_requeridas=claves_requeridas,
            payload=payload,
        )

    return ClienteHttp(cfg).enviar(
        endpoint=endpoint,
        method=method,
        prompt=prompt,
        params=params,
        payload=payload,
        timeout=timeout,
        verificar_ssl=verificar_ssl,
        instruccion_sistema=instruccion_sistema,
        claves_requeridas=claves_requeridas,
    )
