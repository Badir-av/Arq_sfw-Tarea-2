"""Arranque HTTPS común a ambos Shortener."""

import sys
from pathlib import Path

import uvicorn
from litestar import Litestar

CERTS_DIR = Path(__file__).resolve().parent.parent / "certs"
CERT_FILE = CERTS_DIR / "cert.pem"
KEY_FILE = CERTS_DIR / "key.pem"


def run_https(app: Litestar, host: str, port: int) -> None:
    if not (CERT_FILE.exists() and KEY_FILE.exists()):
        sys.exit(
            "No se encontraron los certificados en certs/. "
            "Genérelos con: python scripts/gen_certs.py"
        )
    uvicorn.run(
        app,
        host=host,
        port=port,
        ssl_certfile=str(CERT_FILE),
        ssl_keyfile=str(KEY_FILE),
    )
