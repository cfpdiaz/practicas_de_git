"""
prompts/banco.py - Definición oficial del Banco de Prompts para Gate 1.

Contiene combinaciones estructuradas con:
- nombre
- descripcion
- instruccion_sistema
- ejemplo_entrada
- claves_esperadas

Es la fuente de verdad del catalogo de tareas usado por la CLI (core/tasks.py).
"""

BANCO_DE_PROMPTS = [
    {
        "nombre": "clasificar_incidente",
        "descripcion": "Clasificación y triaje de incidentes de TI",
        "instruccion_sistema": (
            "Eres un asistente de IA especializado en análisis y clasificación de incidentes técnicos. "
            "Debes responder EXCLUSIVAMENTE con un objeto JSON válido con la siguiente estructura exacta: "
            '{"resumen": "string", "categoria": "string", "prioridad": "alta|media|baja"}. '
            "No incluyas explicaciones ni texto adicional fuera del JSON."
        ),
        "ejemplo_entrada": (
            "El servidor de base de datos en producción está experimentando una sobrecarga "
            "crítica de CPU (98%) y los clientes reportan tiempos de respuesta muy lentos."
        ),
        "claves_esperadas": ["resumen", "categoria", "prioridad"],
    },
    {
        "nombre": "analisis_sentimiento_soporte",
        "descripcion": "Análisis de sentimiento y urgencia en reclamos de clientes",
        "instruccion_sistema": (
            "Eres un analista de soporte al cliente. Analiza el reclamo y responde EXCLUSIVAMENTE "
            "con un objeto JSON válido con la siguiente estructura exacta: "
            '{"resumen": "string", "sentimiento": "positivo|neutral|negativo", "urgencia": "alta|media|baja"}. '
            "No incluyas explicaciones ni texto adicional fuera del JSON."
        ),
        "ejemplo_entrada": (
            "Llevo 3 días intentando acceder a mi cuenta pagada y nadie me da respuesta. "
            "Exijo una solución inmediata o la cancelación del servicio."
        ),
        "claves_esperadas": ["resumen", "sentimiento", "urgencia"],
    },
    {
        "nombre": "extraccion_entidades_logistica",
        "descripcion": "Extracción estructurada de datos de pedidos o despachos",
        "instruccion_sistema": (
            "Eres un extractor de datos logísticos. Procesa la solicitud y responde EXCLUSIVAMENTE "
            "con un objeto JSON válido con la siguiente estructura exacta: "
            '{"numero_pedido": "string", "destino": "string", "estado_envio": "pendiente|en_transito|entregado"}. '
            "No incluyas explicaciones ni texto adicional fuera del JSON."
        ),
        "ejemplo_entrada": (
            "El pedido #ORD-98234 dirigido a la ciudad de Valparaíso se encuentra actualmente en ruta de entrega."
        ),
        "claves_esperadas": ["numero_pedido", "destino", "estado_envio"],
    },
]
