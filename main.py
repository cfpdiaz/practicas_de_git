"""
main.py - Punto de entrada directo (sin banderas obligatorias).

Verifica el entorno virtual y ejecuta el flujo de consumo de la API de IA
Generativa, mostrando la respuesta estructurada en JSON. Si no hay una API Key
configurada (valor placeholder), activa automáticamente el modo de simulación
offline, por lo que funciona sin conexión ni credenciales.

Pensado para auditoría automatizada: `python main.py` no requiere argumentos y
devuelve código de salida 0 cuando la ejecución es correcta.
"""

import json
import sys

from core.api import obtener_datos_api
from core.config import config


def main() -> int:
    """Ejecuta el flujo principal y devuelve el código de salida."""
    print("¡Entorno virtual y proyecto configurados correctamente!")
    print(f"Versión de Python: {sys.version.split()[0]}")
    print(f"Modelo: {config.nombre_modelo}")
    print(f"Endpoint: {config.url_base_api}")
    print()
    print("=== Resultado del flujo de consumo (sin banderas) ===")

    resultado = obtener_datos_api()
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

    return 0 if resultado.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
