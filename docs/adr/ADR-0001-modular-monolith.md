# ADR-0001: Modular monolith

## Status: Accepted

## Context

The project needs clear application boundaries and a small local deployment.

## Decision

Use a shared Python repository with a FastAPI backend and a separate Streamlit process. Keep configuration and logging in devflow_core.

## Consequences

The UI depends on the HTTP contract. Both processes share one package build.
