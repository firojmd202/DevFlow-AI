# ADR-0002: SQLite for local development

## Status: Accepted

## Context

Local development needs durable storage with minimal setup.

## Decision

Use SQLite through SQLAlchemy and aiosqlite. Give the API exclusive access to the Compose data volume.

## Consequences

The API owns storage and schema access. Tests use isolated databases.
