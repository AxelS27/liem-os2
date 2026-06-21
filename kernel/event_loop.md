# LIEM RUNTIME KERNEL: EVENT LOOP

**Objective**: The central processor owning the lifecycle of the system, implementing Model Offloading and Pub/Sub event loops.
**Activation**: Act as Liem Kernel Engine.

---

## RUNTIME CORE PROTOCOLS

### 1. Model Offloading & Dynamic VRAM Allocation (Scale-to-Zero)
- **Local VRAM Constraints**: To run multiple agents concurrently on local GPUs (e.g., 8GB VRAM on RTX 4060) without Out of Memory (OOM) errors, enforce a strict **Scale-to-Zero VRAM policy**:
  - When an agent's state transitions to `WAITING` (waiting for HITL approval), `PAUSED`, or `SUSPENDED` (Scale-to-Zero active), the Kernel must explicitly invoke the `vram_manager.unload_model(model_name)` API.
  - This API commands the underlying LLM provider engine (e.g. Ollama with `keep_alive: 0`, llama.cpp server model unload endpoint, or PyTorch CPU offloading via `.to('cpu')` and `torch.cuda.empty_cache()`) to free up GPU memory.
  - The model weights are reloaded into GPU memory via `vram_manager.load_model(model_name, device="cuda")` only when the Scheduler wakes up the agent and sets its task status to `RUNNING`.
  - The Kernel schedules slots dynamically, queuing agent executions if VRAM usage exceeds a configurable safety threshold (e.g., 90% of total VRAM).

### 2. Event-Driven Pub/Sub (Consolidation Gate)
- **No polling**: To eliminate CPU-wasting database polling loops (polling SQLite/WAL logs constantly), the system uses an Event-Driven Pub/Sub pattern via an internal Event Bus or WebSocket/IPC loop.
- **Trigger Sequence**:
  - The Executor runs a work unit, completes it, and writes the state transition (e.g., `COMPLETE`, `FAILED`) to the Write-Ahead Logging (WAL) database.
  - Immediately upon database commit, the Executor publishes a `task.status.completed` or `task.status.failed` event onto the Event Bus.
  - The Event Bus catches the message and instantly invokes the Scheduler's event handler. This wakes up the Scheduler thread to process the next step of the state graph without latency or database polling.

