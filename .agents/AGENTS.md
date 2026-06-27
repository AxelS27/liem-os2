# LIEM OS Agent System Specifications

This file guides how AI assistants (Cursor, Antigravity) must interact with the LIEM OS codebase.

## CRITICAL EXECUTION RULES
- **DO NOT bypass the Liem OS engine**: Do not write project files or code solutions directly.
- **Check if the engine is already running FIRST**: Before launching the engine or asking the user to run it, check if port 8000 (default dashboard port) is already active (e.g. by trying to query `http://127.0.0.1:8000/api/status` or running a check command like `netstat -ano | findstr :8000` on Windows). If it is already running, **DO NOT** launch it again or ask the user to start it. Instead, proceed directly to working with the running engine server.
- **DO run the engine in an external console (only if NOT running)**: If and only if the engine is not active, launch it in a separate external command prompt window using:
  `start cmd /k python src/liem_os/main.py`
- Always use `start cmd /k` for long-running servers or GUI applications to prevent blocking the agent terminal.
- Refer to the individual agent instructions under the `agents/` directory to understand the system roles:
  - User Copilot: [axel.md](file:///d:/Liem OS/agents/axel.md)
  - Core Planner: [planner.md](file:///d:/Liem OS/agents/core/planner.md)
  - Core Router: [router.md](file:///d:/Liem OS/agents/core/router.md)
  - Core Executor: [executor.md](file:///d:/Liem OS/agents/core/executor.md)
- **Direct Engine Integration (DO NOT ask user to type/copy-paste to Axel)**: If the engine/server is running on port 8000, you (Antigravity) MUST trigger the task execution directly by sending an HTTP POST request to the running server:
  `http://127.0.0.1:8000/api/prompt` with JSON payload `{"prompt": "<user-request>"}`.
  Do not ask the user to open the dashboard and type the request manually. Trigger it programmatically on behalf of the user using python/curl command execution.

## Architecture Details
LIEM OS consists of:
- **Control Plane**: Planner, Router, Scheduler, Validator
- **Data Plane**: Executor, Context Compressor, Recovery Manager
- **Kernel**: Event Loop, Event Bus, VRAM Manager

## Documentation Rules
- **Always use Context7 MCP**: Use the Context7 MCP server to fetch current documentation whenever you need information about a library, framework, SDK, API, CLI tool, or cloud service. Always call `resolve-library-id` first, select the best library ID in `/org/project` format, and then call `query-docs` to fetch the docs before answering. Do not rely on web search or internal memory when Context7 can resolve the documentation.
