import os
import sys
from pathlib import Path

import grpc

from .models import NormalizedRecord

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from proto.generated import normalized_pb2, normalized_pb2_grpc

HISTORIAN_GRPC_TARGET = os.getenv("HISTORIAN_GRPC_TARGET", "localhost:50051")

def send_to_historian(record: NormalizedRecord):
    message = normalized_pb2.NormalizedRecordMessage(
        source_id=record.source_id,
        source_type=record.source_type,
        protocol_hint=record.protocol_hint,
        event_time=record.event_time,
        quality=record.quality,
        event_type=record.event_type,
        sequence_no=record.sequence_no,
        measurements=record.measurements,
        attributes={k: str(v) for k, v in record.attributes.items()},
    )

    with grpc.insecure_channel(HISTORIAN_GRPC_TARGET) as channel:
        stub = normalized_pb2_grpc.HistorianServiceStub(channel)
        return stub.StoreNormalizedRecord(message, timeout=5)
