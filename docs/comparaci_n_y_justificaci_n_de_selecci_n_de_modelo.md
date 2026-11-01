# Comparación, Justificación y Selección de Modelo de IA

Este documento detalla el análisis comparativo de rendimiento, costos y viabilidad técnica de los modelos evaluados en la plataforma Groq Cloud para la miniaplicación del proyecto.

---

## 3. Comparación de candidatos

A continuación se consolida la evaluación comparativa realizada con datos reales del proveedor y pruebas de ejecución en vivo:

| Métrica / Criterio | Candidato A: `openai/gpt-oss-120b` (Elegido) | Candidato B: `llama-3.3-70b-versatile` (Descartado) |
|---|---|---|
| **Proveedor / Endpoint** | Groq Cloud (`/v1/chat/completions`) | Groq Cloud (`/v1/chat/completions`) |
| **Costo Entrada (por 1M tokens)** | ~$0.15 USD | ~$0.59 USD |
| **Costo Salida (por 1M tokens)** | ~$0.60 USD | ~$0.79 USD |
| **Ventana de Contexto** | 128,000 tokens | 128,000 tokens |
| **Velocidad de Inferencia** | ~500 – 600 tokens/segundo | ~250 – 300 tokens/segundo |
| **Cumplimiento Contrato JSON** | **100%** (9/9 pasadas exitosas en `test_consistencia.py`) | N/A (Error de disponibilidad) |
| **Estado en Producción / Vivo** | **Certificado HTTP 200 OK** | HTTP 404 (`model_not_found`) |

---

## 4. Justificación de la elección

Se seleccionó el modelo **`openai/gpt-oss-120b`** como el motor principal de inferencia por las siguientes razones técnicas y financieras:

1. **Eficiencia y Viabilidad Económica:**
   - Presenta una reducción de costos de cerca del **74% en tokens de entrada** y **24% en tokens de salida** en comparación con el modelo alternativo.
   - Para un flujo de trabajo con alta frecuencia de peticiones o integraciones continuas, optimiza sustancialmente la cuota de uso.

2. **Alta Velocidad e Inferencia Ultra-Rápida:**
   - Procesa entre 500 y 600 tokens por segundo en la infraestructura LPUs de Groq, minimizando la latencia del cliente CLI en la terminal.

3. **Determinismo y Estricto Cumplimiento de Contrato:**
   - Certificó un **100% de éxito (9/9)** en la batería de consistencia de prompts, garantizando que el JSON devuelto siempre contenga las claves obligatorias: `resumen`, `categoria` y `prioridad`.

---

## 5. Alternativa descartada y por qué

Se descartó formalmente el modelo **`llama-3.3-70b-versatile`** debido a los siguientes factores:

1. **Falta de Disponibilidad Técnica (Bloqueante):**
   - Durante la certificación en vivo contra la API de Groq, la consulta autenticada respondió con `HTTP 404 model_not_found`. El modelo no se encuentra activo o habilitado para el tier/proyecto de la cuenta utilizada, impidiendo su despliegue inmediato.

2. **Estructura de Costos Menos Competitiva:**
   - Mantiene una tarifa sensiblemente mayor ($0.59 USD por 1M de tokens de entrada), lo cual incrementa el costo operativo por request sin ofrecer ventajas funcionales adicionales para la tarea de estructuración de datos requerida.