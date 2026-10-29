"""
main.py - Verificación del entorno virtual del proyecto.

Imprime la versión de Python y confirma que el entorno está configurado.
"""

import sys


def main() -> None:
    print("¡Entorno virtual y proyecto configurados correctamente!")
    print(f"Versión de Python: {sys.version}")


if __name__ == "__main__":
    main()
