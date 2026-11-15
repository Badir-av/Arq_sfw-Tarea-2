"""Endpoint POST compartido por ambas arquitecturas.

Acortar una URL funciona igual en las dos; lo que cambia entre ellas es cómo
se responde el GET de redirección, que vive en cada arquitectura.
"""

from dataclasses import dataclass

from litestar import Request, post
from litestar.di import NamedDependency
from litestar.exceptions import ValidationException
from litestar.params import JSONBody

from common.repository import UrlRepository
from common.urls import InvalidUrlError, normalize_long_url


@dataclass
class ShortenRequest:
    url: str


@dataclass
class ShortenResponse:
    short_url: str
    hash: str
    long_url: str


@post("/shorten", sync_to_thread=True)
def shorten_url(
    data: JSONBody[ShortenRequest], repo: NamedDependency[UrlRepository], request: Request
) -> ShortenResponse:
    """Recibe la URL original y devuelve su URL corta."""
    try:
        long_url = normalize_long_url(data.url)
    except InvalidUrlError as exc:
        raise ValidationException(detail=str(exc)) from exc

    created = repo.create(long_url)
    return ShortenResponse(
        short_url=f"{request.base_url}{created.hash}",
        hash=created.hash,
        long_url=created.long_url,
    )
