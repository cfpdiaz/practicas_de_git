# Decisión de personalización

**Fecha:** 2026-11-20
**Proyecto:** `practicas_de_git` (Gate 1) — pipeline de IA Generativa sobre Groq
**Modelo base:** `openai/gpt-oss-120b` (endpoint `/chat/completions`)
**Estado:** Propuesta fundamentada (Bloque 30)

Este documento aplica el método de decisión de la Unidad 2.6 a un caso candidato
real del proyecto y resuelve, con criterio de ingeniería, la estrategia de
personalización del modelo para imponer un comportamiento y un formato de salida
consistentes a bajo costo.

---

## 1. El problema

El pipeline hoy codifica el contrato JSON **dentro del prompt de sistema** en
cada consulta. En `prompts/banco.py` (`BANCO_DE_PROMPTS`) cada tarea repite una
instrucción de sistema extensa que especifica, a mano, el esquema exacto y el
tono:

| Tarea (`BANCO_DE_PROMPTS`) | Contrato de salida |
|---|---|
| `clasificar_incidente` | `resumen`, `categoria`, `prioridad` (`alta\|media\|baja`) |
| `analisis_sentimiento_soporte` | `resumen`, `sentimiento`, `urgencia` |
| `extraccion_entidades_logistica` | `numero_pedido`, `destino`, `estado_envio` |

El contrato se valida en `core/schemas.py` (`validar_respuesta_api`,
`CLAVES_REQUERIDAS = {"resumen", "categoria", "prioridad"}` y
`PRIORIDADES_PERMITIDAS = {"alta", "media", "baja"}`), y la batería
`prompts/test_consistencia.py` certifica hoy un **9/9 (100 %)** de cumplimiento.
Sin embargo, ese cumplimiento se consigue a costa de **repetir el esquema JSON y
las reglas de tono en cada request**.

**Caso candidato (Bloque 29):** escalar el sistema de clasificación y extracción
a **nuevos dominios** (p. ej. `extraccion_entidades_financieras`,
`clasificacion_tickets_legales`, `resumen_ordenes_medicas`) manteniendo:

1. **Formato JSON estricto** (claves y enums idénticos a los que hoy valida `core/schemas.py`).
2. **Tono técnico uniforme** (sin explicaciones, sin markdown, sin texto fuera del JSON).
3. **Menor sobrecarga de tokens de sistema por consulta** (hoy ~82 tokens de *prompt* por consulta, medidos en el Bloque 28).

Este problema es **distinto** de la consulta de **documentación técnica que cambia
con frecuencia**, que ya cubre el flujo **RAG** del Bloque 28 (`rag/metricas_rag.py`,
`registros_latencia_costo.jsonl`): aquí lo que se quiere fijar es el
**comportamiento y el esquema de salida**, no inyectar conocimiento volátil.

---

## 2. Resultado del método de decisión

Se evalúan las 4 técnicas de la Unidad 2.6 sobre **5 criterios** (escala 0–5,
mayor = mejor):

| Criterio | Fine-tuning completo | PEFT (LoRA) | RAG | Soft-prompting |
|---|---|---|---|---|
| Consistencia de formato/comportamiento JSON | 5 | 5 | 2 | 2 |
| Reducción de tokens de sistema por consulta | 5 | 5 | 1 | 3 |
| Bajo costo de infraestructura / despliegue | 3 | 5 | 3 | 4 |
| Bajo costo de datos (curaduría + revisión) | 3 | 4 | 5 | 2 |
| Mantenibilidad del conocimiento (cambia seguido) | 2 | 2 | 5 | 3 |
| **Total (25)** | **18** | **21** | **16** | **14** |

**Lista de puntajes:**

- `Fine-tuning completo`: **18 puntos**
- `PEFT`: **21 puntos**
- `RAG`: **16 puntos**
- `Soft-prompting`: **14 puntos**

### El empate que hay que resolver

`Fine-tuning completo` y `PEFT` **empatan 5/5 en el criterio determinante**
(*consistencia de formato/comportamiento*) y en *reducción de tokens de sistema*.
Son los dos únicos finalistas capaces de **imponer el formato desde dentro del
modelo**, porque ambos modifican los pesos (o un adaptador de pesos) para que el
JSON y el tono salgan "de fábrica", eliminando la instrucción de sistema extensa.
La diferencia de 3 puntos del total proviene **exclusivamente de los costos**
(infraestructura y datos), y es lo que se desempata en la Sección 3.

### Por qué RAG puntúa bajo para este problema

RAG **inyecta contexto** en el prompt en lugar de cambiar el comportamiento del
modelo: recupera documentos (`rag/metricas_rag.py`, recuperación TF-IDF con `k=3`)
y los antepone a la consulta. Para imponer un formato JSON estricto, RAG
**aumenta** el prompt (más tokens, no menos) y además **no garantiza** que el
modelo respete el esquema: seguiría dependiendo de la instrucción de sistema
larga que se quiere eliminar. Por eso obtiene 2 en *consistencia de formato* y 1
en *reducción de tokens*. Su fortaleza (5 en *mantenibilidad*) está en el
conocimiento **cambiante**, no en el **comportamiento**.

### Por qué Soft-prompting no aplica

El *soft-prompting* (tuning de *soft tokens* prefijados) requiere **acceso al
gradiente/embeddings** del modelo para optimizar los vectores del prefijo. En una
**API gestionada** como Groq (`/chat/completions`) solo se expone inferencia: no
se puede tunear el prefijo ni subir *soft prompts* entrenados. Por tanto no es
aplicable aquí (consistencia 2, y descartado por viabilidad).

---

## 3. Técnica elegida y por qué

**Elección: PEFT (LoRA)** — un *adapter* entrenado sobre `openai/gpt-oss-120b`.

El empate de la Sección 2 se desempata con las **3 dimensiones de costo real**
del Bloque 30:

### 3.1 Costo de datos (trabajo humano)

La curaduría y el etiquetado exacto de pares `entrada → JSON válido` **no aparece
en la factura de la API**, pero domina el esfuerzo inicial. `PEFT` (LoRA) congela
los pesos base y entrena solo una fracción pequeña de parámetros
(~0.1–1 %), por lo que **aprende el formato con menos ejemplos** que el
*fine-tuning completo* (que actualiza todos los pesos y exige más volumen para no
olvidar capacidades previas). Resultado: con PEFT el mismo dataset rinde más.

### 3.2 Costo de infraestructura

- **RAG** exige mantener un *vector store* activo, respaldado, con embeddings
  generados y **reindexado** ante cada cambio de documentos — infraestructura
  extra y operación continua.
- **Fine-tuning completo** implica servir un *checkpoint* completo de 120B de
  parámetros (GPU pesada y más memoria).
- **PEFT** se sirve **desde el mismo endpoint `/chat/completions`** que ya usa el
  proyecto (`core/http_client.py`, `core/api.py`), con el *adapter* como un
  pequeño artefacto acoplado al modelo base. **Cero servidores adicionales.**

### 3.3 Costo de tiempo y cómputo

El prompt largo se mide en `docs/metricas_bloque28.md` /
`registros_latencia_costo.jsonl`: **82 tokens de prompt**, **36 de completion**
(**118 total**) y **\$0.00007682 USD por consulta** (tarifas: \$0.00059/1k de
prompt y \$0.00079/1k de completion). A 10.000 consultas son **1,18 M de tokens**
y **\$0.77 USD**; buena parte de esos 82 tokens de prompt es la instrucción de
sistema que repite el esquema.

Con PEFT, el modelo **internaliza el esquema**, el prompt de sistema se reduce a
una orden mínima y se recorta la fracción de tokens de prompt por consulta. El
entrenamiento LoRA de un adaptador es de **minutos a pocas horas en una sola
GPU**, frente al *fine-tuning completo* de un modelo de 120B que requiere un
clúster de GPUs y días. Es decir: **la misma consistencia de comportamiento a una
fracción del costo de cómputo**.

### Nota sobre la arquitectura óptima en producción

La combinación ganadora es **híbrida**:

- **PEFT** para el **comportamiento y el esquema de salida consistente**
  (el problema de esta decisión).
- **RAG** para la **documentación técnica que cambia** (el flujo ya implementado
  del Bloque 28).

### Descartados explícitamente

- **Fine-tuning completo:** misma consistencia que PEFT, pero mucho mayor costo
  de cómputo e infraestructura (checkpoint completo de 120B). No aporta ventaja
  funcional para imponer formato.
- **RAG solo:** no impone formato sin inflar el prompt; es complementario, no
  sustituto.
- **Soft-prompting:** inviable en API gestionada (sin acceso a embeddings).

---

## 4. Qué necesitarías para ejecutarla

Antes de entrenar el *adapter* se requieren estos insumos concretos:

### 4.1 Dataset mínimo curado

- **300 a 500 ejemplos reales** de entrada y salida JSON válida, generados a
  partir de `BANCO_DE_PROMPTS` (y extendidos a los nuevos dominios del caso).
- Cada ejemplo: `{"entrada": "...", "salida": {"clave": "valor", ...}}` con las
  claves y enums de `core/schemas.py`.
- **Estimación de etiquetado:** ~5 min por ejemplo ⇒ **25–42 horas** de curaduría
  para 300–500 ejemplos.
- **Doble revisión del 20 %** (60–100 ejemplos revisados por una segunda persona)
  ⇒ **~2–4 horas adicionales**, para detectar sesgos o enums mal escritos.

### 4.2 Script de validación automática previa al entrenamiento

Un *check* de pre-entrenamiento que garantice que **el 100 % de los ejemplos**:

1. Cumplen el contrato de `core/schemas.py` (`validar_respuesta_api` /
   `CLAVES_REQUERIDAS` / `PRIORIDADES_PERMITIDAS`): JSON válido, claves
   requeridas y enums permitidos.
2. No exceden el límite de tokens (para **evitar truncado silencioso** de la
   salida de ejemplo, que envenenaría el entrenamiento).

### 4.3 Evaluación comparativa contra la línea base actual

- **Consistencia de comportamiento:** re-correr `prompts/test_consistencia.py`
  (línea base actual **9/9**) y comparar contra el modelo ajustado con PEFT.
- **Latencia y costo:** reusar `rag/metricas_rag.py` y
  `registros_latencia_costo.jsonl` del Bloque 28 para demostrar la reducción de
  *prompt tokens* por consulta (hoy 82) y el costo resultante por consulta
  (hoy \$0.00007682 USD).
