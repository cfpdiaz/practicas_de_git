"""
prompts/test_consistencia.py - Prueba de Consistencia para el Gate 1.

Ejecuta iteraciones consecutivas por cada prompt estructurado definido en
`prompts/banco.py` contra la API utilizando `fetch_api_data` de `app.py`.
Valida que cada respuesta sea un JSON válido y contenga las claves esperadas.
Calcula la tasa de éxito y guarda automáticamente la evidencia en
`prompts/registro_resultados.json`.

Ejecucion: ``python -m prompts.test_consistencia``.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

# Asegurar que el directorio raíz del proyecto esté en sys.path para importaciones
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import fetch_api_data
from prompts.banco import BANCO_DE_PROMPTS

ITERACIONES_POR_PROMPT = 3
REGISTRO_RESULTADOS_PATH = PROJECT_ROOT / "prompts" / "registro_resultados.json"


def validar_respuesta_json(
    respuesta: Dict[str, Any], claves_esperadas: List[str]
) -> Dict[str, Any]:
    """
    Valida que la respuesta de la API sea exitosa, represente un JSON válido y
    contenga todas las claves requeridas por el contrato.
    """
    if not isinstance(respuesta, dict):
        return {
            "valido": False,
            "error": f"La respuesta no es un diccionario: {type(respuesta).__name__}",
            "claves_presentes": [],
            "datos_extraidos": None,
        }

    if not respuesta.get("success", False):
        error_msg = respuesta.get("message") or respuesta.get("error_type") or "Fallo en la petición"
        details = respuesta.get("details")
        full_error = f"{error_msg} (Detalles: {details})" if details else str(error_msg)
        return {
            "valido": False,
            "error": full_error,
            "claves_presentes": [],
            "datos_extraidos": None,
        }

    # Obtener el objeto estructurado
    structured = respuesta.get("structured_output")
    if structured is None and "data" in respuesta:
        try:
            choices = respuesta["data"].get("choices", [])
            if choices and "message" in choices[0]:
                content = choices[0]["message"].get("content", "")
                structured = json.loads(content)
        except Exception as err:
            return {
                "valido": False,
                "error": f"No se pudo extraer JSON de choices.content: {err}",
                "claves_presentes": [],
                "datos_extraidos": None,
            }

    if not isinstance(structured, dict):
        return {
            "valido": False,
            "error": f"El contenido estructurado no es un diccionario válido: {type(structured).__name__}",
            "claves_presentes": [],
            "datos_extraidos": structured,
        }

    claves_presentes = list(structured.keys())
    claves_faltantes = set(claves_esperadas) - set(claves_presentes)

    if claves_faltantes:
        return {
            "valido": False,
            "error": f"Faltan claves esperadas en el JSON: {sorted(claves_faltantes)}",
            "claves_presentes": claves_presentes,
            "datos_extraidos": structured,
        }

    return {
        "valido": True,
        "error": None,
        "claves_presentes": claves_presentes,
        "datos_extraidos": structured,
    }


def ejecutar_pruebas_consistencia() -> int:
    """
    Ejecuta 3 iteraciones seguidas por cada prompt de BANCO_DE_PROMPTS,
    evalúa la consistencia, genera el reporte JSON y muestra resultados en terminal.
    """
    ahora_local = datetime.now()
    ahora_utc = datetime.now(timezone.utc)

    print("=" * 65)
    print(" PRUEBA DE CONSISTENCIA - BANCO DE PROMPTS (GATE 1)")
    print("=" * 65)
    print(f" Fecha y hora local: {ahora_local.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Total de prompts a evaluar: {len(BANCO_DE_PROMPTS)}")
    print(f" Iteraciones por prompt:     {ITERACIONES_POR_PROMPT}")
    print("=" * 65)

    detalle_prompts: List[Dict[str, Any]] = []
    total_ejecuciones = 0
    total_validas = 0
    total_fallidas = 0

    for idx, prompt_info in enumerate(BANCO_DE_PROMPTS, start=1):
        nombre = prompt_info["nombre"]
        descripcion = prompt_info.get("descripcion", "")
        system_instruction = prompt_info["system_instruction"]
        ejemplo_entrada = prompt_info["ejemplo_entrada"]
        claves_esperadas = prompt_info["claves_esperadas"]

        print(f"\n[{idx}/{len(BANCO_DE_PROMPTS)}] Evaluando prompt: '{nombre}'")
        print(f"      Descripción: {descripcion}")
        print(f"      Claves esperadas: {claves_esperadas}")

        iteraciones_resultado: List[Dict[str, Any]] = []
        validas_prompt = 0
        fallidas_prompt = 0

        for i in range(1, ITERACIONES_POR_PROMPT + 1):
            total_ejecuciones += 1
            # Realizar llamada a través de fetch_api_data de app.py
            respuesta = fetch_api_data(
                prompt=ejemplo_entrada,
                system_instruction=system_instruction,
                required_keys=claves_esperadas,
            )

            validacion = validar_respuesta_json(respuesta, claves_esperadas)
            es_valido = validacion["valido"]

            if es_valido:
                validas_prompt += 1
                total_validas += 1
                estado_str = "OK"
            else:
                fallidas_prompt += 1
                total_fallidas += 1
                estado_str = f"FALLÓ: {validacion['error']}"

            iteraciones_resultado.append(
                {
                    "iteracion": i,
                    "valida": es_valido,
                    "claves_detectadas": validacion["claves_presentes"],
                    "salida": validacion["datos_extraidos"],
                    "error": validacion["error"],
                    "status_code": respuesta.get("status_code"),
                }
            )

            print(f"  - Iteración {i}/{ITERACIONES_POR_PROMPT}: {estado_str}")

        tasa_exito_prompt = (
            f"{validas_prompt}/{ITERACIONES_POR_PROMPT} "
            f"({(validas_prompt / ITERACIONES_POR_PROMPT) * 100:.1f}%)"
        )
        consistente = validas_prompt == ITERACIONES_POR_PROMPT

        detalle_prompts.append(
            {
                "nombre": nombre,
                "descripcion": descripcion,
                "claves_esperadas": claves_esperadas,
                "total_iteraciones": ITERACIONES_POR_PROMPT,
                "validas": validas_prompt,
                "fallidas": fallidas_prompt,
                "tasa_exito": tasa_exito_prompt,
                "consistente": consistente,
                "iteraciones": iteraciones_resultado,
            }
        )

        print(f"  --> Resultado '{nombre}': {tasa_exito_prompt} - Consistente: {'SÍ' if consistente else 'NO'}")

    tasa_global = (
        f"{total_validas}/{total_ejecuciones} "
        f"({(total_validas / total_ejecuciones) * 100:.1f}%)"
        if total_ejecuciones > 0
        else "0.0%"
    )
    meta_cumplida = total_validas == total_ejecuciones

    registro_final = {
        "fecha": ahora_local.strftime("%Y-%m-%d"),
        "hora": ahora_local.strftime("%H:%M:%S"),
        "timestamp_iso": ahora_utc.isoformat(),
        "resumen_ejecucion": {
            "total_prompts": len(BANCO_DE_PROMPTS),
            "iteraciones_por_prompt": ITERACIONES_POR_PROMPT,
            "total_ejecuciones": total_ejecuciones,
            "ejecuciones_validas": total_validas,
            "ejecuciones_fallidas": total_fallidas,
            "tasa_exito_global": tasa_global,
            "meta_3_de_3_cumplida": meta_cumplida,
        },
        "detalle_por_prompt": detalle_prompts,
    }

    # Guardar automáticamente en prompts/registro_resultados.json
    REGISTRO_RESULTADOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRO_RESULTADOS_PATH, "w", encoding="utf-8") as f:
        json.dump(registro_final, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 65)
    print(" RESUMEN GENERAL DE CONSISTENCIA")
    print("=" * 65)
    print(f" Total ejecuciones:       {total_ejecuciones}")
    print(f" Ejecuciones válidas:     {total_validas}")
    print(f" Ejecuciones fallidas:    {total_fallidas}")
    print(f" Tasa de éxito global:    {tasa_global}")
    print(f" Meta (3/3 por prompt):   {'CUMPLIDA CON ÉXITO' if meta_cumplida else 'NO CUMPLIDA'}")
    print(f" Registro guardado en:    {REGISTRO_RESULTADOS_PATH}")
    print("=" * 65)

    return 0 if meta_cumplida else 1


if __name__ == "__main__":
    sys.exit(ejecutar_pruebas_consistencia())
