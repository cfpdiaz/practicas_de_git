# Métricas del Bloque 28 — Latencia y Costo del Flujo RAG

## Descripción

El **Bloque 28** implementa un sistema de **observabilidad** para pipelines
RAG (Retrieval-Augmented Generation) dentro del proyecto `practicas_de_git`.
Mide latencia por etapa y estima el costo económico de cada consulta al LLM.

---

## Arquitectura del módulo `rag/`

```
rag/
├── __init__.py          # Expone medir_etapa y registrar_consulta
└── metricas_rag.py      # Lógica de medición, extracción de tokens y escritura JSONL
```

### Funciones principales

| Función | Rol |
|---|---|
| `medir_etapa(tiempos, nombre)` | Context manager — mide ms con `perf_counter()` |
| `_extraer_tokens_y_costo(resp)` | Extracción defensiva de usage en 3 formatos |
| `registrar_consulta(...)` | Orquesta etapas y persiste en JSONL |

---

## Pipeline RAG medido

```
pregunta
   │
   ▼
[embed_y_busqueda]  → recuperar_documentos(pregunta, k)   ← TF-IDF coseno
   │
   ▼
[generacion]        → generar_respuesta_rag(pregunta, docs) ← armar_peticion + enviar_peticion
   │
   ▼
registrar_consulta() → escribe 1 línea en registros_latencia_costo.jsonl
```

---

## Formato del registro JSONL

Cada línea de `registros_latencia_costo.jsonl` es un objeto JSON con
exactamente **6 claves obligatorias**:

```jsonl
{
  "timestamp": "2026-11-20T04:28:17.374Z",
  "pregunta": "¿Cómo funciona el modo simulación offline?",
  "k": 3,
  "tiempos_ms": {
    "embed_y_busqueda": 0.33,
    "generacion": 0.21
  },
  "tiempo_total_ms": 0.59,
  "tokens": {
    "prompt_tokens": 82,
    "completion_tokens": 36,
    "total_tokens": 118,
    "costo_usd_estimado": 7.682e-05
  }
}
```

> **Formato JSON Lines**: una línea = un objeto JSON válido. Nunca una lista global.

---

## Métricas de ejecución (modo simulación offline)

Resultados obtenidos con `python correr_bloque28.py --offline` sobre 3 consultas:

| # | Etapa | embed_y_busqueda | generacion | tiempo_total_ms | tokens | costo_usd |
|---|---|---|---|---|---|---|
| 1 | simulación | 0.33 ms | 0.21 ms | 0.59 ms | 118 | \$0.00007682 |
| 2 | simulación | 0.29 ms | 0.17 ms | 0.48 ms | 118 | \$0.00007682 |
| 3 | simulación | 0.33 ms | 0.15 ms | 0.50 ms | 118 | \$0.00007682 |
| **Prom.** | | **0.32 ms** | **0.18 ms** | **0.52 ms** | **118** | **\$0.00007682** |

> [!NOTE]
> En modo simulación los tokens son fijos (simulados por `core/simulation.py`):
> `prompt=82`, `completion=36`, `total=118`.

---

## Modelo de costo estimado

Los precios usados corresponden a **openai/gpt-oss-120b** vía Groq:

| Tipo de token | Precio por 1 000 tokens (USD) |
|---|---|
| Prompt (entrada) | \$0.00059 |
| Completion (salida) | \$0.00079 |

**Fórmula:**
```
costo_usd = (prompt_tokens / 1000) × 0.00059
           + (completion_tokens / 1000) × 0.00079
```

> [!TIP]
> Ajusta `_PRECIO_INPUT_POR_1K` y `_PRECIO_OUTPUT_POR_1K` en `rag/metricas_rag.py`
> si cambias de modelo o proveedor.

---

## Extracción defensiva de tokens (`_extraer_tokens_y_costo`)

Soporta tres formatos de respuesta sin lanzar `AttributeError`:

| Prioridad | Formato | Atributo/clave |
|---|---|---|
| 1 | LangChain | `respuesta.usage_metadata` → `input_tokens`, `output_tokens` |
| 2 | `requests.Response` / `RespuestaSimulada` | `.json()["usage"]` → `prompt_tokens`, `completion_tokens` |
| 3 | Dict de `obtener_datos_api` | `data["data"]["usage"]` → mismas claves |

Si ninguno aplica → retorna `None` (el campo `tokens` del registro queda `null`).

---

## Scripts del Bloque 28

### `correr_bloque28.py`

```bash
# Modo simulación (sin API Key real)
python correr_bloque28.py --offline

# Cambiar k y archivo de salida
python correr_bloque28.py --offline --k 5 --output mi_registro.jsonl

# Con API Key real (configurada en .env)
python correr_bloque28.py
```

### `leer_registros.py`

```bash
# Verificar y mostrar resumen del JSONL por defecto
python leer_registros.py

# Verificar un archivo personalizado
python leer_registros.py --archivo ruta/registro.jsonl
```

Valida: ≥ 3 líneas válidas + 6 claves obligatorias por línea.

---

## Tests (`test_metricas_rag.py`)

Suite con **28 pruebas unitarias** que cubren:

- `medir_etapa`: 7 tests (registro ms, redondeo, bloques anidados, excepciones)
- `_extraer_tokens_y_costo`: 9 tests (5 formatos + None defensivo + fórmula de costo)
- `_buscar_usage_en_dict`: 4 tests (formatos directo, anidado, vacío)
- `registrar_consulta`: 13 tests (escritura, append, 6 claves, timestamp, mkdir)

```bash
pytest test_metricas_rag.py -v
```

---

## Integración con `core/`

El Bloque 28 se integra con la arquitectura existente sin modificar ningún
archivo del paquete `core/`:

```
correr_bloque28.py
   ├── from core.api import armar_peticion, enviar_peticion, extraer_texto
   ├── from core.config import ConfiguracionApp, cargar_configuracion
   ├── from core.simulation import es_modo_simulacion   (detección offline)
   └── from rag.metricas_rag import registrar_consulta
```

> [!IMPORTANT]
> El modo simulación se activa automáticamente cuando `API_KEY` en `.env` usa
> el valor placeholder `tu_groq_api_key_aqui` o cuando se pasa `--offline`.
> No se realizan llamadas reales ni se consume cuota.
