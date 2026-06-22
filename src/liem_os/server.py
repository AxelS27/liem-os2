import os
import sys
import logging
import asyncio
import re
import urllib.request

def load_dotenv():
    # Look for .env in current directory or project root
    for path in [".env", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")]:
        if os.path.exists(path):
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
active_provider = "antigravity"

provider_telemetry = {
    "antigravity": {
        "total_tokens": 142850,
        "total_cost_usd": 0.21,
        "avg_latency_sec": 1.84,
        "mcp_servers": [
            {"name": "filesystem", "status": "connected"},
            {"name": "github", "status": "connected"},
            {"name": "web-search", "status": "connected"},
            {"name": "context7", "status": "connected"}
        ]
    },
    "claude": {
        "total_tokens": 189120,
        "total_cost_usd": 1.15,
        "avg_latency_sec": 2.15,
        "mcp_servers": [
            {"name": "brave-search", "status": "connected"},
            {"name": "postgres", "status": "connected"},
            {"name": "sequentialthinking", "status": "connected"}
        ]
    },
    "cursor": {
        "total_tokens": 98450,
        "total_cost_usd": 0.45,
        "avg_latency_sec": 1.50,
        "mcp_servers": [
            {"name": "filesystem", "status": "connected"},
            {"name": "interpreter", "status": "connected"}
        ]
    }
}

telemetry_data = {
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

class ProviderRequest(BaseModel):
    provider: str

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
    p_data = provider_telemetry.get(active_provider, provider_telemetry["antigravity"])
    
    # Merge simulated loaded models based on provider
    if active_provider == "antigravity":
        loaded = list(vram_manager.loaded_models.keys())
    elif active_provider == "claude":
        # Simulate Claude model loaded states based on whether system is running
        loaded = ["claude-3-5-sonnet"] if telemetry_data["system_state"] == "running" else []
    else:
        loaded = ["gpt-4o"] if telemetry_data["system_state"] == "running" else []
        
    return {
        "vram_used": vram_manager.get_vram_usage() if active_provider == "antigravity" else (2.4 if loaded else 0.0),
        "vram_limit": vram_manager.limit_gb,
        "loaded_models": loaded,
        "total_tokens": p_data["total_tokens"],
        "total_cost_usd": p_data["total_cost_usd"],
        "avg_latency_sec": p_data["avg_latency_sec"],
        "system_state": telemetry_data["system_state"],
        "logs": telemetry_data["logs"][-50:],  # Return last 50 lines
        "agent_context": telemetry_data["agent_context"],
        "mcp_servers": p_data["mcp_servers"],
        "active_provider": active_provider
    }

@app.post("/api/provider")
async def set_provider(req: ProviderRequest):
    global active_provider
    prov = req.provider.lower()
    if prov not in ["antigravity", "claude", "cursor"]:
        raise HTTPException(status_code=400, detail="Invalid provider")
    
    active_provider = prov
    
    # Add a system log line
    provider_names = {
        "antigravity": "Antigravity",
        "claude": "Claude Desktop",
        "cursor": "Cursor IDE"
    }
    name = provider_names.get(prov, prov.capitalize())
    telemetry_data["logs"].append(f"[Kernel] Switched active provider context to: {name}.")
    
    return {"status": "success", "active_provider": active_provider}

@app.get("/api/tasks")
async def get_tasks():
    # Return all tasks across all executions
    return db.get_active_tasks("exec-100") + db.get_active_tasks("exec-200")

def get_gemini_reply(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    # System instruction context for Axel Copilot
    system_instruction = (
        "You are Axel, the friendly and highly intelligent User Copilot for LIEM OS (a declarative multi-agent orchestrator). "
        "Your role is to guide the user in setting up projects, writing code, running agent simulations, and testing. "
        "Respond in a concise, developer-friendly, and engaging tone. Keep your responses short (under 3-4 sentences if possible) "
        "and mention that the user can ask you to run simulations by describing coding tasks (e.g. 'Build a Stripe payment api'). "
        "Answer in the user's language (if they greet you in Indonesian, respond in Indonesian)."
    )
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"System Context: {system_instruction}\n\nUser: {prompt}"}
                ]
            }
        ]
    }
    
    import json
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = response.read().decode("utf-8")
            res_json = json.loads(res_data)
            reply = res_json["candidates"][0]["content"]["parts"][0]["text"]
            return reply.strip()
    except Exception as e:
        return f"(Gagal menghubungkan ke Gemini API: {e}. Periksa validitas API Key Anda.)"

def parse_skill_metadata(full_path, default_name):
    name = default_name
    description = "Declarative agent skill description."
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
            frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            if frontmatter_match:
                fm = frontmatter_match.group(1)
                name_match = re.search(r"name:\s*\"(.*?)\"", fm) or re.search(r"name:\s*(.*?)\n", fm)
                desc_match = re.search(r"description:\s*\"(.*?)\"", fm) or re.search(r"description:\s*(.*?)\n", fm)
                if name_match:
                    name = name_match.group(1).strip()
                if desc_match:
                    description = desc_match.group(1).strip()
    except Exception:
        pass
    return name, description

def get_declarative_skills():
    skills = []
    
    # 1. Load Global Customizations Root (specifically for Antigravity)
    if active_provider == "antigravity":
        global_skills_dir = os.path.join(os.path.expanduser("~"), ".gemini", "config", "skills")
        if os.path.exists(global_skills_dir) and os.path.isdir(global_skills_dir):
            for item in os.listdir(global_skills_dir):
                item_path = os.path.join(global_skills_dir, item)
                if os.path.isdir(item_path):
                    skill_md = os.path.join(item_path, "SKILL.md")
                    if os.path.exists(skill_md):
                        default_name = item.replace("-", " ").title()
                        name, description = parse_skill_metadata(skill_md, default_name)
                        skills.append({
                            "name": name,
                            "file": f"~/.gemini/config/skills/{item}/SKILL.md",
                            "domain": "GLOBAL CUSTOMIZATION",
                            "description": description
                        })
                        
    # 2. Load Workspace Customizations Root (available to active workspace)
    for base in [os.getcwd(), os.path.dirname(os.getcwd())]:
        workspace_skills_dir = os.path.join(base, ".agents", "skills")
        if os.path.exists(workspace_skills_dir) and os.path.isdir(workspace_skills_dir):
            for item in os.listdir(workspace_skills_dir):
                item_path = os.path.join(workspace_skills_dir, item)
                if os.path.isdir(item_path):
                    skill_md = os.path.join(item_path, "SKILL.md")
                    if os.path.exists(skill_md):
                        default_name = item.replace("-", " ").title()
                        name, description = parse_skill_metadata(skill_md, default_name)
                        skills.append({
                            "name": name,
                            "file": f".agents/skills/{item}/SKILL.md",
                            "domain": "WORKSPACE CUSTOMIZATION",
                            "description": description
                        })
            break
            
    return skills

@app.post("/api/prompt")
async def trigger_prompt(req: PromptRequest):
    logger = logging.getLogger("LiemServer")
    logger.info(f"Received prompt command: {req.prompt}")
    telemetry_data["logs"].append(f"[User] {req.prompt}")
    
    prompt_lower = req.prompt.strip().lower()
    greetings = ["halo", "hello", "hi", "hey", "p", "test", "apa kabar", "siapa kamu", "who are you", "help", "tolong", "siapa"]
    
    # Check if prompt is a short conversational input or greeting
    if any(g in prompt_lower for g in greetings) or len(prompt_lower.split()) < 3:
        async def run_conversational_reply():
            vram_manager.load_model("axel")
            await asyncio.sleep(0.8)
            
            # Query Gemini API if key is set, else use rules fallback
            gemini_reply = get_gemini_reply(req.prompt)
            if gemini_reply:
                reply = f"[Axel] {gemini_reply}"
            else:
                if "siapa" in prompt_lower or "who" in prompt_lower:
                    reply = "[Axel] Saya adalah Axel, User Copilot pendamping kamu di LIEM OS. Tugas saya membantu mendelegasikan tugas ke agent spesialis (seperti Backend Agent, QA Agent, dan DevOps Agent) serta memonitor perkembangannya."
                elif "apa kabar" in prompt_lower or "how are you" in prompt_lower:
                    reply = "[Axel] Saya sangat baik! Seluruh sistem LIEM OS berjalan optimal. VRAM aman, MCP servers terkoneksi, dan saya siap membantu pengerjaan project kamu."
                elif "help" in prompt_lower or "tolong" in prompt_lower:
                    reply = "[Axel] Kamu bisa memerintahkan saya untuk membuat project baru, seperti:\n- 'Buat payment endpoint dengan Stripe'\n- 'Bikin API kalkulator pajak'\n- 'Tolong audit keamanan kode'"
                else:
                    reply = (
                        "[Axel] Halo! Saya mendeteksi percakapan biasa. Untuk mengobrol bebas dengan kecerdasan AI sesungguhnya, "
                        "silakan atur environment variable **`GEMINI_API_KEY`** dengan API key kamu. "
                        "Saat ini, kamu bisa menyuruh saya menjalankan simulasi coding dengan mengetik perintah tugas (misalnya: 'buat billing endpoint')."
                    )
                
            telemetry_data["logs"].append(reply)
            vram_manager.unload_model("axel")
            
        asyncio.create_task(run_conversational_reply())
    else:
        # Trigger the code generation pipeline simulation
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

@app.get("/api/agents")
async def get_agents():
    return [
        {"name": "User Copilot (Axel)", "role": "Copilot & Coordinator", "vram_gb": 1.5, "domain": "Control Plane", "desc": "Handles conversation, decomposing requests, and coordinating agents."},
        {"name": "Core Planner", "role": "Planning Decomposer", "vram_gb": 3.0, "domain": "Control Plane", "desc": "Generates acyclic plan sequences and task dependency graphs."},
        {"name": "Core Router", "role": "Deterministic Resolver", "vram_gb": 1.0, "domain": "Control Plane", "desc": "Maps capabilities to agent skills deterministically using registry maps."},
        {"name": "Core Scheduler", "role": "Lifecycle Coordinator", "vram_gb": 1.0, "domain": "Control Plane", "desc": "Manages execution loops, temperature decays, and loop-breaking thresholds."},
        {"name": "Core Validator", "role": "JSON Schema Asserter", "vram_gb": 1.0, "domain": "Control Plane", "desc": "Asserts payload validity against JSON schemas and manages HITL gates."},
        {"name": "Backend Developer", "role": "Code Implementation", "vram_gb": 4.5, "domain": "Data Plane", "desc": "Implements backend code modules, database endpoints, and core logic."},
        {"name": "QA Tester", "role": "Testing & QA validation", "vram_gb": 2.0, "domain": "Data Plane", "desc": "Executes testing suites, validates code blocks, and asserts convergence."},
        {"name": "DevOps Engineer", "role": "CI/CD & Cloud Provisioning", "vram_gb": 2.0, "domain": "Data Plane", "desc": "Deploys code, builds containers, and manages cloud infrastructure."},
        {"name": "ETL Data Engineer", "role": "Data Pipeline Architect", "vram_gb": 3.0, "domain": "Data Plane", "desc": "Builds ETL pipelines, ensures idempotency, and loads data schemas."}
    ]

@app.get("/api/skills")
async def get_skills():
    return get_declarative_skills()

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
