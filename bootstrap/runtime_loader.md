# LIEM BOOTSTRAP: RUNTIME LOADER

**Objective**: Resumes crashed DAG runs and recovers execution states.
**Steps**:
1. Read active runs in `runtime/executions/`.
2. Retrieve state lease locks from `runtime/locks/`.
3. Re-queue tasks marked as `RUNNING` that exceeded their lease time limits.
