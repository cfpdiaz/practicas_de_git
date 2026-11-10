# Estrategia de Tolerancia a Fallos y Resiliencia (Bloque 20)

Este documento detalla los mecanismos de resiliencia, clasificación de excepciones, políticas de reintento y respuestas de contingencia (*fallbacks*) implementados en el pipeline de IA.

## 1. Clasificación de Excepciones y Estrategia de Respuesta

| Categoría de Error | Códigos HTTP / Excepciones | Estrategia de Mitigación | Comportamiento del Sistema |
|---|---|---|---|
| **Error Reintentable (Transitorio)** | `HTTP 429 RateLimitExceeded`, `Timeout`, `HTTP 500/503` | **Reintento con Backoff Exponencial** | Pausa la ejecución e intenta nuevamente hasta `MAX_REINTENTOS=3`. |
| **Error Fatal (No Reintentable)** | `HTTP 401/403` (Credenciales), `HTTP 404` (Modelo) | **Fallo Inmediato Controlado** | Detiene peticiones y retorna mensaje descriptivo de autenticación/disponibilidad. |
| **Error de Estructura / Formato** | `JSONDecodeError`, `SchemaValidationError` | **Captura y Fallback** | Encapsula el error en respuesta JSON y activa esquema o modo simulación. |
| **Fallo Total de Red / Sin Conexión** | `ConnectionError` | **Modo Contingencia / Offline** | Activa el motor de simulación local sin colapsar la app. |

La clasificación vive en `core/resiliencia.py` (`clasificar_error`) y se aplica en el cliente HTTP (`core/http_client.py`).

## 2. Parámetros de Reintentos y Exponential Backoff

- **Número máximo de intentos (`MAX_REINTENTOS`):** `3`
- **Tiempo base de espera (`RETRASO_INICIAL`):** `2.0` segundos
- **Factor de multiplicación (`FACTOR_BACKOFF`):** `2.0` (delays: 2s, 4s, 8s)

Los parámetros se definen en `core/resiliencia.py` y los aplica el bucle `ejecutar_con_reintentos`, que acepta una función `dormir` inyectable para que las pruebas no esperen los delays reales.

## 3. Mecanismo de Conmutación (Fallback)

- **En LangChain (`agente.py`):** este proyecto **no usa LangChain** (dependencias: `requests` + `python-dotenv`), por lo que no existe `agente.py` ni `.with_fallbacks()`. El equivalente funcional se implementa en el cliente HTTP propio.
- **En el cliente HTTP REST (`app.py` / `core/http_client.py`):** si se agotan los reintentos de un error transitorio o falla la red (`ConnectionError`), se activa el **modo de simulación offline** (`core/simulation.py`) y se devuelve una respuesta degradada con `fallback: true`, `error_original` y el `structured_output` simulado. Así el pipeline no colapsa y la aplicación sigue siendo ejecutable.
- El modo simulación también se activa de forma defensiva cuando la API Key es un placeholder (`es_modo_simulacion`).

## 4. Pruebas de Verificación

Los escenarios de error son validados mediante la suite de pruebas unitarias (`pytest`) con `unittest.mock` para simular respuestas HTTP 429, Timeouts y respuestas no válidas de forma 100% aislada:

- `test_app.py` (6 pruebas): éxito 200, `Timeout`, `HTTPError 429`, `JSONDecodeError`, `ConnectionError` y `SchemaValidationError`.
- `test_core.py` → `TestResiliencia`: clasificación de errores (`reintentable`, `fatal`, `estructura`, `red`), cálculo del backoff (2s, 4s, 8s), reintentos con espera inyectada, fallback simulado al agotar reintentos y verificación de que un error fatal (401) no se reintenta ni activa fallback.

> Nota: las pruebas inyectan una función `dormir` falsa (`esperas.append`) para no esperar los delays reales y mantener la suite rápida y determinista.
