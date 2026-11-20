"""
rag - Paquete de métricas y flujos RAG (Retrieval-Augmented Generation).

Expone utilidades para medir latencia, estimar costo y registrar
cada ejecución de un pipeline RAG en formato JSON Lines.
"""

from rag.metricas_rag import medir_etapa, registrar_consulta

__all__ = ["medir_etapa", "registrar_consulta"]
