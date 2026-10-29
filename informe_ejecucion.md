# Informe de Ejecución y Pruebas del Proyecto

**Fecha y hora de verificación:** 2026-10-22 16:12 (America/Santiago)
**Entorno:** Windows / PowerShell / Python 3.12.5 / `.venv`
**Endpoint:** `https://api.groq.com/openai/v1/chat/completions`
**Modelo:** `openai/gpt-oss-120b`
**TLS:** `SSL_VERIFY=true`

> La API key se mantiene únicamente en `.env`; no se reproduce en este informe.

## 1. Configuración y autenticación

Valores configurados en `.env` y `.env.example`:

```ini
API_BASE_URL=https://api.groq.com/openai/v1
AI_MODEL=openai/gpt-oss-120b
SSL_VERIFY=true
```

`git check-ignore -v .env` confirmó:

```text
.gitignore:38:.env    .env
```

La credencial autenticó correctamente contra Groq.

## 2. Consumo estándar en vivo sin overrides

Comando:

```powershell
python app.py
```

Resultado:

```json
{
  "success": true,
  "status": "success",
  "status_code": 200,
  "data": {
    "model": "openai/gpt-oss-120b",
    "usage": {
      "prompt_tokens": 224,
      "completion_tokens": 202,
      "total_tokens": 426
    }
  },
  "structured_output": {
    "resumen": "...",
    "categoria": "...",
    "prioridad": "alta"
  }
}
```

La respuesta fue recibida directamente desde Groq y validada por el contrato JSON.

## 3. Consistencia viva del banco de prompts

Comando sin overrides:

```powershell
python -m prompts.test_consistencia
```

| Prompt | Resultado | HTTP |
|---|---:|---:|
| `clasificar_incidente` | 3/3 (100.0%) | 200 en las 3 iteraciones |
| `analisis_sentimiento_soporte` | 3/3 (100.0%) | 200 en las 3 iteraciones |
| `extraccion_entidades_logistica` | 3/3 (100.0%) | 200 en las 3 iteraciones |
| **Total** | **9/9 (100.0%)** | **9 respuestas válidas** |

`prompts/registro_resultados.json` quedó actualizado con `meta_3_de_3_cumplida=true`.

## 4. Batería de excepciones y seguridad

Comando sin overrides:

```powershell
python app.py --test-exceptions
```

Resultados:

- Petición viva a Groq: HTTP 200.
- `Timeout`: interceptado.
- HTTP 429: clasificado como `RateLimitExceeded`.
- HTML/no-JSON: clasificado como `JSONDecodeError`.
- `is_trusted_url("https://httpbin.org/test", False)` devolvió `False` y no se envió `Authorization`.

## 5. Suite unitaria

Con `.venv` activado:

```text
pytest -ra
collected 6 items
6 passed in 2.19s
```

Resultado: **6 passed, 0 failed, 0 xfailed**.

## 6. Repositorio y evidencias

- `.env` y `.venv` no aparecen en `git ls-files`.
- Ambos permanecen ignorados por `.gitignore`.
- Existen `.env.example`, `README.md`, `informe_ejecucion.md` y `prompts/registro_resultados.json`.
- `README.md` contiene dos diagramas Mermaid.
- Ningún informe contiene la API key.

## Conclusión

La configuración quedó actualizada para que `python app.py` funcione sin overrides. La autenticación, el consumo HTTP 200, `structured_output`, el uso de tokens, la consistencia 9/9, las excepciones y la suite de 6 pruebas quedaron verificados directamente contra Groq. La credencial debe rotarse posteriormente porque fue compartida en el chat.

---

> **Nota:** documento registrado durante la validación del Gate 1 e integración en vivo con Groq.
