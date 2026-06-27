# LIEM OS Agent System Specifications

This file guides how AI assistants (Cursor, Antigravity) must interact with the LIEM OS codebase.

## CRITICAL EXECUTION RULES
- **DO NOT bypass the Liem OS engine**: Do not write project files or code solutions directly.
- **DO run the engine in an external console**: Because starting `main.py` launches a web server and a PyWebView desktop GUI, it will HANG indefinitely in a headless terminal. You MUST launch it in a separate external command prompt window using:
  `start cmd /k python src/liem_os/main.py`
- Always use `start cmd /k` for long-running servers or GUI applications to prevent blocking the agent terminal.
- Refer to the individual agent instructions under the `agents/` directory to understand the system roles:
  - User Copilot: [axel.md](file:///d:/Liem OS/agents/axel.md)
  - Core Planner: [planner.md](file:///d:/Liem OS/agents/core/planner.md)
  - Core Router: [router.md](file:///d:/Liem OS/agents/core/router.md)
  - Core Executor: [executor.md](file:///d:/Liem OS/agents/core/executor.md)

## Architecture Details
LIEM OS consists of:
- **Control Plane**: Planner, Router, Scheduler, Validator
- **Data Plane**: Executor, Context Compressor, Recovery Manager
- **Kernel**: Event Loop, Event Bus, VRAM Manager
