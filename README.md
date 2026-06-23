# gRPC Industrial Data Processing Microservices

This project is a proof-of-concept distributed architecture for processing and monitoring heterogeneous industrial data using Python microservices, gRPC, PostgreSQL, Docker Compose and Prometheus.

## Overview

The system simulates industrial data sources such as reactor, compressor, tank and pump. External messages are received by an Ingestion Service, normalized into a common `NormalizedRecord` model and transmitted internally through gRPC to specialized services.

## Main Components

- **Simulator Service** – generates heterogeneous industrial JSON messages.
- **Ingestion Service** – receives external HTTP/JSON messages, validates the source token and normalizes data.
- **Historian Service** – stores normalized records in PostgreSQL.
- **Alarm Service** – evaluates alarm rules and stores alarm events.
- **Prometheus** – collects operational metrics from the services.
- **PostgreSQL** – stores normalized records and alarm events.

## Technologies

- Python
- FastAPI
- gRPC
- Protocol Buffers
- PostgreSQL
- Docker Compose
- Prometheus
- SimPy

## Architecture Flow

```text
Industrial sources / Simulator
        ↓ HTTP/JSON
Ingestion Service
        ↓ gRPC
Historian Service + Alarm Service
        ↓
PostgreSQL

Prometheus monitors the services through /metrics endpoints.
