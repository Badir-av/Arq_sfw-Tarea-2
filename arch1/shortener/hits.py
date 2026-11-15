"""Cliente gRPC que envía los eventos "url hit" al componente Log."""

import logging
from datetime import datetime
from typing import Protocol, runtime_checkable

import grpc

from arch1.proto import url_hit_pb2, url_hit_pb2_grpc

logger = logging.getLogger("shortener_v1.hits")


# runtime_checkable: LiteStar valida las dependencias inyectadas con isinstance.
@runtime_checkable
class HitPublisher(Protocol):
    async def publish(self, timestamp: datetime, short_url: str, long_url: str) -> None: ...

    async def close(self) -> None: ...


class GrpcHitPublisher:
    def __init__(self, target: str, timeout_seconds: float = 2.0) -> None:
        self._target = target
        self._timeout = timeout_seconds
        self._channel: grpc.aio.Channel | None = None
        self._stub: url_hit_pb2_grpc.LogServiceStub | None = None

    def _get_stub(self) -> url_hit_pb2_grpc.LogServiceStub:
        # El canal se crea en el primer uso para que quede asociado al event
        # loop del servidor, y luego se reutiliza en todos los envíos.
        if self._stub is None:
            self._channel = grpc.aio.insecure_channel(self._target)
            self._stub = url_hit_pb2_grpc.LogServiceStub(self._channel)
        return self._stub

    async def publish(self, timestamp: datetime, short_url: str, long_url: str) -> None:
        hit = url_hit_pb2.UrlHit(short_url=short_url, long_url=long_url)
        hit.timestamp.FromDatetime(timestamp)
        try:
            await self._get_stub().RecordUrlHit(hit, timeout=self._timeout)
        except grpc.aio.AioRpcError as exc:
            # La analítica no debe botar la redirección: si el Log no responde,
            # el hit se pierde y queda registrado como advertencia.
            logger.warning(
                "No se pudo registrar el hit de %s: %s (%s)",
                short_url,
                exc.code().name,
                exc.details(),
            )

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
