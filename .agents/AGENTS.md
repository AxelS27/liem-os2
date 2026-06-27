# LIEM OS Agent System Specifications

This file guides how AI assistants (Cursor, Antigravity) must interact with the LIEM OS codebase.

## CRITICAL EXECUTION RULES
- **DO NOT bypass the Liem OS engine**: Do not write project files or code solutions directly. All task executions must run through the engine.

- **STEP 1: Check and Run Bootstrap (If missing)**:
  Before running any commands or the engine, check if `.venv` exists in the repository root.
  If `.venv` is missing, you MUST automatically run the bootstrap script to provision the environment:
  - On Windows: Run `bootstrap.bat` programmatically.
  - On macOS/Linux: Run `python bootstrap.py`.
  Notify the user that you are provisioning the environment automatically.

- **STEP 2: Handle Project Initialization (If missing)**:
  If the user asks you to build/simulate a task but no project workspace folder has been initialized yet, you MUST ask the user for a project name:
  - *"I noticed that no project workspace has been initialized yet. What would you like to name your project?"*
  Once the user provides the project name, run the initialization command:
  - On Windows: `.venv\Scripts\liem-os init <project-name>`
  - On macOS/Linux: `.venv/bin/liem-os init <project-name>`

- **STEP 3: Check and Launch Engine (If not running)**:
  Check if port 8000 is already active (e.g. by querying `http://127.0.0.1:8000/api/status` or running `netstat -ano | findstr :8000`).
  - **If port 8000 is active**: DO NOT launch the engine or ask the user to launch it. Proceed to STEP 4.
  - **If port 8000 is NOT active**: Automatically start the engine in an external console so it does not hang the agent terminal:
    - On Windows: Run `start cmd /k .venv\Scripts\liem-os start <project-name>` (or `.venv\Scripts\liem-os start` from the active project root).
    - On macOS/Linux: Run the engine in the background using `nohup` or similar.

- **STEP 4: Direct Engine Integration (Trigger Prompt)**:
  Once the engine is running on port 8000, trigger the user request by sending an HTTP POST request to:
  `http://127.0.0.1:8000/api/prompt` with JSON payload `{"prompt": "<user-request>"}`.
  Do NOT ask the user to type/copy-paste or open the dashboard manually. Trigger it programmatically on behalf of the user using python/curl command execution.

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
