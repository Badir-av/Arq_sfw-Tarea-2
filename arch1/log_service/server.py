"""Servidor gRPC del componente Log (arquitectura 1)."""

import asyncio
import logging
from datetime import timezone

import grpc

from arch1.log_service.repository import HitRepository
from arch1.proto import url_hit_pb2, url_hit_pb2_grpc

logger = logging.getLogger("log_service")


class LogServicer(url_hit_pb2_grpc.LogServiceServicer):
    def __init__(self, repo: HitRepository) -> None:
        self._repo = repo

    async def RecordUrlHit(self, request, context):  # noqa: N802 (nombre definido por el .proto)
        timestamp = request.timestamp.ToDatetime(tzinfo=timezone.utc)
        # sqlite3 es bloqueante: se saca del event loop para no frenar otros RPC.
        await asyncio.to_thread(
            self._repo.save, timestamp, request.short_url, request.long_url
        )
        logger.info("hit %s %s -> %s", timestamp.isoformat(), request.short_url, request.long_url)
        return url_hit_pb2.UrlHitAck()


async def start_server(repo: HitRepository, address: str) -> tuple[grpc.aio.Server, int]:
    """Levanta el servidor y devuelve también el puerto real (útil si se pide el 0)."""
    server = grpc.aio.server()
    url_hit_pb2_grpc.add_LogServiceServicer_to_server(LogServicer(repo), server)
    port = server.add_insecure_port(address)
    await server.start()
    return server, port
