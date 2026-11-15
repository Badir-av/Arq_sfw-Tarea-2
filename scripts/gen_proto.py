"""Regenera los stubs gRPC a partir de arch1/proto/url_hit.proto.

Uso: python scripts/gen_proto.py

Los archivos generados (url_hit_pb2.py y url_hit_pb2_grpc.py) están versionados
en el repositorio; solo hay que volver a correr esto si cambia el .proto.
"""

import sys
from pathlib import Path

import grpc_tools
from grpc_tools import protoc

ROOT = Path(__file__).resolve().parent.parent
PROTO = "arch1/proto/url_hit.proto"


def main() -> int:
    # Se compila desde la raíz del repo para que los imports generados queden
    # como "from arch1.proto import url_hit_pb2", coherentes con el paquete.
    well_known_protos = Path(grpc_tools.__file__).parent / "_proto"
    return protoc.main(
        [
            "grpc_tools.protoc",
            f"-I{ROOT}",
            f"-I{well_known_protos}",
            f"--python_out={ROOT}",
            f"--grpc_python_out={ROOT}",
            str(ROOT / PROTO),
        ]
    )


if __name__ == "__main__":
    sys.exit(main())
