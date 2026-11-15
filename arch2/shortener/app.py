"""Shortener v2: redirección permanente (301) + rate limiter + caché.

Implementa dos tácticas arquitectónicas:
- "Controlar arribo de eventos": RateLimitMiddleware de LiteStar.
- "Mantener múltiples copias de datos": caché de respuestas de LiteStar, que
  guarda en memoria una copia de la redirección ya resuelta desde la DB.
"""

from litestar import Litestar, get
from litestar.config.response_cache import ResponseCacheConfig
from litestar.di import NamedDependency, Provide
from litestar.exceptions import NotFoundException
from litestar.middleware.rate_limit import RateLimitConfig
from litestar.params import FromPath
from litestar.response import Redirect
from litestar.status_codes import HTTP_301_MOVED_PERMANENTLY

from common.api import shorten_url
from common.repository import UrlRepository


# cache=True: la primera respuesta para cada hash se guarda y las siguientes se
# sirven desde la copia en memoria sin consultar la DB. LiteStar solo cachea
# respuestas 2xx, 301 y 308, así que un 404 nunca queda cacheado y un hash que
# aún no existe puede crearse después sin problemas.
@get("/{url_hash:str}", cache=True, sync_to_thread=True)
def redirect_to_long_url(
    url_hash: FromPath[str], repo: NamedDependency[UrlRepository]
) -> Redirect:
    found = repo.find_by_hash(url_hash)
    if found is None:
        raise NotFoundException(detail=f"No existe la URL corta '{url_hash}'")

    # 301: el navegador puede guardar la redirección y no volver a consultar.
    return Redirect(path=found.long_url, status_code=HTTP_301_MOVED_PERMANENTLY)


def create_app(
    repo: UrlRepository,
    rate_limit_per_minute: int = 60,
    cache_ttl_seconds: int = 300,
) -> Litestar:
    # El límite se aplica por dirección IP del cliente y cubre todas las rutas,
    # incluidas las respuestas que salen del caché.
    rate_limit = RateLimitConfig(rate_limit=("minute", rate_limit_per_minute))

    return Litestar(
        route_handlers=[shorten_url, redirect_to_long_url],
        dependencies={"repo": Provide(lambda: repo, sync_to_thread=False)},
        middleware=[rate_limit.middleware],
        response_cache_config=ResponseCacheConfig(default_expiration=cache_ttl_seconds),
    )
