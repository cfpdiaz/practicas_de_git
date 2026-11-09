# Interpretación y Límites del Pipeline (Bloque 17)

**Fecha de la evidencia:** 2026-11-09
**Modelo:** `openai/gpt-oss-120b` (Groq)
**Runner:** `python -m prompts.test_consistencia`
**Resultado:** 9/9 ejecuciones válidas (100.0%) — `meta_3_de_3_cumplida: true`

---

## 1. Análisis Cualitativo

Se ejecutaron 3 iteraciones por cada uno de los 3 prompts del banco (9 llamadas reales). Todas las respuestas cumplieron el contrato JSON estructurado en español:

| Prompt | Claves esperadas | Resultado | Observación |
|---|---|---|---|
| `clasificar_incidente` | `resumen`, `categoria`, `prioridad` | 3/3 (100%) | `prioridad` siempre `"alta"`; `categoria` varía entre `"rendimiento de base de datos"`, `"Base de datos"` y `"rendimiento"` |
| `analisis_sentimiento_soporte` | `resumen`, `sentimiento`, `urgencia` | 3/3 (100%) | `sentimiento` `"negativo"` y `urgencia` `"alta"` en las 3 iteraciones |
| `extraccion_entidades_logistica` | `numero_pedido`, `destino`, `estado_envio` | 3/3 (100%) | `numero_pedido` `"ORD-98234"`, `destino` `"Valparaíso"`, `estado_envio` `"en_transito"` en las 3 iteraciones |

### Cumplimiento del formato
- **JSON válido:** las 9 respuestas son objetos JSON parseables, sin texto adicional ni bloques Markdown.
- **Claves obligatorias:** las 9 respuestas contienen todas las claves del contrato.
- **Valores permitidos:** se respetan los enums (`prioridad`: alta/media/baja; `sentimiento`: positivo/neutral/negativo; `urgencia`: alta/media/baja; `estado_envio`: pendiente/en_transito/entregado).
- **Idioma:** resúmenes y categorías en español, coherentes con la instrucción del sistema.

### Variabilidad observada
- Los campos de texto libre (`resumen`, `categoria`) presentan variaciones de redacción entre iteraciones, pero **la estructura y la clasificación se mantienen estables** (prioridad, sentimiento, urgencia y estado no cambian).
- No se detectaron casos de JSON inválido, claves faltantes ni valores fuera de los enums.

---

## 2. Límites Técnicos del Pipeline

### 2.1 Latencia de la red de inferencia
- Cada llamada espera la inferencia del proveedor (aprox. 0.5–2 s por petición en Groq). El runner hace 9 llamadas secuenciales, por lo que la latencia se acumula (~10–20 s en total).
- El pipeline aplica `API_TIMEOUT` (10 s por defecto) y reporta `Timeout` como error estructurado, pero **no reintenta automáticamente**.

### 2.2 Sensibilidad al formateo del prompt del sistema
- La instrucción del sistema es estricta ("responde EXCLUSIVAMENTE con un objeto JSON…") y se refuerza con `response_format: {"type": "json_object"}`.
- Si se modifica el formato del prompt (instrucciones extra, ejemplos, Markdown, cambios de idioma), el modelo podría devolver texto fuera del JSON o claves distintas. La validación de contrato (`validar_respuesta_api`) detecta JSON inválido o claves faltantes, pero **no desviaciones semánticas** (por ejemplo, una `categoria` vacía o poco precisa).

### 2.3 Gestión de cuotas de tasa (HTTP 429)
- Un HTTP 429 se clasifica como `RateLimitExceeded` y expone `Retry-After`.
- El pipeline **no reintenta**: la política de espera queda en manos del llamador. En planes gratuitos, una ráfaga de 9 llamadas puede agotar la cuota y cortar la ejecución.

### 2.4 Comportamiento en modo simulación offline
- Con una API Key placeholder o ausente, `es_modo_simulacion` devuelve respuestas simuladas deterministas y **sin red**.
- Ventajas: tests/auditoría reproducibles sin cuota.
- Límites: la simulación no refleja la variabilidad real del modelo ni los fallos de red; por construcción siempre cumple el contrato, así que **no valida el comportamiento real** del proveedor.

---

## 3. Recomendaciones de Mitigación

### 3.1 Reintentos con backoff exponencial
- Envolver la llamada HTTP en un reintento que respete `Retry-After` y use backoff exponencial con jitter para 429, 5xx y timeouts transitorios (por ejemplo con `tenacity` o un bucle propio).
- Limitar el número de intentos y exponer el resultado final en el JSON de error.

### 3.2 Validación previa con esquema en `app.py`
- Validar la petición (payload/mensajes) y la respuesta con un esquema formal (por ejemplo `jsonschema` o un modelo `pydantic`) antes de continuar el pipeline.
- Esto permite rechazar entradas mal formadas antes de consumir cuota y detectar respuestas fuera de contrato con mensajes de error precisos.

### 3.3 Mocks en entorno de prueba
- Mantener la suite de `pytest` con `unittest.mock` (`patch`) para probar éxito y excepciones sin red ni API Key.
- Añadir pruebas específicas para la política de reintentos y para la validación de esquema, de modo que CI sea determinista y no dependa de cuotas.

---

## 4. Conclusión

El pipeline cumple el contrato JSON en **9/9 ejecuciones reales (100%)**. Los riesgos principales son la **latencia**, la **sensibilidad al prompt del sistema** y el **límite de cuota (HTTP 429)**. Las mitigaciones propuestas (reintentos con backoff, validación con esquema y mocks) reducen el impacto sin cambiar el contrato de salida.
