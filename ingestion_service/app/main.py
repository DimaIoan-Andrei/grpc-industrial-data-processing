import os
from typing import Any

import grpc
from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import ValidationError
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import Counter
from prometheus_client import generate_latest

from .alarm_grpc_client import evaluate_alarms
from .external_adapters import adapt_external_message
from .historian_grpc_client import send_to_historian
from .models import NormalizedRecord


app = FastAPI(title="Ingestion Service")
EXPECTED_SOURCE_TOKEN = os.getenv("INGESTION_API_TOKEN", "dev-source-token")

records_received_total = Counter(
    "ingestion_records_received_total",
    "Total number of authenticated external records received by ingestion_service.",
)
records_normalized_total = Counter(
    "ingestion_records_normalized_total",
    "Total number of external records successfully normalized by ingestion_service.",
)
auth_failures_total = Counter(
    "ingestion_auth_failures_total",
    "Total number of ingestion_service requests rejected because of missing or invalid source tokens.",
)
historian_requests_total = Counter(
    "ingestion_historian_requests_total",
    "Total number of historian gRPC call attempts made by ingestion_service.",
)
historian_errors_total = Counter(
    "ingestion_historian_errors_total",
    "Total number of historian gRPC call failures seen by ingestion_service.",
)
alarm_requests_total = Counter(
    "ingestion_alarm_requests_total",
    "Total number of alarm gRPC call attempts made by ingestion_service.",
)
alarm_errors_total = Counter(
    "ingestion_alarm_errors_total",
    "Total number of alarm gRPC call failures seen by ingestion_service.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

def process_normalized_record(normalized: NormalizedRecord) -> None:
    try:
        historian_requests_total.inc()
        send_to_historian(normalized)
    except grpc.RpcError as exc:
        historian_errors_total.inc()
        details = exc.details() or str(exc)
        raise HTTPException(
            status_code=502,
            detail=f"Could not store normalized record in historian gRPC service: {details}",
        ) from exc

    try:
        alarm_requests_total.inc()
        alarm_result = evaluate_alarms(normalized)
    except grpc.RpcError as exc:
        alarm_errors_total.inc()
        details = exc.details() or str(exc)
        raise HTTPException(
            status_code=502,
            detail=f"Could not evaluate alarms through alarm gRPC service: {details}",
        ) from exc

    print(
        f"Alarm evaluation for source_id={alarm_result.source_id}: "
        f"{alarm_result.alarm_count} alarm(s)"
    )
    for alarm in alarm_result.alarms:
        print(f"- {alarm.severity} {alarm.code}: {alarm.message}")


@app.post("/ingest/external")
def ingest_external(
    body: dict[str, Any],
    x_source_token: str | None = Header(default=None, alias="X-Source-Token"),
) -> dict[str, str | NormalizedRecord]:
    if x_source_token != EXPECTED_SOURCE_TOKEN:
        auth_failures_total.inc()
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid source token.",
        )

    records_received_total.inc()
    print(body)

    try:
        normalized = adapt_external_message(body)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    records_normalized_total.inc()
    print(normalized)

    process_normalized_record(normalized)

    return {
        "status": "normalized",
        "source_id": normalized.source_id,
        "schema_type": body.get("schema_type", "unknown"),
        "normalized_record": normalized,
    }
