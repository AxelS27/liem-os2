# LIEM OS - Core Development and Execution Rules

## Reference Commands
- Run the simulated multi-agent pipeline: `python src/liem_os/main.py`
- Run the FastAPI server: `python -m src.liem_os.server`

## CRITICAL RUNTIME RULES FOR CLAUDE CODE
Whenever the user asks you to build, modify, or simulate anything in this workspace:
1. **YOU MUST NOT write code or files manually** to implement the requested feature.
2. **YOU MUST EXECUTE the Liem OS runner** using `python src/liem_os/main.py` in the terminal first to process the task.
3. If the server is running, you can also interact with the server API (`http://127.0.0.1:8000`).
4. Only after the Liem OS run completes should you inspect the outputs in the workspace and report back to the user.
5. Do not bypass the Liem OS Multi-Agent lifecycle (Kernel, Event Loop, Scheduler, Executor).
