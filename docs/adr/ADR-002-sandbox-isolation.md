# Architecture Decision Record: ADR-002 - Sandbox Tool Isolation

## Context & Problem
Running arbitrary shell commands or write actions directly on the server exposes the system to security vulnerabilities and accidental data deletion.

## Decision
All executor agents must validate execution permissions and target directories against `sandbox/policy.yaml` before running commands. Tool execution is confined to whitelisted paths and has a strict timeout limit of 30 seconds.

## Consequences
- Protects system folders.
- Mitigates shell injection exploits.
- Limits infinite loops in runtime processes.
