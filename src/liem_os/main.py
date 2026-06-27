import asyncio
import os
import sys
import logging

# Safety overrides for stdout/stderr when run as a windowed (--noconsole) application
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

def load_dotenv():
    # Gather potential search paths for .env
    search_paths = []
    
    # 1. CWD and parent of CWD
    try:
        cwd = os.getcwd()
        search_paths.append(os.path.join(cwd, ".env"))
        search_paths.append(os.path.join(os.path.dirname(cwd), ".env"))
    except Exception:
        pass

    # 2. Executable / Entry script location and its parent
    try:
        if sys.argv and sys.argv[0]:
            script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            search_paths.append(os.path.join(script_dir, ".env"))
            search_paths.append(os.path.join(os.path.dirname(script_dir), ".env"))
    except Exception:
        pass
        
    try:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        search_paths.append(os.path.join(exe_dir, ".env"))
        search_paths.append(os.path.join(os.path.dirname(exe_dir), ".env"))
    except Exception:
        pass

    # 3. Source file relative path (three directories up from this file)
    try:
        file_dir = os.path.dirname(os.path.abspath(__file__))
        search_paths.append(os.path.join(file_dir, ".env"))
        search_paths.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(file_dir))), ".env"))
    except Exception:
        pass

    # Deduplicate paths
    seen = set()
    unique_paths = []
    for p in search_paths:
        abs_p = os.path.abspath(p)
        if abs_p not in seen:
            seen.add(abs_p)
            unique_paths.append(abs_p)

    # Load from the first matching .env file
    for path in unique_paths:
        if os.path.exists(path) and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, val = line.split("=", 1)
                            key = key.strip()
                            val = val.strip().strip('"').strip("'")
                            os.environ[key] = val
                break
            except Exception:
                pass

load_dotenv()

# Add src/ directory to sys.path to allow absolute imports of liem_os package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from liem_os.storage.sqlite_db import SQLiteStateRepository
from liem_os.kernel.event_bus import EventBus
from liem_os.kernel.vram_manager import VRAMManager
from liem_os.kernel.event_loop import KernelEventLoop
from liem_os.kernel.scheduler import CoreScheduler
from liem_os.kernel.recovery import RecoveryManager
from liem_os.agents.context import ContextCompressor
from liem_os.agents.base import LiemBaseAgent

# Set up logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("LiemMain")

async def run_liem_pipeline():
    logger.info("=== INITIALIZING LIEM MULTI-AGENT ORCHESTRATOR ===")
    
    # Resolve LIEM_HOME (the liem-os/ subdirectory root)
    def get_liem_home():
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            if os.path.basename(exe_dir).lower() == "dist":
                return os.path.dirname(exe_dir)
            return exe_dir
        else:
            file_dir = os.path.dirname(os.path.abspath(__file__))
            return os.path.dirname(os.path.dirname(os.path.dirname(file_dir)))
            
    liem_home = get_liem_home()
    
    # Internal state store database lives inside liem-os/runtime/
    db_path = os.path.join(liem_home, "runtime", "liem.db")
    
    # Project application workspace file lives in the current working directory (e.g. Ecommerce-website root)
    dummy_code_path = "finance_tool.py"
    
    # Clean old run files
    if os.path.exists(db_path):
        os.remove(db_path)
    if os.path.exists(dummy_code_path):
        os.remove(dummy_code_path)

    # Initialize components
    db = SQLiteStateRepository(db_path)
    event_bus = EventBus()
    vram_manager = VRAMManager(limit_gb=8.0)
    kernel = KernelEventLoop(db, event_bus, vram_manager)
    scheduler = CoreScheduler(db, event_bus, max_retries=5)
    recovery = RecoveryManager(db, event_bus, kernel)
    compressor = ContextCompressor()

    # Create dummy files simulating agent workspace
    with open(dummy_code_path, "w", encoding="utf-8") as f:
        f.write('''def calculate_tax(amount):
    return amount * 0.1
''')

    logger.info(f"[Main] Created dummy agent workspace file: {os.path.abspath(dummy_code_path)}")

    # Boot the system
    await kernel.boot()

    # Step 1: User copilot Axel receives the request
    logger.info("\n--- STEP 1: USER CONVERSATION GATEWAY ---")
    vram_manager.load_model("axel")
    logger.info("[Axel] User request: '@axel build a finance calculation tool that handles exceptions.'")
    vram_manager.unload_model("axel")

    # Step 2: Planner maps the request to a task graph
    logger.info("\n--- STEP 2: WORK UNIT DECOMPOSITION & PLANNING ---")
    vram_manager.load_model("planner")
    logger.info("[Planner] Decomposed plan: Task 'T-001' (Write tax logic) -> Task 'T-002' (Validate tax logic).")
    vram_manager.unload_model("planner")

    # Step 3: Router maps capabilities
    logger.info("\n--- STEP 3: CAPABILITY ROUTING ---")
    vram_manager.load_model("router")
    logger.info("[Router] Routing task 'T-001' to 'backend_agent' based on capabilities.yaml.")
    vram_manager.unload_model("router")

    # Step 4: Execution & State Transitions with Loop Breakers
    logger.info("\n--- STEP 4: REACTIVE RUNTIME CYCLE (WITH RETRIES) ---")
    
    # Save the execution run
    db.save_execution("exec-100", "running", {"objective": "build finance tool"})

    # Setup custom event handler for simulated runs
    async def run_agent_execution(event):
        task_id = event["task_id"]
        agent = event["agent_name"]
        
        # Load the agent to VRAM
        vram_manager.load_model(agent)
        
        task = db.get_task(task_id)
        retry_count = task["retry_count"]
        temp = task["temperature"]

        logger.info(f"[{agent}] Executing task {task_id} (Retry: {retry_count}, Temp: {temp:.2f})...")

        if retry_count == 0:
            # First attempt: Simulated code has validation failure
            logger.warning(f"[{agent}] Generated logic written to {dummy_code_path}. Running unit tests...")
            # Simulate a validation fail trigger from the QA validator agent
            await scheduler.handle_validation_failure(task_id)
        elif retry_count == 1:
            # Second attempt: Decayed temperature forces deterministic fixes. We use AST Node injection!
            logger.info(f"[{agent}] Using decayed temperature for strict bug-fixing. Emitting AST Node ID patch...")
            
            replace_block = """def calculate_tax(amount, rate=0.1):
    if amount < 0:
        raise ValueError("Amount cannot be negative")
    return amount * rate"""
            
            # Apply AST Node ID Injection
            success = compressor.apply_ast_injection(
                file_path=dummy_code_path,
                ast_node_id="calculate_tax",
                replace_block=replace_block
            )
            
            if success:
                logger.info(f"[{agent}] AST patch applied. Re-running QA validation...")
                # Verify code content
                with open(dummy_code_path, "r", encoding="utf-8") as f:
                    updated_code = f.read()
                logger.info(f"[Validator] Checked {dummy_code_path}. Current file content:\n{updated_code}")
                logger.info("[Validator] Validation PASSED. Emitters complete.")
                await scheduler.transition_task(task_id, "completed")
            else:
                await scheduler.handle_validation_failure(task_id)

    event_bus.subscribe("task.status.running", run_agent_execution)

    # Dispatch Task T-001
    await scheduler.dispatch_task(
        task_id="T-001",
        target_agent="backend_agent",
        payload={"objective": "Implement calculate_tax with exceptions", "file": dummy_code_path},
        execution_id="exec-100"
    )

    # Let the async events run
    await asyncio.sleep(0.5)

    # Step 5: Simulate Loop Breaker Escalation to Recovery
    logger.info("\n--- STEP 5: SIMULATING UNHAPPY LOOP ESCALATION ---")
    # Dispatch a new task that will repeatedly fail validation to trigger the loop breaker limit (5)
    db.save_execution("exec-200", "running", {"objective": "faulty logic execution"})
    
    async def run_failing_agent(event):
        task_id = event["task_id"]
        agent = event["agent_name"]
        logger.info(f"[{agent}] Executing task {task_id} that constantly fails...")
        await scheduler.handle_validation_failure(task_id)

    event_bus.subscribe("task.status.running_fail", run_failing_agent)
    
    # We alter subscription for this specific test task to route it to run_failing_agent
    # instead of the general run_agent_execution handler
    async def route_runner(event):
        if event["task_id"] == "T-999":
            await run_failing_agent(event)
        else:
            await run_agent_execution(event)
            
    # Unsubscribe old and subscribe router
    event_bus._listeners["task.status.running"] = [route_runner]

    await scheduler.dispatch_task(
        task_id="T-999",
        target_agent="qa_agent",
        payload={"objective": "Test loop limits"},
        execution_id="exec-200"
    )

    # Let the loops run and exceed the 5 iterations threshold
    await asyncio.sleep(0.5)

    # Shutdown Kernel
    logger.info("\n--- STEP 6: GRACEFUL SHUTDOWN ---")
    await kernel.shutdown()
    logger.info("=== LIEM ENGINE EXECUTION COMPLETE ===")

def start_engine():
    import threading
    import webview
    import uvicorn
    from liem_os.server import app

    # ANSI Colors
    CYAN = ""
    GREEN = ""
    RESET = ""
    
    # Enable Windows ANSI support using ctypes
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            CYAN = "\033[36m"
            GREEN = "\033[32m"
            RESET = "\033[0m"
        except:
            pass
    else:
        CYAN = "\033[36m"
        GREEN = "\033[32m"
        RESET = "\033[0m"

    print(f"\n{CYAN}==================================================")
    print("   __    _  ____  __  ___    ____  ____")
    print("  / /   / |/ /  |/  |/ _ \\  / __ \\/ __/")
    print(" / /__ /    / /|_/ /  __ / / /_/ /\\ \\  ")
    print("/____//_/|_/_/  /_/_/      \\____/___/  ")
    print(f"=================================================={RESET}")

    print(f"{GREEN}[Liem OS] Starting Dashboard server on http://127.0.0.1:8000 in background...{RESET}")
    
    def start_server():
        # Run uvicorn server silently in a background thread
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    print(f"{GREEN}[Liem OS] Launching Native Desktop GUI Application...{RESET}")
    # Open pywebview native desktop window loading the FastAPI root
    webview.create_window(
        title="LIEM OS - Enterprise Multi-Agent Orchestrator",
        url="http://127.0.0.1:8000/",
        width=1280,
        height=800,
        resizable=True,
        min_size=(1024, 768)
    )
    # Start the desktop window loop (blocks until window is closed)
    webview.start()
    print(f"{GREEN}[Liem OS] Desktop GUI window closed. Exiting LIEM OS.{RESET}")

def cli_entrypoint():
    import sys
    import shutil
    import urllib.request
    import zipfile
    import io

    # ANSI Colors (High-contrast for both light/white and dark backgrounds)
    CYAN = ""
    GREEN = ""
    MAGENTA = ""
    RED = ""
    RESET = ""
    
    # Enable Windows ANSI support using ctypes
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # Enable ENABLE_PROCESSED_OUTPUT (1) and ENABLE_VIRTUAL_TERMINAL_PROCESSING (4)
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            CYAN = "\033[36m"
            GREEN = "\033[32m"
            MAGENTA = "\033[35m"
            RED = "\033[31m"
            RESET = "\033[0m"
        except:
            pass
    else:
        CYAN = "\033[36m"
        GREEN = "\033[32m"
        MAGENTA = "\033[35m"
        RED = "\033[31m"
        RESET = "\033[0m"

    if len(sys.argv) < 2:
        print(f"Usage: {CYAN}liem-os [init <project-name> | start]{RESET}")
        sys.exit(1)

    command = sys.argv[1]
    if command == "start":
        start_engine()
        sys.exit(0)

    if command != "init":
        print(f"Unknown command: {command}. Usage: {CYAN}liem-os [init <project-name> | start]{RESET}")
        sys.exit(1)

    if len(sys.argv) < 3:
        print(f"Usage: {CYAN}liem-os init <project-name>{RESET}")
        sys.exit(1)

    project_name = sys.argv[2]
    if os.path.exists(project_name):
        print(f"{RED}Error: Folder '{project_name}' already exists.{RESET}")
        sys.exit(1)

    # Print Liem OS welcome ASCII art in cyan
    art = r"""
.----------------------------------------.
|                                        |
|   _    ___ ___ __  __       ___  ___   |
|  | |  |_ _| __|  \/  |     / _ \/ __|  |
|  | |__ | || _|| |\/| |    | (_) \__ \  |
|  |____|___|___|_|  |_|     \___/|___/  |
|                                        |
'----------------------------------------'"""
    print(f"\n{CYAN}{art}{RESET}")

    os.makedirs(project_name)
    print(f"{GREEN}Initializing new LIEM OS project: {project_name}...{RESET}")

    # Folders to copy
    folders = ["kernel", "agents", "schemas", "registry", "sandbox", "src"]

    # Try copying from local installation source
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    copied_locally = True
    for f in folders:
        src_path = os.path.join(base_path, f)
        if not os.path.exists(src_path):
            copied_locally = False
            break

    if copied_locally:
        for f in folders:
            src_path = os.path.join(base_path, f)
            dest_path = os.path.join(project_name, f)
            shutil.copytree(src_path, dest_path)
        print(f"{GREEN}Successfully initialized templates from local package source.{RESET}")
    else:
        # Fallback: Download from GitHub repository
        print(f"{MAGENTA}Local templates not found. Downloading from GitHub...{RESET}")
        url = "https://github.com/AxelS27/liem-os2/archive/refs/heads/main.zip"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                zip_data = response.read()
            
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
                for member in zip_ref.namelist():
                    parts = member.split('/')
                    if len(parts) > 1 and parts[1] in folders:
                        relative_path = '/'.join(parts[1:])
                        if relative_path.strip():
                            dest_path = os.path.join(project_name, relative_path)
                            if member.endswith('/'):
                                os.makedirs(dest_path, exist_ok=True)
                            else:
                                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                                with open(dest_path, "wb") as out_f:
                                    out_f.write(zip_ref.read(member))
            print(f"{GREEN}Successfully initialized templates and engine from GitHub repository.{RESET}")
        except Exception as e:
            print(f"{RED}Error downloading templates from GitHub: {e}{RESET}")
            sys.exit(1)

    # Restructure from package naming if extracted
    # If the user runs python src/main.py, we make sure they have a correct package path
    # by adding an empty __init__.py inside src/liem_os if not present
    init_py = os.path.join(project_name, "src", "liem_os", "__init__.py")
    if os.path.exists(os.path.dirname(init_py)) and not os.path.exists(init_py):
        with open(init_py, "w") as f:
            pass

    # Automatically initialize GitHub Spec Kit in the new project
    print(f"\n{CYAN}[Liem OS] Integrating Spec-Driven Development (GitHub Spec Kit)...{RESET}")
    try:
        import subprocess
        # Try running using current python binary + module specify_cli
        cmd = [sys.executable, "-m", "specify_cli", "init", "--here", "--integration", "claude", "--integration", "gemini", "--script", "ps", "--ignore-agent-tools", "--force"]
        result = subprocess.run(
            cmd,
            cwd=project_name,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"{GREEN}[Liem OS] Successfully initialized Spec Kit templates, constitution, and agent skills!{RESET}")
        else:
            # Fallback to standalone specify command
            cmd_fallback = ["specify", "init", "--here", "--integration", "claude", "--integration", "gemini", "--script", "ps", "--ignore-agent-tools", "--force"]
            result_fallback = subprocess.run(
                cmd_fallback,
                cwd=project_name,
                capture_output=True,
                text=True
            )
            if result_fallback.returncode == 0:
                print(f"{GREEN}[Liem OS] Successfully initialized Spec Kit templates, constitution, and agent skills!{RESET}")
            else:
                print(f"{MAGENTA}[Liem OS] Warning: Could not initialize Spec Kit automatically: {result.stderr or result_fallback.stderr}{RESET}")
    except Exception as e:
        print(f"{MAGENTA}[Liem OS] Warning: Could not initialize Spec Kit automatically: {e}{RESET}")

    # Generate 1-click batch script for Windows (run.bat)
    run_bat_content = """@echo off
title LIEM OS Engine
echo [Liem OS] Launching visual dashboard and orchestrator...
..\\.venv\\Scripts\\python.exe src\\liem_os\\main.py start
if %errorlevel% neq 0 (
    echo [Liem OS] Error: Could not launch engine.
    pause
)
"""
    try:
        with open(os.path.join(project_name, "run.bat"), "w", encoding="utf-8") as f:
            f.write(run_bat_content)
    except Exception as e:
        print(f"{MAGENTA}Warning: Could not create run.bat: {e}{RESET}")

    # Generate 1-click shell script for Unix/macOS (run.sh)
    run_sh_content = """#!/bin/bash
echo "[Liem OS] Launching visual dashboard and orchestrator..."
../.venv/bin/python src/liem_os/main.py start
"""
    try:
        sh_path = os.path.join(project_name, "run.sh")
        with open(sh_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(run_sh_content)
        # Make the shell script executable
        os.chmod(sh_path, 0o755)
    except Exception as e:
        print(f"{MAGENTA}Warning: Could not create run.sh: {e}{RESET}")

    # Print beautiful, colorized CLI Card
    if os.name == 'nt':
        card = f"""
{GREEN}.------------------------------------------------------------.
|                                                            |
|  {GREEN}SUCCESS:{RESET} Project '{CYAN}{project_name}{RESET}' initialized successfully!
|                                                            |
|  To launch the visual dashboard & orchestrator:            |
|                                                            |
|  {MAGENTA}[Option A] 1-Click Launch (Windows Explorer){RESET}         |
|  -> Double-click the {CYAN}run.bat{RESET} file inside the project folder. |
|                                                            |
|  {MAGENTA}[Option B] Terminal Command{RESET}                           |
|  -> {CYAN}cd {project_name}{RESET}                                         |
|  -> {CYAN}..\\.venv\\Scripts\\liem-os start{RESET}                      |
|                                                            |
'------------------------------------------------------------'{RESET}"""
    else:
        card = f"""
{GREEN}.------------------------------------------------------------.
|                                                            |
|  {GREEN}SUCCESS:{RESET} Project '{CYAN}{project_name}{RESET}' initialized successfully!
|                                                            |
|  To launch the visual dashboard & orchestrator:            |
|                                                            |
|  {MAGENTA}[Option A] Terminal Launch{RESET}                           |
|  -> {CYAN}cd {project_name}{RESET}                                         |
|  -> {CYAN}./run.sh{RESET}                                                |
|                                                            |
|  {MAGENTA}[Option B] Direct CLI Command{RESET}                        |
|  -> {CYAN}cd {project_name}{RESET}                                         |
|  -> {CYAN}../.venv/bin/liem-os start{RESET}                             |
|                                                            |
'------------------------------------------------------------'{RESET}"""
    
    print(card)

if __name__ == "__main__":
    start_engine()
