# Límites de Autonomía: Agente de Clasificación de Incidentes (pipeline de IA)

Este documento describe los límites de autonomía del agente implementado en este
repositorio (`main.py` + paquete `core/`). La **matriz de autonomía** está definida
en código en `core/autonomia.py` (`MATRIZ_AUTONOMIA`) y se aplica antes de ejecutar
cualquier acción mediante la barrera única `ejecutar_con_autonomia`.

## Matriz de autonomía (definida en código)

| Nivel | Criterio | Acciones del proyecto |
|---|---|---|
| **Bajo (ejecución directa)** | Lectura de datos, formateo de texto, consultas a la API de solo lectura | `armar_peticion`, `enviar_peticion`, `extraer_texto`, `obtener_datos_api`, `validar_respuesta_api`, `construir_respuesta_simulada`, `construir_definiciones_tareas` |
| **Medio (registro en trazas)** | Modificación de variables locales de estado o de la memoria de contexto | `registrar_traza` (escribe la traza/contexto del agente) |
| **Alto (requiere aprobación)** | Eliminación de archivos, llamadas a servicios externos destructivos, cambios persistentes | `ejecutar_pruebas`, `test_consistencia` (escriben `prompts/registro_resultados.json`, un cambio persistente) |

> Las acciones no listadas se tratan como **ALTO** por defecto (conservador).

## Herramientas y nivel de riesgo (detalle)

- `armar_peticion`, `extraer_texto`: **bajo** — construyen/parsean sin efectos externos.
- `obtener_datos_api`, `enviar_peticion`: **bajo** — consulta de solo lectura a la API.
- `validar_respuesta_api`, `construir_respuesta_simulada`, `construir_definiciones_tareas`: **bajo** — lectura/validación/formateo.
- `registrar_traza`: **medio** — modifica el estado local (escribe la traza); queda registrada en trazas.
- `ejecutar_pruebas`, `test_consistencia`: **alto** — cambio persistente (`prompts/registro_resultados.json`); requieren aprobación.

## Herramientas que requieren aprobación humana

- **`ejecutar_pruebas` / `test_consistencia` (riesgo ALTO):** antes de ejecutarlas, `ejecutar_con_autonomia` invoca `esperar_aprobacion(...)`. Si el operador no aprueba, se devuelve `AprobacionDenegada` y la acción **no** se ejecuta. **Por qué:** escriben un archivo persistente en el repositorio.
- **Llamada real a la API (`obtener_datos_api` / `enviar_peticion`):** es de riesgo **bajo** por defecto (consulta de solo lectura), pero conserva una **sobreprotección opcional** (`REQUIERE_APROBACION=true` en el entorno) para auditorías estrictas o para no gastar cuota sin supervisión.

## Revisión de trazas

- **Frecuencia:** tras cada ejecución del agente (`python main.py`) y antes de cada entrega. El archivo de trazas es `trazas_agente.jsonl` (artefacto local, ignorado por Git).
- **Qué se registra (auditoría):** `ejecutar_con_autonomia` escribe una línea por cada acción ejecutada (con su `nivel_riesgo` y resultado) y, para las acciones de riesgo ALTO, una línea adicional con `resultado_aprobacion` (`aprobada`/`denegada`). Así cada decisión, llamada a herramienta y resultado de aprobación queda auditado.
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
