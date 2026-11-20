"""
correr_bloque28.py - Script ejecutable del Bloque 28 (Latencia y Costo RAG).

Implementa un pipeline RAG completo sobre un corpus técnico local del proyecto,
registra métricas de latencia y costo en JSONL, y valida automáticamente los
registros al finalizar.

Uso:
    python correr_bloque28.py --offline
    python correr_bloque28.py --k 5 --output mi_registro.jsonl
    python correr_bloque28.py                   # usa API real si hay KEY válida
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Permitir ejecución desde la raíz del proyecto sin instalar el paquete
# ---------------------------------------------------------------------------
_RAIZ = Path(__file__).resolve().parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from core.api import armar_peticion, enviar_peticion, extraer_texto
from core.config import ConfiguracionApp, cargar_configuracion
from leer_registros import validar_registros
from rag.metricas_rag import registrar_consulta


# ---------------------------------------------------------------------------
# Corpus técnico local del proyecto (documentos para la base de conocimiento)
# ---------------------------------------------------------------------------

CORPUS: List[Dict[str, str]] = [
    {
        "id": "doc_arch_groq",
        "titulo": "Arquitectura del cliente HTTP con Groq",
        "contenido": (
            "El proyecto usa Groq como proveedor principal de inferencia a través del "
            "modelo openai/gpt-oss-120b, accesible en https://api.groq.com/openai/v1. "
            "La clase ClienteHttp en core/http_client.py encapsula la lógica de reintentos "
            "con backoff exponencial y delega la construcción de peticiones a armar_peticion "
            "en core/api.py, que genera la cabecera Authorization: Bearer <API_KEY> sólo "
            "cuando la URL destino es confiable según es_url_confiable."
        ),
    },
    {
        "id": "doc_seguridad_url",
        "titulo": "Seguridad anti-exfiltración: es_url_confiable",
        "contenido": (
            "ConfiguracionApp.es_url_confiable(url, es_relativa) implementa protección "
            "anti-exfiltración de API Key. Una URL es confiable si: (1) es una ruta relativa "
            "al url_base_api configurado, (2) su host pertenece a dominios_confiables "
            "(por defecto: api.groq.com, api.openai.com, openrouter.ai), o (3) su host "
            "coincide con el host del url_base_api. Si la URL no es confiable, enviar_peticion "
            "elimina el header Authorization antes de realizar la petición HTTP."
        ),
    },
    {
        "id": "doc_excepciones_http",
        "titulo": "Manejo de excepciones HTTP en ClienteHttp",
        "contenido": (
            "core/resiliencia.py define MAX_REINTENTOS=3, RETRASO_INICIAL=1.0s y "
            "FACTOR_BACKOFF=2.0. La función clasificar_error mapea excepciones de requests "
            "a categorías: Timeout → reintentable, HTTPError 429/5xx → reintentable, "
            "ConnectionError → reintentable, JSONDecodeError → no reintentable. "
            "ejecutar_con_reintentos aplica backoff exponencial con jitter antes de cada "
            "reintento y llama a fallback_offline si se agotan todos los intentos."
        ),
    },
    {
        "id": "doc_simulacion_offline",
        "titulo": "Modo simulación offline y placeholder de API Key",
        "contenido": (
            "core/simulation.py activa el modo simulación cuando la API Key es un placeholder "
            "('tu_groq_api_key_aqui', strings que empiezan con 'tu_', o None). La función "
            "es_modo_simulacion retorna True en ese caso (excepto para httpbin.org que se usa "
            "en tests). construir_respuesta_simulada genera una respuesta completa con estructura "
            "OpenAI-compatible incluyendo choices[0].message.content y usage con prompt_tokens, "
            "completion_tokens y total_tokens. Permite desarrollar sin credenciales reales."
        ),
    },
    {
        "id": "doc_limites_autonomia",
        "titulo": "Límites de autonomía del agente IA",
        "contenido": (
            "core/autonomia.py define NivelRiesgo (BAJO, MEDIO, ALTO, CRITICO) y MATRIZ_AUTONOMIA "
            "que mapea acciones a niveles de riesgo. nivel_de_accion determina si una acción "
            "puede ejecutarse autónomamente o requiere aprobación humana. requiere_aprobacion "
            "retorna True para riesgos ALTO y CRITICO. ejecutar_con_autonomia es el punto de "
            "entrada que valida el nivel antes de ejecutar. Si requiere_traza es True, la acción "
            "se registra en trazas_agente.jsonl."
        ),
    },
    {
        "id": "doc_config_env",
        "titulo": "Configuración desde variables de entorno (.env)",
        "contenido": (
            "core/config.py carga variables con python-dotenv: API_KEY (clave Groq), "
            "API_BASE_URL (por defecto https://api.groq.com/openai/v1), AI_MODEL "
            "(por defecto openai/gpt-oss-120b), API_TIMEOUT (por defecto 10.0s), "
            "SSL_VERIFY (por defecto true), REQUIERE_APROBACION (por defecto false). "
            "ConfiguracionApp es un dataclass frozen=True que garantiza inmutabilidad. "
            "La instancia global 'config' se crea al importar el módulo."
        ),
    },
    {
        "id": "doc_pipeline_rag",
        "titulo": "Pipeline RAG: embed, búsqueda y generación",
        "contenido": (
            "El flujo RAG del Bloque 28 se compone de dos etapas medidas: (1) embed_y_busqueda "
            "donde recuperar_documentos usa TF-IDF para rankear el corpus local según similitud "
            "coseno con la pregunta del usuario; (2) generacion donde generar_respuesta_rag "
            "construye un prompt con contexto y llama al LLM vía armar_peticion/enviar_peticion. "
            "rag/metricas_rag.py orquesta todo con medir_etapa (context manager perf_counter) "
            "y persiste un registro JSON Lines por ejecución en registros_latencia_costo.jsonl."
        ),
    },
    {
        "id": "doc_jsonl_formato",
        "titulo": "Formato JSON Lines para registros de observabilidad",
        "contenido": (
            "registros_latencia_costo.jsonl usa el formato JSON Lines (una línea = un objeto JSON). "
            "Cada registro tiene: timestamp (ISO 8601 UTC), pregunta, k (documentos recuperados), "
            "tiempos_ms (dict con embed_y_busqueda y generacion en ms), tiempo_total_ms, y tokens "
            "(dict con prompt_tokens, completion_tokens, total_tokens, costo_usd_estimado en USD). "
            "El costo estimado usa los precios de openai/gpt-oss-120b: $0.00059/1K prompt, "
            "$0.00079/1K completion."
        ),
    },
]


# ---------------------------------------------------------------------------
# TF-IDF simple (sin dependencias externas)
# ---------------------------------------------------------------------------

def _tokenizar(texto: str) -> List[str]:
    """Tokeniza en palabras minúsculas eliminando puntuación."""
    return re.findall(r"[a-záéíóúüñ\w]+", texto.lower())


def _calcular_tf(tokens: List[str]) -> Dict[str, float]:
    """Calcula Term Frequency normalizada."""
    conteo: Dict[str, int] = {}
    for t in tokens:
        conteo[t] = conteo.get(t, 0) + 1
    n = max(len(tokens), 1)
    return {t: c / n for t, c in conteo.items()}


def _calcular_idf(corpus_tokens: List[List[str]]) -> Dict[str, float]:
    """Calcula Inverse Document Frequency sobre el corpus."""
    n_docs = len(corpus_tokens)
    df: Dict[str, int] = {}
    for doc_tokens in corpus_tokens:
        for t in set(doc_tokens):
            df[t] = df.get(t, 0) + 1
    return {
        t: math.log((n_docs + 1) / (freq + 1)) + 1.0
        for t, freq in df.items()
    }


def _similitud_coseno(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Calcula similitud coseno entre dos vectores dispersos."""
    terminos = set(vec_a) & set(vec_b)
    if not terminos:
        return 0.0
    dot = sum(vec_a[t] * vec_b[t] for t in terminos)
    norma_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    norma_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return dot / (norma_a * norma_b)


# Pre-calcular IDF una sola vez al importar el módulo
_corpus_tokens: List[List[str]] = [
    _tokenizar(doc["titulo"] + " " + doc["contenido"]) for doc in CORPUS
]
_idf_global: Dict[str, float] = _calcular_idf(_corpus_tokens)
_tfidf_docs: List[Dict[str, float]] = []
for _doc_tokens in _corpus_tokens:
    _tf = _calcular_tf(_doc_tokens)
    _tfidf_docs.append({t: _tf[t] * _idf_global.get(t, 1.0) for t in _tf})


def recuperar_documentos(pregunta: str, k: int) -> List[Dict[str, str]]:
    """Recupera los ``k`` documentos más relevantes usando TF-IDF + coseno.

    Args:
        pregunta: Consulta del usuario.
        k: Número de documentos a retornar.

    Returns:
        Lista de dicts ``{"titulo": ..., "contenido": ...}`` ordenada por relevancia.
    """
    tokens_q = _tokenizar(pregunta)
    tf_q = _calcular_tf(tokens_q)
    tfidf_q = {t: tf_q[t] * _idf_global.get(t, 1.0) for t in tf_q}

    puntuaciones = [
        (i, _similitud_coseno(tfidf_q, tfidf_doc))
        for i, tfidf_doc in enumerate(_tfidf_docs)
    ]
    puntuaciones.sort(key=lambda x: x[1], reverse=True)

    return [
        {"titulo": CORPUS[i]["titulo"], "contenido": CORPUS[i]["contenido"]}
        for i, _ in puntuaciones[:k]
    ]


# ---------------------------------------------------------------------------
# Generación RAG con core/api.py
# ---------------------------------------------------------------------------

def generar_respuesta_rag(
    pregunta: str,
    documentos: List[Dict[str, str]],
    cfg: ConfiguracionApp | None = None,
) -> Any:
    """Genera una respuesta RAG usando el LLM configurado.

    Construye un prompt de contexto con los documentos recuperados, llama a
    ``armar_peticion`` / ``enviar_peticion`` de ``core/api.py`` y retorna el
    objeto de respuesta (compatible con ``_extraer_tokens_y_costo``).

    Args:
        pregunta: Consulta original del usuario.
        documentos: Documentos recuperados por ``recuperar_documentos``.
        cfg: Configuración opcional (por defecto usa la global).

    Returns:
        Objeto ``RespuestaSimulada`` o ``requests.Response`` con ``.json()``
        que incluye ``usage`` con conteo de tokens.
    """
    # Construir contexto
    bloques_contexto = []
    for idx, doc in enumerate(documentos, start=1):
        bloques_contexto.append(
            f"[{idx}] {doc['titulo']}\n{doc['contenido']}"
        )
    contexto = "\n\n".join(bloques_contexto)

    prompt = (
        f"Usando exclusivamente el contexto técnico proporcionado, responde de forma "
        f"concisa y precisa la siguiente pregunta.\n\n"
        f"CONTEXTO:\n{contexto}\n\n"
        f"PREGUNTA: {pregunta}\n\n"
        f"RESPUESTA:"
    )

    instruccion_sistema = (
        "Eres un asistente técnico especializado en este proyecto Python. "
        "Responde en español, siendo preciso y basándote sólo en el contexto dado. "
        "Si la respuesta no está en el contexto, indícalo claramente."
    )

    peticion = armar_peticion(
        prompt=prompt,
        instruccion_sistema=instruccion_sistema,
        forzar_json=False,
        config=cfg,
    )
    respuesta = enviar_peticion(peticion, config=cfg)
    return respuesta


# ---------------------------------------------------------------------------
# Preguntas de prueba del Bloque 28
# ---------------------------------------------------------------------------

PREGUNTAS_PRUEBA: List[str] = [
    "¿Cómo funciona el modo simulación offline cuando la API Key es un placeholder?",
    "¿Qué hace es_url_confiable y por qué es importante para la seguridad?",
    "¿Cuántos reintentos realiza el cliente HTTP y cuál es la estrategia de backoff?",
]


# ---------------------------------------------------------------------------
# Forzar modo offline inyectando config con placeholder
# ---------------------------------------------------------------------------

def _crear_config_offline() -> ConfiguracionApp:
    """Crea una configuración que activa el modo simulación offline."""
    return ConfiguracionApp(
        url_base_api="https://api.groq.com/openai/v1",
        clave_api="tu_groq_api_key_aqui",   # placeholder → activa simulación
        segundos_timeout=10.0,
        nombre_modelo="openai/gpt-oss-120b",
        verificar_ssl=True,
    )


# ---------------------------------------------------------------------------
# CLI principal
# ---------------------------------------------------------------------------

def _parsear_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bloque 28 — Registra latencia y costo del flujo RAG"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Fuerza el modo simulación offline (no requiere API Key real).",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=3,
        metavar="K",
        help="Número de documentos a recuperar por consulta (por defecto: 3).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("registros_latencia_costo.jsonl"),
        metavar="ARCHIVO",
        help="Ruta del archivo JSONL de salida (por defecto: registros_latencia_costo.jsonl).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parsear_args()

    # Determinar configuración
    if args.offline:
        cfg: ConfiguracionApp = _crear_config_offline()
        print("🔌  Modo: SIMULACIÓN OFFLINE (placeholder key)")
    else:
        cfg = cargar_configuracion()
        from core.simulation import es_modo_simulacion
        url_prueba = f"{cfg.url_base_api}/chat/completions"
        if es_modo_simulacion(cfg, url_prueba, cfg.segundos_timeout):
            print("🔌  Modo: SIMULACIÓN OFFLINE (key no configurada en .env)")
        else:
            print("🌐  Modo: API REAL")

    print(f"📄  Archivo de salida : {args.output}")
    print(f"🔢  k (docs por query): {args.k}")
    print()

    # Limpiar el archivo de salida si ya existe (para demo limpia)
    ruta_salida: Path = Path(args.output)
    if ruta_salida.exists():
        ruta_salida.unlink()
        print(f"🗑   Archivo previo eliminado: {ruta_salida.name}")

    # Funciones adaptadas para inyectar cfg
    def fn_recuperar(pregunta: str, k: int) -> List[Dict[str, str]]:
        return recuperar_documentos(pregunta, k)

    def fn_generar(pregunta: str, documentos: List[Dict[str, str]]) -> Any:
        return generar_respuesta_rag(pregunta, documentos, cfg=cfg)

    # Ejecutar las 3 preguntas
    for idx, pregunta in enumerate(PREGUNTAS_PRUEBA, start=1):
        print(f"[{idx}/{len(PREGUNTAS_PRUEBA)}] Procesando: {pregunta[:60]}...")
        try:
            registro = registrar_consulta(
                pregunta=pregunta,
                fn_recuperar=fn_recuperar,
                fn_generar=fn_generar,
                k=args.k,
                ruta_salida=ruta_salida,
            )
            tiempos = registro.get("tiempos_ms", {})
            print(
                f"      embed+búsqueda: {tiempos.get('embed_y_busqueda', 0):.1f} ms  |  "
                f"generación: {tiempos.get('generacion', 0):.1f} ms  |  "
                f"total: {registro.get('tiempo_total_ms', 0):.1f} ms"
            )
            tokens = registro.get("tokens") or {}
            costo = tokens.get("costo_usd_estimado")
            if costo is not None:
                print(f"      Tokens: {tokens.get('total_tokens', '?')}  |  Costo: ${costo:.8f}")
        except Exception as exc:  # noqa: BLE001
            print(f"      ❌ Error en consulta #{idx}: {exc}", file=sys.stderr)
            sys.exit(1)

    print()
    print(f"✅  {len(PREGUNTAS_PRUEBA)} registros escritos en: {ruta_salida}")
    print()

    # Validar automáticamente al finalizar
    print("─" * 60)
    print("🔍  Ejecutando validación automática...")
    print("─" * 60)
    try:
        validar_registros(ruta=ruta_salida)
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌  Validación fallida: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
