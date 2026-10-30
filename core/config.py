"""
core.config - Configuración centralizada y validación de entorno.

Carga variables desde .env, valida tipos y provee una configuración inmutable
que puede inyectarse en tests sin depender de variables globales.
"""

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv

# Cargar .env una sola vez al importar el módulo
load_dotenv()

DOMINIOS_CONFIABLES_POR_DEFECTO = frozenset({"api.groq.com", "api.openai.com", "openrouter.ai"})


@dataclass(frozen=True)
class ConfiguracionApp:
    """Configuración inmutable de la aplicación."""

    url_base_api: str
    clave_api: str | None
    segundos_timeout: float
    nombre_modelo: str
    verificar_ssl: bool
    dominios_confiables: frozenset[str] = DOMINIOS_CONFIABLES_POR_DEFECTO

    @property
    def host_base(self) -> str:
        """Host de la URL base en minúsculas."""
        return (urlparse(self.url_base_api).hostname or "").lower()

    def es_url_confiable(self, url: str, es_relativa: bool) -> bool:
        """
        Verifica si una URL es confiable para adjuntar credenciales (API Key).

        Es confiable si:
        1. Es una ruta relativa a url_base_api.
        2. Su host pertenece a los dominios confiables.
        3. Su host coincide con el host configurado en url_base_api.
        """
        if es_relativa:
            return True

        host_destino = (urlparse(url).hostname or "").lower()
        if not host_destino:
            return False

        if host_destino in self.dominios_confiables:
            return True

        if self.host_base and host_destino == self.host_base:
            return True

        return False


def cargar_configuracion() -> ConfiguracionApp:
    """
    Carga la configuración desde variables de entorno.

    Returns:
        ConfiguracionApp validada e inmutable.
    """
    url_base_api = os.getenv("API_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    clave_api = os.getenv("API_KEY") or None
    segundos_timeout = float(os.getenv("API_TIMEOUT", "10.0"))
    nombre_modelo = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
    valor_verificar_ssl = os.getenv("SSL_VERIFY", "true").strip().lower()
    verificar_ssl = valor_verificar_ssl not in ("false", "0", "no", "off")

    return ConfiguracionApp(
        url_base_api=url_base_api,
        clave_api=clave_api,
        segundos_timeout=segundos_timeout,
        nombre_modelo=nombre_modelo,
        verificar_ssl=verificar_ssl,
    )


# Instancia global por defecto (la que usa la CLI y los flujos normales)
config = cargar_configuracion()


def es_url_confiable(url: str, es_relativa: bool) -> bool:
    """Helper a nivel de módulo usando la configuración global."""
    return config.es_url_confiable(url, es_relativa)
