"""
core.resiliencia - Tolerancia a fallos del pipeline de IA.

Provee la clasificación de errores, el cálculo del backoff exponencial y el
bucle de reintentos que el cliente HTTP utiliza para absorber fallos
transitorios (Timeout, HTTP 429, HTTP 500/503) antes de caer al modo de
contingencia offline.

Ver ``docs/tolerancia_fallos.md`` para la política completa.
"""

import time
from typing import Any, Callable, Dict

# Parámetros de la política de reintentos (ver docs/tolerancia_fallos.md)
MAX_REINTENTOS = 3
RETRASO_INICIAL = 2.0
FACTOR_BACKOFF = 2.0

# Códigos HTTP que se consideran transitorios (reintentables)
ESTADOS_REINTENTABLES = frozenset({429, 500, 503})
# Códigos HTTP que no deben reintentarse (credenciales, modelo inexistente...)
ESTADOS_FATALES = frozenset({401, 403, 404})


def clasificar_error(resultado: Dict[str, Any]) -> str:
    """
    Clasifica un resultado de la petición para decidir la estrategia.

    Returns:
        "ok"            -> petición correcta.
        "reintentable"  -> Timeout, RateLimitExceeded o HTTP 500/503.
        "fatal"         -> HTTP 401/403/404 (credenciales o modelo inexistente).
        "estructura"    -> JSONDecodeError / SchemaValidationError.
        "red"           -> ConnectionError (sin conexión).
    """
    if resultado.get("success"):
        return "ok"

    tipo = resultado.get("error_type")
    estado = resultado.get("status_code")

    if tipo in ("Timeout", "RateLimitExceeded"):
        return "reintentable"

    if tipo == "HTTPError":
        return "reintentable" if estado in ESTADOS_REINTENTABLES else "fatal"

    if tipo in ("JSONDecodeError", "SchemaValidationError"):
        return "estructura"

    if tipo == "ConnectionError":
        return "red"

    return "fatal"


def calcular_espera(
    intento: int,
    retraso_inicial: float = RETRASO_INICIAL,
    factor: float = FACTOR_BACKOFF,
) -> float:
    """
    Calcula la espera exponencial del reintento ``intento``.

    Con los valores por defecto: intento 1 -> 2s, 2 -> 4s, 3 -> 8s.
    """
    return retraso_inicial * (factor ** (intento - 1))


def ejecutar_con_reintentos(
    accion: Callable[[], Dict[str, Any]],
    dormir: Callable[[float], None] = time.sleep,
    max_reintentos: int = MAX_REINTENTOS,
    retraso_inicial: float = RETRASO_INICIAL,
    factor: float = FACTOR_BACKOFF,
) -> Dict[str, Any]:
    """
    Ejecuta ``accion`` reintentando los errores transitorios con backoff.

    Args:
        accion: función sin argumentos que devuelve un dict de resultado.
        dormir: función de espera (inyectable en pruebas para no esperar).
        max_reintentos: número máximo de reintentos (además del intento inicial).
        retraso_inicial: espera base en segundos.
        factor: multiplicador del backoff.

    Returns:
        El último resultado obtenido (éxito o error).

    Nota:
        Los errores fatales, de estructura o de red no se reintentan: se
        devuelven inmediatamente para que el llamador aplique el fallback.
    """
    resultado = accion()
    intento = 0

    while clasificar_error(resultado) == "reintentable" and intento < max_reintentos:
        intento += 1
        dormir(calcular_espera(intento, retraso_inicial, factor))
        resultado = accion()

    return resultado
