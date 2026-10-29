# Reporte de Verificación Final — Gate 1

**Fecha:** 2026-10-22 16:12 (America/Santiago)
**Entorno:** Windows, Python 3.12.5, `.venv`, pytest 8.4.2.

## Configuración y seguridad

- `API_BASE_URL=https://api.groq.com/openai/v1`.
- `AI_MODEL=openai/gpt-oss-120b` en `.env` y `.env.example`.
- `SSL_VERIFY=true`.
- La API key está configurada localmente y no se reproduce en este informe.
- `git check-ignore -v .env` confirmó `.gitignore:38:.env`.
- `.env` y `.venv` no aparecen en `git ls-files`.

## 1. Consumo estándar en vivo

Comando ejecutado sin variables de modelo adicionales:

```text
python app.py
```

Resultado autenticado desde Groq:

- HTTP **200 OK**.
- `data.model`: `openai/gpt-oss-120b`.
- `structured_output` contiene `resumen`, `categoria` y `prioridad`.
- `data.usage`: `prompt_tokens=224`, `completion_tokens=202`, `total_tokens=426`.
- La respuesta incluyó identificador de solicitud y métricas de uso de Groq.

## 2. Consistencia viva de prompts

Comando ejecutado sin overrides:

```text
python -m prompts.test_consistencia
```

Resultado contra Groq:

- `clasificar_incidente`: **3/3 (100.0%)**.
- `analisis_sentimiento_soporte`: **3/3 (100.0%)**.
- `extraccion_entidades_logistica`: **3/3 (100.0%)**.
- Total: **9/9 (100.0%)**.
- Las 9 iteraciones registraron `status_code=200`.
- `prompts/registro_resultados.json` quedó actualizado con `meta_3_de_3_cumplida=true`.

## 3. Excepciones y protección de credenciales

Comando ejecutado sin overrides:

```text
python app.py --test-exceptions
```

Resultados:

- Petición viva a Groq: HTTP 200.
- `Timeout`: interceptado correctamente.
- HTTP 429: clasificado como `RateLimitExceeded`.
- HTML/no-JSON: clasificado como `JSONDecodeError`.
- La comprobación con la credencial cargada confirmó `is_trusted_url=False` y `authorization_sent=False` para `https://httpbin.org/test`.

## 4. Suite unitaria

Con el entorno virtual activado:

```text
pytest -ra
collected 6 items
6 passed in 2.19s
```

Resultado: **6 passed, 0 failed, 0 xfailed**.

## 5. Evidencias del repositorio

- `.env` y `.venv` están excluidos del índice Git.
- Existen `.env.example`, `README.md`, `informe_ejecucion.md` y `prompts/registro_resultados.json`.
- `README.md` contiene dos diagramas Mermaid.
- Los informes no contienen la API key.

## Resultado por dimensión

| Dimensión | Resultado |
|---|---|
| Python y código | PASS — 6/6 tests |
| Prompt y respuesta | PASS vivo — 9/9 |
| Consumo API | PASS vivo — HTTP 200 |
| Excepciones | PASS |
| Seguridad anti-exfiltración | PASS |
| Entorno/repositorio | PASS |

## Conclusión

La ejecución estándar, la consistencia de prompts y la batería de excepciones se certificaron directamente contra Groq sin overrides. Todas las pruebas unitarias pasan. La credencial debe rotarse posteriormente porque fue compartida en el chat.

---

> **Nota:** documento registrado durante la validación del Gate 1 e integración en vivo con Groq.
