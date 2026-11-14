# ADR-0003: Alembic migrations

## Status: Accepted

## Context

Schema changes need a reviewable history and repeatable verification.

## Decision

Use Alembic with SQLAlchemy metadata and an explicit upgrade and downgrade for each revision.

## Consequences

Run the migration round-trip on a disposable SQLite file. Deployment applies migrations explicitly.
