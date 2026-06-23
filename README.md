# Distributed microservices-based gRPC architecture for processed and monitored industrial data

This project is a proof-of-concept distributed architecture for processing and monitoring heterogeneous industrial data using Python microservices, gRPC, PostgreSQL, Docker Compose and Prometheus.

The system was developed as part of a master's dissertation project and demonstrates how industrial data from multiple simulated sources can be ingested, normalized, stored, evaluated for alarms and monitored through operational metrics.

## Project Overview

Industrial environments often contain heterogeneous data sources that expose different message structures, naming conventions and data formats. This project addresses that challenge by introducing an ingestion and normalization layer that transforms vendor-specific messages into a common internal model called `NormalizedRecord`.

After normalization, the data is transmitted internally through gRPC to specialized microservices responsible for persistence and alarm evaluation.

## Architecture

The system is composed of the following main services:

* **Simulator Service** – generates heterogeneous industrial JSON messages for multiple simulated sources.
* **Ingestion Service** – receives external HTTP/JSON messages, validates the source token and normalizes incoming data.
* **Historian Service** – stores normalized records in PostgreSQL.
* **Alarm Service** – evaluates alarm rules and stores generated alarm events.
* **PostgreSQL** – stores normalized records and alarm events.
* **Prometheus** – collects operational metrics exposed by the services.

## Data Flow

```text
Industrial Sources / Simulator
        ↓ HTTP/JSON
Ingestion Service
        ↓ gRPC
Historian Service + Alarm Service
        ↓
PostgreSQL

Prometheus monitors the services through /metrics endpoints.
```

## Simulated Industrial Sources

The simulator generates data for several industrial source types:

* Reactor
* Compressor
* Tank
* Pump

Each source uses a different message structure in order to simulate industrial data heterogeneity.

## Normalized Data Model

External messages are transformed into a common internal model named `NormalizedRecord`. This model contains fields such as:

* `source_id`
* `source_type`
* `protocol_hint`
* `event_time`
* `quality`
* `event_type`
* `sequence_no`
* `measurements`
* `attributes`

This approach allows internal services to process data without depending on the original external message structure.

## gRPC Communication

After normalization, the Ingestion Service sends the normalized data to internal services using gRPC and Protocol Buffers.

The main gRPC calls are:

* `StoreNormalizedRecord()` – used to send data to the Historian Service.
* `EvaluateAlarms()` – used to send data to the Alarm Service.

Both calls use a common `NormalizedRecordMessage` structure.

## Alarm Evaluation

The Alarm Service evaluates source-specific rules and generates alarm events when abnormal values are detected.

Examples of alarm types include:

* `HIGH_TEMPERATURE`
* `BAD_DATA_QUALITY`
* `LOW_FLOW`
* `HIGH_VIBRATION`

Generated alarms are persisted in the `alarm_events` table.

## Monitoring

Prometheus is used to monitor the operational behavior of the services.

Examples of exposed metrics include:

* `ingestion_records_received_total`
* `ingestion_records_normalized_total`
* `historian_records_stored_total`
* `alarm_events_generated_total`

These metrics provide visibility into the number of received messages, normalized records, stored records and generated alarms.

## Technologies Used

* Python
* FastAPI
* gRPC
* Protocol Buffers
* PostgreSQL
* Docker Compose
* Prometheus
* SimPy

## Running the Project

Create the environment file:

```bash
cp .env.example .env
```

Start the services:

```bash
docker compose up -d --build
```

Check the running containers:

```bash
docker compose ps
```

Run the simulator:

```bash
docker compose run --rm \
  -e SIMULATION_DURATION_SECONDS=60 \
  -e SIMULATION_REALTIME=true \
  -e SIMULATION_REALTIME_FACTOR=1.5 \
  simulator-service
```

Access Prometheus:

```text
http://localhost:9090
```

## Example API Test

Send a valid external message:

```bash
curl -X POST http://localhost:8000/ingest/external \
  -H "Content-Type: application/json" \
  -H "X-Source-Token: demo-token" \
  --data-binary "@external_pump.json"
```

Send a message with an invalid token:

```bash
curl -X POST http://localhost:8000/ingest/external \
  -H "Content-Type: application/json" \
  -H "X-Source-Token: wrong-token" \
  --data-binary "@external_pump.json"
```

## Database Checks

Check normalized records:

```bash
docker compose exec postgres psql -U postgres -d factory_historian -c "SELECT COUNT(*) FROM normalized_records;"
```

Check alarm events:

```bash
docker compose exec postgres psql -U postgres -d factory_historian -c "SELECT COUNT(*) FROM alarm_events;"
```

Display recent normalized records:

```bash
docker compose exec postgres psql -U postgres -d factory_historian -c "SELECT id, source_id, source_type, quality, event_type FROM normalized_records ORDER BY id DESC LIMIT 5;"
```

Display recent alarm events:

```bash
docker compose exec postgres psql -U postgres -d factory_historian -c "SELECT id, source_id, source_type, alarm_code, severity FROM alarm_events ORDER BY id DESC LIMIT 5;"
```

## Project Scope

This project is a prototype. The industrial sources are simulated, but the software flow is complete:

```text
data generation → ingestion → normalization → gRPC communication → persistence → alarm evaluation → monitoring
```

In a future real-world implementation, the simulated sources could be replaced by actual industrial data sources using protocols such as OPC UA, MQTT or other industrial communication mechanisms through dedicated gateways or adapters.

## Author

Dima Ioan-Andrei

Master's dissertation project – Advanced Software Technologies for Communications.
