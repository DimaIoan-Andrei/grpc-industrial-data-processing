# AGENTS.md

## Project context
This project is a proof of concept for integrating heterogeneous industrial data sources into a distributed architecture.

The main purpose of the application is:
- receive raw JSON data from heterogeneous source adapters
- validate and normalize the incoming data into a common internal model
- distribute normalized data to internal services
- detect simple alarms
- persist data in a historian service
- run all components in containers

The primary domain is industrial data integration.
Possible later extensions to other JSON-based domains are allowed only after the industrial flow works end-to-end.

## Architectural interpretation
The simulated sources do NOT represent PLCs or field devices sending HTTP directly.
They represent software adapters / edge connectors / gateways that collect data from heterogeneous industrial sources and forward them to the integration platform.

This means:
- external side = heterogeneous source adapters
- platform entrypoint = ingestion service
- internal platform communication = typed service-to-service communication

## Implementation strategy
Build the system incrementally.
Do NOT generate the whole application at once.

Implementation order must be:

1. simulator / adapter service sends raw data
2. ingestion service receives raw data
3. ingestion validates raw data
4. ingestion normalizes data into a common model
5. historian service stores normalized data
6. alarm service evaluates normalized data
7. internal communication is migrated to gRPC + Protobuf
8. containerization and orchestration are finalized
9. metrics / monitoring are added after the core flow works

## Important constraints
- Keep the implementation simple and feasible.
- Prefer a minimal working end-to-end flow over adding many features.
- Do not introduce unnecessary complexity.
- Do not add UI unless explicitly requested later.
- Do not introduce Kubernetes.
- Do not introduce complex authentication or authorization.
- Do not introduce many databases or advanced infrastructure early.
- Do not refactor unrelated files.
- Do not change project structure unless necessary.

## Communication rules for the coding assistant
When working on this repository:

- Work in very small steps.
- Touch as few files as possible in each task.
- Before making changes, briefly state what files will be created or modified.
- Prefer minimal code that works over large abstractions.
- Preserve the current implementation logic unless asked to refactor.
- Do not add features beyond the current step.
- If something is uncertain, choose the simplest implementation that keeps the architecture valid.

## Code generation rules
- Use Python for all services unless otherwise specified.
- Keep services modular and easy to understand.
- Prefer FastAPI for HTTP services.
- Prefer Pydantic models for request/response validation.
- Use clear folder separation per service.
- Write code that is easy to debug locally.
- Add only essential dependencies.
- Keep function and file names explicit.
- Avoid hidden magic and overly abstract patterns.

## Current step discipline
At any moment, focus only on the current milestone.
Do not start the next milestone until the current one works.

Current expected milestone progression:
- first: ingestion service minimal
- then: connect simulator to ingestion
- then: add normalization
- then: add historian
- then: add alarm service
- then: add gRPC + Protobuf between internal services

## Definition of success for each step
A step is complete only if:
- the service starts correctly
- the intended endpoint or logic works
- the output can be tested locally
- the change is understandable by the project owner

## Scope protection
This repository is primarily about industrial data integration.
Cross-domain extensibility may be demonstrated later, but it must not replace or dilute the industrial proof of concept.

## Style preference
The project owner prefers:
- short explanations
- step-by-step implementation
- explicit and understandable code
- keeping the implementation logic stable across steps