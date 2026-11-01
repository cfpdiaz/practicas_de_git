# Registro de Decisión de Arquitectura (ADR-001): Elección de Modelo de IA

**Fecha:** 2026-10-22  
**Estado:** Aprobado  
**Proyecto:** Miniaplicación de Desarrollo con IA (Gate 1)  

---

## 1. Modelo elegido

**`openai/gpt-oss-120b`** (desplegado sobre la infraestructura de inferencia ultra-rápida de **Groq Cloud**).

---

## 2. Diagrama de arquitectura

La siguiente arquitectura describe cómo se integra el modelo elegido dentro del flujo de la miniaplicación, garantizando la navegación defensiva, validación de esquema y manejo de excepciones:

```mermaid
flowchart TD
    subgraph Entrada ["Interfaz de Línea de Comandos (CLI)"]
        CLI["app.py --task / --test-exceptions"]
        TESTS["pytest / test_app.py"]
    end

    subgraph Config ["Configuración y Seguridad"]
        ENV[".env / python-dotenv"]
        SEC["is_trusted_url + TLS SSL_VERIFY=true"]
    end

    subgraph Core ["Aplicación Principal (app.py)"]
        FETCH["fetch_api_data"]
        EX_HAND["Manejador de Excepciones de Red"]
        SCHEMA["Validador Estricto de Esquema JSON"]
    end

    subgraph External ["Proveedor Externo (Groq)"]
        GROQ["Groq API: openai/gpt-oss-120b"]
    end

    subgraph Output ["Salida y Evidencia"]
        JSON_OUT["Respuesta JSON Estructurada"]
        REPORT["informe_ejecucion.md / registro_resultados.json"]
    end

    CLI -->|Lee variables| ENV
    TESTS -->|Mocks de red| FETCH
    CLI -->|Ejecuta consulta| FETCH
    FETCH -->|Valida dominio seguro| SEC
    SEC -->|Petición POST HTTPS| GROQ
    GROQ -->|Respuesta HTTP 200 / JSON| EX_HAND
    EX_HAND -->|JSON Bruto| SCHEMA
    SCHEMA -->|structured_output| JSON_OUT
    JSON_OUT -->|Registra evidencia| REPORT