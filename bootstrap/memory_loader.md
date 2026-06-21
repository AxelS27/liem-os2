# LIEM BOOTSTRAP: MEMORY LOADER

**Objective**: Rehydrates the memory namespaces on startup.
**Steps**:
1. Check for active tenant workspaces in `memory/project/`.
2. Load short-term state vectors into `memory/working/`.
3. Check for indexes integrity in `memory/semantic/` vector DB storage.
