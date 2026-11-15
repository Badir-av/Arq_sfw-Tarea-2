"""Punto de entrada: python -m arch1.log_service"""

import asyncio
import logging
import os

from arch1.log_service.repository import HitRepository
from arch1.log_service.server import start_server

DB_PATH = os.environ.get("LOG_DB", "data/arch1/log.db")
# Solo escucha en loopback: el Log es un componente interno del nodo de
# despliegue y solo el Shortener v1 debe poder hablarle.
ADDRESS = os.environ.get("LOG_GRPC_ADDRESS", "127.0.0.1:50051")


async def main() -> None:
    server, port = await start_server(HitRepository(DB_PATH), ADDRESS)
    logging.getLogger("log_service").info(
        "Log gRPC escuchando en puerto %s (Log DB: %s)", port, DB_PATH
    )
    try:
        await server.wait_for_termination()
    finally:
        await server.stop(grace=2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
