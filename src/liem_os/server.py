import os
import sys
import logging
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, List

# Ensure src/ is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from liem_os.storage.sqlite_db import SQLiteStateRepository
from liem_os.kernel.event_bus import EventBus
from liem_os.kernel.vram_manager import VRAMManager
from liem_os.kernel.event_loop import KernelEventLoop
from liem_os.kernel.scheduler import CoreScheduler
from liem_os.kernel.recovery import RecoveryManager
from liem_os.agents.context import ContextCompressor

app = FastAPI(title="LIEM OS API Server")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "runtime", "liem.db")
db = SQLiteStateRepository(DB_PATH)
event_bus = EventBus()
vram_manager = VRAMManager(limit_gb=8.0)
kernel = KernelEventLoop(db, event_bus, vram_manager)
scheduler = CoreScheduler(db, event_bus, max_retries=5)
recovery = RecoveryManager(db, event_bus, kernel)
compressor = ContextCompressor()

# Global Telemetry Store
telemetry_data = {
    "total_tokens": 142850,
    "total_cost_usd": 0.21,
    "avg_latency_sec": 1.84,
    "system_state": "idle",
    "logs": [
        "2026-06-22 06:19:00 [Kernel] System standby. Awaiting copilot commands."
    ],
    "agent_context": {
        "axel": 1250,
        "planner": 3520,
        "router": 820,
        "scheduler": 2100,
        "backend_agent": 0,
        "qa_agent": 0,
        "context_compressor": 0
    }
}

class PromptRequest(BaseModel):
    prompt: str

class HITLAction(BaseModel):
    task_id: str
    action: str  # "approve" or "reject"

async def run_pipeline_simulation_task(prompt: str):
    # Setup dummy file for patching
    dummy_file = "finance_tool.py"
    with open(dummy_file, "w", encoding="utf-8") as f:
        f.write("def calculate_tax(amount):\n    return amount * 0.1\n")

    db.save_execution("exec-100", "running", {"objective": prompt})
    
    # Trigger Axel
    vram_manager.load_model("axel")
    telemetry_data["logs"].append("[Axel] Parsing user request and initializing planning graph...")
    await asyncio.sleep(1.0)
    vram_manager.unload_model("axel")

    # Trigger Planner
    vram_manager.load_model("planner")
    telemetry_data["logs"].append("[Planner] Planning graph generated: Task T-001 created.")
    await asyncio.sleep(1.0)
    vram_manager.unload_model("planner")

    # Custom event handler to simulate runs
    async def run_agent(event):
        task_id = event["task_id"]
        agent = event["agent_name"]
        vram_manager.load_model(agent)
        
        task = db.get_task(task_id)
        retry = task["retry_count"]
        
        telemetry_data["logs"].append(f"[{agent}] Executing task {task_id} (Iteration {retry})...")
        await asyncio.sleep(1.5)

        if retry == 0:
            telemetry_data["logs"].append(f"[{agent}] Logic generated. Running validation checks...")
            await scheduler.handle_validation_failure(task_id)
        elif retry == 1:
            telemetry_data["logs"].append(f"[{agent}] Applying AST Node patch...")
            replace_block = """def calculate_tax(amount, rate=0.1):\n    if amount < 0:\n        raise ValueError("Amount cannot be negative")\n    return amount * rate"""
            compressor.apply_ast_injection(dummy_file, "calculate_tax", replace_block)
            telemetry_data["logs"].append(f"[Validator] Validation PASSED. Task T-001 complete.")
            await scheduler.transition_task(task_id, "completed")

    event_bus._listeners["task.status.running"] = [run_agent]

    # Dispatch Task
    await scheduler.dispatch_task(
        task_id="T-001",
        target_agent="backend_agent",
        payload={"objective": "Implement calculate_tax with validation", "file": dummy_file},
        execution_id="exec-100"
    )

@app.on_event("startup")
async def startup_event():
    await kernel.boot()
    # Subscribe to log events to populate live telemetry
    event_bus.subscribe("task.status.running", on_task_running)
    event_bus.subscribe("task.status.completed", on_task_completed)
    event_bus.subscribe("task.status.failed", on_task_failed)
    
    # Run the demo pipeline in the background on startup (wait 1.5s for page to load)
    async def initial_run():
        await asyncio.sleep(1.5)
        await run_pipeline_simulation_task("@axel build a finance calculation tool that handles exceptions.")
        
    asyncio.create_task(initial_run())

async def on_task_running(event: Dict[str, Any]):
    task_id = event["task_id"]
    agent = event["agent_name"]
    msg = f"[Scheduler] Task {task_id} running on agent {agent}."
    telemetry_data["logs"].append(msg)
    telemetry_data["system_state"] = "running"
    telemetry_data["agent_context"][agent] = 8400  # Simulate context loading

async def on_task_completed(event: Dict[str, Any]):
    task_id = event["task_id"]
    agent = event["agent_name"]
    msg = f"[Kernel] Task {task_id} completed successfully by {agent}."
    telemetry_data["logs"].append(msg)
    telemetry_data["system_state"] = "idle"
    telemetry_data["agent_context"][agent] = 0  # Offload context

async def on_task_failed(event: Dict[str, Any]):
    task_id = event["task_id"]
    agent = event["agent_name"]
    msg = f"[Kernel] Task {task_id} failed on agent {agent}."
    telemetry_data["logs"].append(msg)
    telemetry_data["system_state"] = "idle"

@app.get("/api/status")
async def get_status():
    return {
        "vram_used": vram_manager.get_vram_usage(),
        "vram_limit": vram_manager.limit_gb,
        "loaded_models": list(vram_manager.loaded_models.keys()),
        "total_tokens": telemetry_data["total_tokens"],
        "total_cost_usd": telemetry_data["total_cost_usd"],
        "avg_latency_sec": telemetry_data["avg_latency_sec"],
        "system_state": telemetry_data["system_state"],
        "logs": telemetry_data["logs"][-50:],  # Return last 50 lines
        "agent_context": telemetry_data["agent_context"],
        "mcp_servers": [
            {"name": "filesystem", "status": "connected"},
            {"name": "github", "status": "connected"},
            {"name": "web-search", "status": "connected"}
        ]
    }

@app.get("/api/tasks")
async def get_tasks():
    # Return all tasks across all executions
    return db.get_active_tasks("exec-100") + db.get_active_tasks("exec-200")

@app.post("/api/prompt")
async def trigger_prompt(req: PromptRequest):
    logger = logging.getLogger("LiemServer")
    logger.info(f"Received prompt command: {req.prompt}")
    telemetry_data["logs"].append(f"[User] {req.prompt}")
    asyncio.create_task(run_pipeline_simulation_task(req.prompt))
    return {"status": "dispatched", "message": "LIEM OS execution pipeline started."}

@app.post("/api/hitl/action")
async def hitl_action(req: HITLAction):
    logger = logging.getLogger("LiemServer")
    logger.info(f"HITL Action received for task {req.task_id}: {req.action}")
    telemetry_data["logs"].append(f"[HITL] User action: {req.action.upper()} for task {req.task_id}.")
    
    # Resume task or clear snapshot
    db.clear_snapshot(req.task_id)
    return {"status": "success", "message": f"Task {req.task_id} has been resumed with action: {req.action}"}

# Serve Dashboard files
DASHBOARD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard")
if os.path.exists(DASHBOARD_DIR):
    app.mount("/", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")
else:
    @app.get("/")
    async def root():
        return {"message": "LIEM OS API Online. Dashboard files directory not found. Please verify placement under src/liem_os/dashboard/"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
