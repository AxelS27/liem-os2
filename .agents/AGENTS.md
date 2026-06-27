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

## Documentation Rules
- **Always use Context7 MCP**: Use the Context7 MCP server to fetch current documentation whenever you need information about a library, framework, SDK, API, CLI tool, or cloud service. Always call `resolve-library-id` first, select the best library ID in `/org/project` format, and then call `query-docs` to fetch the docs before answering. Do not rely on web search or internal memory when Context7 can resolve the documentation.
