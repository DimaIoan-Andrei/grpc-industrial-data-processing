from concurrent import futures
import os

import grpc
from prometheus_client import Counter, start_http_server

from proto.generated import normalized_pb2, normalized_pb2_grpc

from .db import init_db
from .models import NormalizedRecord
from .storage import save_normalized_record


RECORDS_STORED_TOTAL = Counter(
    "historian_records_stored_total",
    "Total normalized records successfully stored by the historian service.",
)
STORE_ERRORS_TOTAL = Counter(
    "historian_store_errors_total",
    "Total normalized record storage errors in the historian service.",
)


class HistorianGrpcService(normalized_pb2_grpc.HistorianServiceServicer):
    def StoreNormalizedRecord(self, request, context):
        record = NormalizedRecord(
            source_id=request.source_id,
            source_type=request.source_type,
            protocol_hint=request.protocol_hint,
            event_time=request.event_time,
            quality=request.quality,
            event_type=request.event_type,
            sequence_no=request.sequence_no,
            measurements=dict(request.measurements),
            attributes=dict(request.attributes),
        )
        try:
            save_normalized_record(record)
        except Exception:
            STORE_ERRORS_TOTAL.inc()
            raise

        RECORDS_STORED_TOTAL.inc()
        return normalized_pb2.StoreNormalizedRecordResponse(
            status="ok",
            message="stored",
        )


def serve() -> None:
    init_db()
    port = os.getenv("HISTORIAN_GRPC_PORT", "50051")
    metrics_port = int(os.getenv("HISTORIAN_METRICS_PORT", "9101"))
    start_http_server(metrics_port)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    normalized_pb2_grpc.add_HistorianServiceServicer_to_server(
        HistorianGrpcService(),
        server,
    )
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"Historian gRPC server listening on port {port}")
    print(f"Historian metrics server listening on port {metrics_port}")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
