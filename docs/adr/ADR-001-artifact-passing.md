# Architecture Decision Record: ADR-001 - Artifact-based Context Passing

## Context & Problem
Core orchestrator context windows blow up when agents pass raw generated code or bulky outputs in conversation logs, causing high costs and LLM degradation.

## Decision
All agents must write their generated output to `artifacts/objects/` and return a compact reference URI (`artifact://...`) and `restore_pointer`. The orchestrator will only pass references. Sub-agents will explicitly rehydrate dependencies when required.

## Consequences
- Prevents context window explosion.
- Reduces token costs.
- Requires explicit rehydration step for downstream agents.
