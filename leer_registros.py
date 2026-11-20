"""
leer_registros.py - Script de verificación de registros_latencia_costo.jsonl

Lee el archivo JSONL generado por el flujo RAG del Bloque 28, valida su
integridad (mínimo 3 líneas, 6 claves obligatorias por línea) y muestra
un resumen legible de latencias por etapa y costo estimado.

Uso:
    python leer_registros.py
    python leer_registros.py --archivo ruta/personalizada.jsonl
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


CLAVES_OBLIGATORIAS: tuple[str, ...] = (
    "timestamp",
    "pregunta",
    "k",
    "tiempos_ms",
    "tiempo_total_ms",
    "tokens",
)

MINIMO_REGISTROS: int = 3
ARCHIVO_DEFAULT: Path = Path("registros_latencia_costo.jsonl")


# ---------------------------------------------------------------------------
# Lectura y validación
# ---------------------------------------------------------------------------

def leer_y_validar(ruta: Path) -> List[Dict[str, Any]]:
    """Lee el JSONL, valida cada línea y retorna la lista de registros.

    Raises:
        FileNotFoundError: Si el archivo no existe.
        ValueError: Si hay menos de ``MINIMO_REGISTROS`` líneas válidas, o si
                    alguna línea no es JSON válido o le faltan claves.
    """
    if not ruta.exists():
        raise FileNotFoundError(
            f"Archivo no encontrado: {ruta}\n"
            "  → Ejecute primero: python correr_bloque28.py --offline"
        )

    registros: List[Dict[str, Any]] = []
    errores: List[str] = []

    with ruta.open("r", encoding="utf-8") as fh:
        for numero_linea, linea_raw in enumerate(fh, start=1):
            linea = linea_raw.strip()
            if not linea:
                continue  # saltar líneas vacías

            # Validar JSON
            try:
                registro = json.loads(linea)
            except json.JSONDecodeError as exc:
                errores.append(f"  Línea {numero_linea}: JSON inválido → {exc}")
                continue

            if not isinstance(registro, dict):
                errores.append(
                    f"  Línea {numero_linea}: se esperaba un objeto JSON (dict), "
                    f"se obtuvo {type(registro).__name__}"
                )
                continue

            # Validar claves obligatorias
            faltantes = [c for c in CLAVES_OBLIGATORIAS if c not in registro]
            if faltantes:
                errores.append(
                    f"  Línea {numero_linea}: faltan claves → {faltantes}"
                )
                continue

            registros.append(registro)

    if errores:
        raise ValueError(
            f"Se encontraron errores en el archivo JSONL:\n" + "\n".join(errores)
        )

    if len(registros) < MINIMO_REGISTROS:
        raise ValueError(
            f"Se requieren al menos {MINIMO_REGISTROS} registros válidos; "
            f"se encontraron {len(registros)}."
        )

    return registros


# ---------------------------------------------------------------------------
# Resumen en consola
# ---------------------------------------------------------------------------

def _fmt_ms(valor: Any) -> str:
    """Formatea un valor de milisegundos con 2 decimales."""
    try:
        return f"{float(valor):.2f} ms"
    except (TypeError, ValueError):
        return str(valor)


def _fmt_costo(valor: Any) -> str:
    """Formatea un costo en USD con 8 decimales significativos."""
    try:
        return f"${float(valor):.8f}"
    except (TypeError, ValueError):
        return str(valor)


def mostrar_resumen(registros: List[Dict[str, Any]], ruta: Path) -> None:
    """Imprime en consola un resumen tabular de cada registro."""
    separador = "─" * 72

    print()
    print("╔" + "═" * 70 + "╗")
    print(f"║  {'RESUMEN — REGISTROS_LATENCIA_COSTO.JSONL':^68}  ║")
    print("╚" + "═" * 70 + "╝")
    print(f"  Archivo : {ruta.resolve()}")
    print(f"  Total de registros válidos: {len(registros)}")
    print()

    # Acumuladores para promedios
    totales_embed: float = 0.0
    totales_gen: float = 0.0
    totales_total: float = 0.0
    totales_costo: float = 0.0
    n_con_tokens: int = 0

    for idx, reg in enumerate(registros, start=1):
        print(separador)
        print(f"  Registro #{idx}  |  {reg.get('timestamp', 'N/A')}")
        print(f"  Pregunta : {reg.get('pregunta', '')[:70]}")
        print(f"  k        : {reg.get('k', '?')}")

        tiempos = reg.get("tiempos_ms") or {}
        embed_ms = tiempos.get("embed_y_busqueda", 0.0)
        gen_ms = tiempos.get("generacion", 0.0)
        total_ms = reg.get("tiempo_total_ms", 0.0)

        print(f"  Latencias:")
        print(f"    embed_y_busqueda : {_fmt_ms(embed_ms)}")
        print(f"    generacion       : {_fmt_ms(gen_ms)}")
        print(f"    tiempo_total_ms  : {_fmt_ms(total_ms)}")

        tokens = reg.get("tokens")
        if tokens and isinstance(tokens, dict):
            pt = tokens.get("prompt_tokens", 0)
            ct = tokens.get("completion_tokens", 0)
            tt = tokens.get("total_tokens", 0)
            costo = tokens.get("costo_usd_estimado", 0.0)
            print(f"  Tokens:")
            print(f"    prompt     : {pt}")
            print(f"    completion : {ct}")
            print(f"    total      : {tt}")
            print(f"    costo est. : {_fmt_costo(costo)}")
            totales_costo += float(costo)
            n_con_tokens += 1
        else:
            print("  Tokens: N/A")

        totales_embed += float(embed_ms)
        totales_gen += float(gen_ms)
        totales_total += float(total_ms)

    n = len(registros)
    print(separador)
    print()
    print("  PROMEDIOS:")
    print(f"    embed_y_busqueda : {_fmt_ms(totales_embed / n)}")
    print(f"    generacion       : {_fmt_ms(totales_gen / n)}")
    print(f"    tiempo_total_ms  : {_fmt_ms(totales_total / n)}")
    if n_con_tokens > 0:
        print(f"    costo_usd_total  : {_fmt_costo(totales_costo)}")
        print(f"    costo_usd_prom   : {_fmt_costo(totales_costo / n_con_tokens)}")
    print()
    print("  ✅  Validación completada sin errores.")
    print()


# ---------------------------------------------------------------------------
# Función pública reutilizable (usada por correr_bloque28.py)
# ---------------------------------------------------------------------------

def validar_registros(
    ruta: Path = ARCHIVO_DEFAULT,
    *,
    silencioso: bool = False,
) -> List[Dict[str, Any]]:
    """Lee, valida y (opcionalmente) muestra el resumen del JSONL.

    Args:
        ruta: Ruta al archivo ``.jsonl``.
        silencioso: Si ``True``, omite la impresión del resumen.

    Returns:
        Lista de registros validados.
    """
    registros = leer_y_validar(ruta)
    if not silencioso:
        mostrar_resumen(registros, ruta)
    return registros


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parsear_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verifica y muestra el resumen de registros_latencia_costo.jsonl"
    )
    parser.add_argument(
        "--archivo",
        type=Path,
        default=ARCHIVO_DEFAULT,
        help=f"Ruta al archivo JSONL (por defecto: {ARCHIVO_DEFAULT})",
    )
    return parser.parse_args()


def main() -> None:
    args = _parsear_args()
    try:
        validar_registros(args.archivo)
    except (FileNotFoundError, ValueError) as exc:
        print(f"\n❌  Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
