"""Validación y normalización de la URL original recibida en el POST."""

from urllib.parse import urlsplit


class InvalidUrlError(ValueError):
    pass


def normalize_long_url(raw: str) -> str:
    """Devuelve una URL absoluta http(s) o lanza InvalidUrlError.

    El enunciado usa ejemplos sin esquema ("usm.cl/informatica/..."). Sin
    esquema, el header Location se interpretaría como ruta relativa al
    acortador, así que en ese caso se asume https.
    """
    url = raw.strip()
    if not url:
        raise InvalidUrlError("La URL no puede estar vacía")
    if "://" not in url:
        url = f"https://{url}"

    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise InvalidUrlError("Solo se aceptan URLs http o https")
    if not parts.hostname or "." not in parts.hostname:
        raise InvalidUrlError("La URL no tiene un dominio válido")
    return url
