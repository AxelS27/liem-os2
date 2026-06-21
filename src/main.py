import asyncio
import os
import sys
import logging

# Ensure src/ directory is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from storage.sqlite_db import SQLiteStateRepository
from kernel.event_bus import EventBus
from kernel.vram_manager import VRAMManager
from kernel.event_loop import KernelEventLoop
from kernel.scheduler import CoreScheduler
from kernel.recovery import RecoveryManager
from agents.context import ContextCompressor
from agents.base import LiemBaseAgent

# Set up logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("LiemMain")

async def run_liem_pipeline():
    logger.info("=== INITIALIZING LIEM MULTI-AGENT ORCHESTRATOR ===")
    
    # Paths
    db_path = "runtime/liem.db"
    dummy_code_path = "runtime/finance_tool.py"
    
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
    os.makedirs(os.path.dirname(os.path.abspath(dummy_code_path)), exist_ok=True)
    with open(dummy_code_path, "w", encoding="utf-8") as f:
        f.write('''def calculate_tax(amount):
    return amount * 0.1
''')

    logger.info("[Main] Created dummy agent workspace file: finance_tool.py")

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

if __name__ == "__main__":
    asyncio.run(run_liem_pipeline())
