# Architecture Decision Record: ADR-007 - Model Offloading and Dynamic VRAM Management

## Context & Problem
Running multiple concurrent LLM agents on local hardware (e.g., consumer GPU with 8GB VRAM) triggers Out of Memory (OOM) errors during context switching between Planner, Router, Scheduler, and Executor pipelines, especially when running async tasks.

## Decision
- Enforce a strict **Scale-to-Zero VRAM policy** coordinated by the Runtime Kernel.
- When an agent's execution transitions to `WAITING` (HITL confirmation phase), `PAUSED`, or `SUSPENDED` states, the Kernel invokes the `vram_manager.unload_model()` interface to explicitly evict model weights from GPU memory to host RAM.
- The model weights are only loaded back to GPU memory via `vram_manager.load_model()` when the task state transitions to `RUNNING`.
- Queue task execution blocks if concurrent model footprints exceed 90% VRAM allocation limits.

## Consequences
- Enables execution of complex multi-agent pipelines on standard consumer hardware (e.g., RTX 4060).
- Prevents OOM crashes.
- Introduces minimal cold-start latency when reloading models into VRAM (typically 2-4 seconds depending on host PCIe and RAM bandwidth).

