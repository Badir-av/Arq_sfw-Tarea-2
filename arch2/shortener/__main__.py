"""Punto de entrada: python -m arch2.shortener"""

import os

from arch2.shortener.app import create_app
from common.repository import UrlRepository
from common.server import run_https

DB_PATH = os.environ.get("SHORTENER_DB", "data/arch2/shortener.db")
HOST = os.environ.get("SHORTENER_HOST", "127.0.0.1")
PORT = int(os.environ.get("SHORTENER_PORT", "8444"))
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "300"))

if __name__ == "__main__":
    app = create_app(
        UrlRepository(DB_PATH),
        rate_limit_per_minute=RATE_LIMIT_PER_MINUTE,
        cache_ttl_seconds=CACHE_TTL_SECONDS,
    )
    run_https(app, HOST, PORT)
