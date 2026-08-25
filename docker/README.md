# YouthEscalateBench Container Infrastructure

This directory contains containerization definitions for reproducible evaluation, microservice deployment, and sandboxed benchmarking.

## Subdirectories

- [`docker/evaluator/`](evaluator/README.md): Dockerfile and operational manual for the **HTTP `/predict` Evaluator Service**.
  - Standardized Pydantic `InferenceRequest` ➔ `ModelOutput` contract.
  - Supports `--network none` air-gapped zero-leakage evaluation.
  - Ready for local testing, Kubernetes microservice pods, and competitive benchmark platforms.
