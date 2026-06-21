import asyncio
import os
import sys
import logging

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
    liem_home = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
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

def cli_entrypoint():
    import sys
    import shutil
    import urllib.request
    import zipfile
    import io

    if len(sys.argv) < 3 or sys.argv[1] != "init":
        print("Usage: liem-os init <project_name>")
        sys.exit(1)

    project_name = sys.argv[2]
    if os.path.exists(project_name):
        print(f"Error: Folder '{project_name}' already exists.")
        sys.exit(1)

    os.makedirs(project_name)
    print(f"Initializing new LIEM OS project: {project_name}...")

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
        print("Successfully initialized templates from local package source.")
    else:
        # Fallback: Download from GitHub repository
        print("Local templates not found. Downloading from GitHub...")
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
            print("Successfully initialized templates and engine from GitHub repository.")
        except Exception as e:
            print(f"Error downloading templates from GitHub: {e}")
            sys.exit(1)

    # Restructure from package naming if extracted
    # If the user runs python src/main.py, we make sure they have a correct package path
    # by adding an empty __init__.py inside src/liem_os if not present
    init_py = os.path.join(project_name, "src", "liem_os", "__init__.py")
    if os.path.exists(os.path.dirname(init_py)) and not os.path.exists(init_py):
        with open(init_py, "w") as f:
            pass

    print(f"\nProject '{project_name}' successfully initialized!")
    print(f"To run the engine:")
    print(f"  cd {project_name}")
    print(f"  python src/liem_os/main.py")

if __name__ == "__main__":
    import threading
    import webview
    import uvicorn
    from liem_os.server import app

    def start_server():
        # Run uvicorn server silently in a background thread
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

    print("[Main] Starting Dashboard server on http://127.0.0.1:8000 in background...")
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    print("[Main] Launching Native Desktop GUI Application...")
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
    print("[Main] Desktop GUI window closed. Exiting LIEM OS.")
