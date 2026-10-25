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

DEFAULT_TRUSTED_DOMAINS = frozenset({"api.groq.com", "api.openai.com", "openrouter.ai"})


@dataclass(frozen=True)
class AppConfig:
    """Configuración inmutable de la aplicación."""

    api_base_url: str
    api_key: str | None
    timeout_seconds: float
    model_name: str
    ssl_verify: bool
    trusted_domains: frozenset[str] = DEFAULT_TRUSTED_DOMAINS

    @property
    def base_host(self) -> str:
        """Host de la URL base en minúsculas."""
        return (urlparse(self.api_base_url).hostname or "").lower()

    def is_trusted_url(self, url: str, is_relative: bool) -> bool:
        """
        Verifica si una URL es confiable para adjuntar credenciales (API Key).

        Es confiable si:
        1. Es una ruta relativa a api_base_url.
        2. Su host pertenece a los dominios confiables.
        3. Su host coincide con el host configurado en api_base_url.
        """
        if is_relative:
            return True

        target_host = (urlparse(url).hostname or "").lower()
        if not target_host:
            return False

        if target_host in self.trusted_domains:
            return True

        if self.base_host and target_host == self.base_host:
            return True

        return False


def load_config() -> AppConfig:
    """
    Carga la configuración desde variables de entorno.

    Returns:
        AppConfig validada e inmutable.
    """
    api_base_url = os.getenv("API_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    api_key = os.getenv("API_KEY") or None
    timeout_seconds = float(os.getenv("API_TIMEOUT", "10.0"))
    model_name = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
    ssl_verify_env = os.getenv("SSL_VERIFY", "true").strip().lower()
    ssl_verify = ssl_verify_env not in ("false", "0", "no", "off")

    return AppConfig(
        api_base_url=api_base_url,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        model_name=model_name,
        ssl_verify=ssl_verify,
    )


# Instancia global por defecto (la que usa la CLI y los flujos normales)
config = load_config()


def is_trusted_url(url: str, is_relative: bool) -> bool:
    """Helper a nivel de módulo usando la configuración global."""
    return config.is_trusted_url(url, is_relative)
