# LIEM OS Agent System Specifications

This file guides how AI assistants (Cursor, Antigravity) must interact with the LIEM OS codebase.

## CRITICAL EXECUTION RULES
- **DO NOT bypass the Liem OS engine**: Do not write project files or code solutions directly.
- **DO run the engine**: Always invoke `python src/liem_os/main.py` to trigger the multi-agent orchestration for any task execution.
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
