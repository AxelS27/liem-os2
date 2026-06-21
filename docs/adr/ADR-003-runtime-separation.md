# Architecture Decision Record: ADR-003 - Separation of Control Plane and Data Plane

## Context & Problem
Mixing planning, task routing, and tool executions in a single monolithic orchestrator process causes scaling bottlenecks and increases SRE complexity.

## Decision
Separate the LIEM runtime into:
- **Control Plane**: Planner, Router, Scheduler, and Validator. Handles cognitive design, queuing, and routing. Never runs tools or writes code.
- **Data Plane**: Executor, Providers, Artifacts, and Sandbox. Handles executing scripts, making API calls, and persisting data. Never plans or decomposes tasks.

## Consequences
- Protects orchestrator from execution faults.
- Allows parallel scaling of executors.
- Forces communication through explicit Pydantic/JSON schemas.
