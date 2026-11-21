"""Shortener v1: redirección temporal (302) + evento "url hit" por gRPC."""

from datetime import datetime, timezone

from litestar import Litestar, Request, get
from litestar.background_tasks import BackgroundTask
from litestar.di import NamedDependency, Provide
from litestar.exceptions import NotFoundException
from litestar.params import FromPath
from litestar.response import Redirect
from litestar.status_codes import HTTP_302_FOUND

from arch1.shortener.hits import HitPublisher
from common.api import shorten_url
from common.repository import UrlRepository


@get("/{url_hash:str}", sync_to_thread=True)
def redirect_to_long_url(
    url_hash: FromPath[str],
    repo: NamedDependency[UrlRepository],
    hits: NamedDependency[HitPublisher],
    request: Request,
) -> Redirect:
    found = repo.find_by_hash(url_hash)
    if found is None:
        raise NotFoundException(detail=f"No existe la URL corta '{url_hash}'")

    # El hit se envía después de responder para mantener la llamada al Log
    # fuera de la latencia de la redirección.
    return Redirect(
        path=found.long_url,
        status_code=HTTP_302_FOUND,
        headers={"Cache-Control": "no-store"},
        background=BackgroundTask(
            hits.publish,
            timestamp=datetime.now(timezone.utc),
            short_url=str(request.url),
            long_url=found.long_url,
        ),
    )


def create_app(repo: UrlRepository, hits: HitPublisher) -> Litestar:
    return Litestar(
        route_handlers=[shorten_url, redirect_to_long_url],
        dependencies={
            "repo": Provide(lambda: repo, sync_to_thread=False),
            "hits": Provide(lambda: hits, sync_to_thread=False),
        },
        on_shutdown=[hits.close],
    )
