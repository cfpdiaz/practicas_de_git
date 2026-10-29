"""
Paquete prompts - Banco de prompts y pruebas de consistencia del Gate 1.

Contiene:
- ``banco.py``: banco de prompts estructurados (fuente de verdad de las tareas).
- ``test_consistencia.py``: prueba de consistencia (3 iteraciones por prompt).
- ``registro_resultados.json``: evidencia generada (9/9 ejecuciones validas).
"""

from prompts.banco import BANCO_DE_PROMPTS

__all__ = ["BANCO_DE_PROMPTS"]
