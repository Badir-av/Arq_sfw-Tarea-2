"""Punto de entrada: python -m arch1.shortener"""

import logging
import os

from arch1.shortener.app import create_app
from arch1.shortener.hits import GrpcHitPublisher
from common.repository import UrlRepository
from common.server import run_https

DB_PATH = os.environ.get("SHORTENER_DB", "data/arch1/shortener.db")
LOG_TARGET = os.environ.get("LOG_GRPC_TARGET", "127.0.0.1:50051")
HOST = os.environ.get("SHORTENER_HOST", "127.0.0.1")
PORT = int(os.environ.get("SHORTENER_PORT", "8443"))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    app = create_app(UrlRepository(DB_PATH), GrpcHitPublisher(LOG_TARGET))
    run_https(app, HOST, PORT)
