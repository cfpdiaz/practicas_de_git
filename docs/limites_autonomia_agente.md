# Límites de Autonomía: Agente de Clasificación de Incidentes (pipeline de IA)

Este documento describe los límites de autonomía del agente implementado en este
repositorio (`main.py` + paquete `core/`). El agente consume una API de IA
Generativa y devuelve un JSON estructurado en español; **no mueve dinero ni
modifica datos externos**, por lo que no existe una herramienta de riesgo alto
(escritura irreversible con impacto económico).

## Herramientas y nivel de riesgo

- `armar_peticion`: **bajo** — solo construye URL, cabeceras y payload; no tiene efectos externos.
- `extraer_texto`: **bajo** — solo parsea la respuesta; no tiene efectos externos.
- `obtener_datos_api` / `enviar_peticion` (llamada a la API): **medio** — realiza una petición HTTP a la API de IA; consume cuota (impacto económico), aunque una petición individual no es irreversible.
- `ejecutar_pruebas` / `test_consistencia`: **medio** — escribe `prompts/registro_resultados.json` (escritura **reversible** vía control de versiones).
- `es_url_confiable`, `es_modo_simulacion`, `clasificar_error` y el reintento con backoff: **bajo** — son defensas internas de seguridad/resiliencia; no ejecutan acciones externas.

## Herramientas que requieren aprobación humana

- **Llamada real a la API (`obtener_datos_api` / `enviar_peticion`)**: requiere aprobación humana cuando está activada la opción `REQUIERE_APROBACION=true` (por defecto `false`, para permitir la automatización y la auditoría offline).
  - **Por qué:** es la única acción con impacto económico real (consumo de cuota del proveedor). Por eso es la única candidata a una barrera de confirmación; el resto de las herramientas son de solo lectura o de escritura reversible y no necesitan aprobación.
  - **Cómo:** antes de enviar la petición, `core/api.py` invoca `esperar_aprobacion(...)` (confirmación con límite de tiempo). Si el operador no aprueba, la llamada se cancela y se devuelve el error controlado `AprobacionDenegada`.

## Revisión de trazas

- **Frecuencia:** tras cada ejecución del agente (`python main.py`) y antes de cada entrega. El archivo de trazas es `trazas_agente.jsonl` (artefacto local, ignorado por Git).
- **Qué se busca:**
  - Herramientas invocadas con argumentos inesperados (por ejemplo, un endpoint distinto al esperado).
  - Respuestas con `error_type` inesperados (`RateLimitExceeded` repetido → posible bucle de reintentos/cuota).
  - Cualquier intento de enviar la API Key a un host no confiable (mitigado por `es_url_confiable`, que omite el header `Authorization`).
  - Ejecuciones con `fallback=true` (indican que se activó la simulación offline por agotar reintentos o por falta de red).
  - Respuestas finales que no respeten el contrato (`resumen`, `categoria`, `prioridad`).

## Qué hacer ante un comportamiento inesperado

1. **Detener la ejecución** de la herramienta afectada (forzar `REQUIERE_APROBACION=true` o el modo simulación para cortar el consumo).
2. **Revisar la traza** correspondiente en `trazas_agente.jsonl` para reproducir la entrada, la herramienta y la respuesta.
3. **Revisar el prompt del sistema** (`core/http_client.py` / `prompts/banco.py`): si el modelo devuelve JSON mal formado o claves incorrectas, ajustar la instrucción de sistema o el contrato (`claves_esperadas`).
4. **Ajustar la descripción/contrato** de la tarea en `prompts/banco.py` (claves y valores permitidos).
5. **Re-ejecutar las pruebas** (`pytest -ra`) y el runner de consistencia (`python -m prompts.test_consistencia`) para verificar que el comportamiento vuelve a ser el esperado.
6. Si el problema es de red o cuota, revisar la política de reintentos en `core/resiliencia.py` y el fallback en `core/http_client.py`.
