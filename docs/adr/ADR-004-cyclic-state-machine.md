# Architecture Decision Record: ADR-004 - Cyclic State Machine, Decaying Temperature, and Loop Breakers

## Context & Problem
Static DAGs are acyclic and cannot handle iteration loops (e.g. Code ➔ Test ➔ Fail ➔ Re-Code) efficiently. Re-initializing new DAGs on each failure adds massive planning overhead. However, allowing unrestricted cyclic state transitions can lead to infinite loops, burning compute cycles and API tokens.

## Decision
- Migrate the LIEM scheduler from a static DAG to a LangGraph-style **Reactive State Machine**.
- Implement **Decaying Temperature**: On each cyclic loop back (e.g. from `VALIDATING` to `RUNNING`), decay the model temperature parameter by `0.15` (calculated as `T_new = max(0.0, T_initial - (i * 0.15))`). This increases the determinism of subsequent LLM code generation runs, guiding the model toward strict convergence.
- Implement **Max_Retry Loop Breakers**: Enforce a hard loop limit of 5 retries.
- **Escalation Path**: If the limit of 5 retries is breached, transition the task to `FAILED` and escalate via the `Recovery Manager` (using model fallback, HITL manual patching via Axel, or graph re-planning).

## Consequences
- Enables native, iterative development loops without planning overhead.
- Prevents infinite loop resource leaks.
- Guarantees eventual convergence or clean escalation for stuck agents.
- Slightly reduces creative/exploratory variation on later iterations (which is desired during bug-fixing phases).
