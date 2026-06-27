import os
import sys
import logging
import asyncio
import re
import urllib.request

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
from liem_os.kernel.security import SkillSpectorScanner

app = FastAPI(title="LIEM OS API Server")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve LIEM HOME directory
def get_liem_home():
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if os.path.basename(exe_dir).lower() == "dist":
            return os.path.dirname(exe_dir)
        return exe_dir
    else:
        file_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(os.path.dirname(os.path.dirname(file_dir)))

LIEM_HOME = get_liem_home()
DB_PATH = os.path.join(LIEM_HOME, "runtime", "liem.db")
db = SQLiteStateRepository(DB_PATH)
event_bus = EventBus()
vram_manager = VRAMManager(limit_gb=8.0)
kernel = KernelEventLoop(db, event_bus, vram_manager)
scheduler = CoreScheduler(db, event_bus, max_retries=5)
recovery = RecoveryManager(db, event_bus, kernel)
compressor = ContextCompressor()

# Settings persistence
SETTINGS_PATH = os.path.join(LIEM_HOME, "runtime", "settings.json")

def load_settings():
    import json
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_settings(settings_data):
    import json
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings_data, f, indent=4)
    except Exception:
        pass

settings = load_settings()
active_provider = settings.get("active_provider", "antigravity")

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

# Real session telemetry (in-memory)
session_tokens = 0
session_cost_usd = 0.0

def track_usage(tokens: int, cost: float, is_task: bool = False):
    global session_tokens, session_cost_usd
    session_tokens += tokens
    session_cost_usd += cost
    
    settings_data = load_settings()
    settings_data.setdefault("weekly_tokens_used", 142850)
    settings_data.setdefault("weekly_limit", 500000)
    settings_data.setdefault("five_hour_tokens_used", 32450)
    settings_data.setdefault("five_hour_limit", 100000)
    
    settings_data.setdefault("chatbot_tokens_used", 0)
    settings_data.setdefault("chatbot_cost_used", 0.0)
    
    settings_data["weekly_tokens_used"] = min(
        settings_data["weekly_limit"], 
        settings_data["weekly_tokens_used"] + tokens
    )
    settings_data["five_hour_tokens_used"] = min(
        settings_data["five_hour_limit"], 
        settings_data["five_hour_tokens_used"] + tokens
    )
    
    if not is_task:
        settings_data["chatbot_tokens_used"] += tokens
        settings_data["chatbot_cost_used"] += cost
        
    save_settings(settings_data)

def get_project_totals():
    try:
        with db._get_connection() as conn:
            row = conn.execute("SELECT SUM(tokens_used) as total_tokens, SUM(cost_usd) as total_cost FROM tasks").fetchone()
            db_tokens = row["total_tokens"] or 0
            db_cost = row["total_cost"] or 0.0
    except Exception:
        db_tokens = 0
        db_cost = 0.0
        
    settings_data = load_settings()
    chatbot_tokens = settings_data.get("chatbot_tokens_used", 0)
    chatbot_cost = settings_data.get("chatbot_cost_used", 0.0)
    
    return {
        "project_tokens": db_tokens + chatbot_tokens,
        "project_cost_usd": db_cost + chatbot_cost
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
        
        task = db.get_task(task_id)
        if not task or task["status"] in ["paused", "cancelled", "completed", "failed"]:
            return
            
        vram_manager.load_model(agent)
        retry = task["retry_count"]
        
        telemetry_data["logs"].append(f"[{agent}] Executing task {task_id} (Iteration {retry})...")
        await asyncio.sleep(1.5)

        # Check status again after sleep in case it was cancelled/paused
        task = db.get_task(task_id)
        if not task or task["status"] in ["paused", "cancelled", "completed", "failed"]:
            vram_manager.unload_model(agent)
            return

        if retry == 0:
            telemetry_data["logs"].append(f"[{agent}] Logic generated. Running validation checks...")
            await scheduler.handle_validation_failure(task_id)
        elif retry == 1:
            telemetry_data["logs"].append(f"[{agent}] Applying AST Node patch...")
            replace_block = """def calculate_tax(amount, rate=0.1):\n    if amount < 0:\n        raise ValueError("Amount cannot be negative")\n    return amount * rate"""
            compressor.apply_ast_injection(dummy_file, "calculate_tax", replace_block)
            telemetry_data["logs"].append(f"[Validator] Validation PASSED. Task T-001 complete.")
            await scheduler.transition_task(task_id, "completed")
            
        vram_manager.unload_model(agent)

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

async def on_task_running(event: Dict[str, Any]):
    task_id = event["task_id"]
    agent = event["agent_name"]
    msg = f"[Scheduler] Task {task_id} running on agent {agent}."
    telemetry_data["logs"].append(msg)
    telemetry_data["system_state"] = "running"
    telemetry_data["agent_context"][agent] = 8400  # Simulate context loading
    
    p_data = provider_telemetry.get(active_provider)
    if p_data:
        p_data["total_tokens"] += 1240
        rate = 0.00000015 if active_provider == "antigravity" else (0.000006 if active_provider == "claude" else 0.000003)
        cost = 1240 * rate
        p_data["total_cost_usd"] += cost
        track_usage(1240, cost, is_task=True)

async def on_task_completed(event: Dict[str, Any]):
    task_id = event["task_id"]
    agent = event["agent_name"]
    msg = f"[Kernel] Task {task_id} completed successfully by {agent}."
    telemetry_data["logs"].append(msg)
    telemetry_data["system_state"] = "idle"
    telemetry_data["agent_context"][agent] = 0  # Offload context
    
    p_data = provider_telemetry.get(active_provider)
    if p_data:
        p_data["total_tokens"] += 3520
        rate = 0.00000015 if active_provider == "antigravity" else (0.000006 if active_provider == "claude" else 0.000003)
        cost = 3520 * rate
        p_data["total_cost_usd"] += cost
        track_usage(3520, cost, is_task=True)

async def on_task_failed(event: Dict[str, Any]):
    task_id = event["task_id"]
    agent = event["agent_name"]
    msg = f"[Kernel] Task {task_id} failed on agent {agent}."
    telemetry_data["logs"].append(msg)
    telemetry_data["system_state"] = "idle"

@app.get("/api/status")
async def get_status():
    p_data = provider_telemetry.get(active_provider, provider_telemetry["antigravity"])
    
    # Sum up project totals
    proj_totals = get_project_totals()
    
    # Load settings for quota limits
    settings_data = load_settings()
    settings_data.setdefault("weekly_tokens_used", 142850)
    settings_data.setdefault("weekly_limit", 500000)
    settings_data.setdefault("five_hour_tokens_used", 32450)
    settings_data.setdefault("five_hour_limit", 100000)
    
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
        
        # Active Provider metrics
        "total_tokens": p_data["total_tokens"],
        "total_cost_usd": p_data["total_cost_usd"],
        "avg_latency_sec": p_data["avg_latency_sec"],
        
        # Project telemetry
        "project_tokens": proj_totals["project_tokens"],
        "project_cost_usd": proj_totals["project_cost_usd"],
        
        # Session telemetry
        "session_tokens": session_tokens,
        "session_cost_usd": session_cost_usd,
        
        # Quota metrics
        "weekly_tokens_used": settings_data["weekly_tokens_used"],
        "weekly_limit": settings_data["weekly_limit"],
        "five_hour_tokens_used": settings_data["five_hour_tokens_used"],
        "five_hour_limit": settings_data["five_hour_limit"],
        
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
    
    # Persist the settings
    settings_data = load_settings()
    settings_data["active_provider"] = active_provider
    save_settings(settings_data)
    
    # Add a system log line
    provider_names = {
        "antigravity": "Antigravity",
        "claude": "Claude Desktop",
        "cursor": "Cursor IDE"
    }
    name = provider_names.get(prov, prov.capitalize())
    telemetry_data["logs"].append(f"[Kernel] Switched active provider context to: {name}.")
    
    return {"status": "success", "active_provider": active_provider}

class TaskActionRequest(BaseModel):
    task_id: str

@app.get("/api/tasks")
async def get_tasks():
    # Return all tasks ordered by timestamp
    return db.get_all_tasks()

@app.get("/api/executions")
async def get_executions():
    return db.get_all_executions()

@app.post("/api/tasks/pause")
async def pause_task(req: TaskActionRequest):
    task = db.get_task(req.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] not in ["running", "pending"]:
        return {"status": "ignored", "message": f"Task {req.task_id} is not running."}
        
    await scheduler.transition_task(req.task_id, "paused")
    telemetry_data["logs"].append(f"[Scheduler] Task {req.task_id} manually paused by developer.")
    return {"status": "success", "message": f"Task {req.task_id} paused."}

@app.post("/api/tasks/resume")
async def resume_task(req: TaskActionRequest):
    task = db.get_task(req.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "paused":
        return {"status": "ignored", "message": f"Task {req.task_id} is not paused."}
        
    await scheduler.transition_task(req.task_id, "running")
    telemetry_data["logs"].append(f"[Scheduler] Task {req.task_id} manually resumed by developer.")
    return {"status": "success", "message": f"Task {req.task_id} resumed."}

@app.post("/api/tasks/cancel")
async def cancel_task(req: TaskActionRequest):
    task = db.get_task(req.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] in ["completed", "failed", "cancelled"]:
        return {"status": "ignored", "message": f"Task {req.task_id} is already completed/failed."}
        
    await scheduler.transition_task(req.task_id, "cancelled")
    telemetry_data["logs"].append(f"[Scheduler] Task {req.task_id} manually cancelled by developer.")
    return {"status": "success", "message": f"Task {req.task_id} cancelled."}

@app.post("/api/tasks/clear")
async def clear_tasks():
    db.clear_all_tasks()
    telemetry_data["logs"].append("[Kernel] Cleared all tasks and executions from the database.")
    return {"status": "success", "message": "All tasks cleared."}

@app.post("/api/tasks/delete")
async def delete_task_endpoint(req: TaskActionRequest):
    task = db.get_task(req.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    db.delete_task(req.task_id)
    telemetry_data["logs"].append(f"[Kernel] Task {req.task_id} cleared from database.")
    return {"status": "success", "message": f"Task {req.task_id} deleted."}

@app.post("/api/system/reset")
async def reset_system():
    global active_provider, provider_telemetry, telemetry_data, session_tokens, session_cost_usd
    
    session_tokens = 0
    session_cost_usd = 0.0

    
    # 1. Clear settings file
    if os.path.exists(SETTINGS_PATH):
        try:
            os.remove(SETTINGS_PATH)
        except Exception:
            pass
            
    # 2. Clear database
    db.clear_all_tasks()
    
    # 3. Reset active provider state
    active_provider = "antigravity"
    
    # 4. Reset telemetry data
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
            "[Kernel] System reset to factory defaults. All state cleared."
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
    
    # 5. Remove dummy files
    dummy_file = "finance_tool.py"
    if os.path.exists(dummy_file):
        try:
            os.remove(dummy_file)
        except Exception:
            pass
            
    vram_manager.loaded_models.clear()
    
    return {"status": "success", "message": "LIEM OS reset to factory defaults."}

def get_gemini_reply(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
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
            
            # Update telemetry with real API usage data
            usage = res_json.get("usageMetadata", {})
            prompt_tokens = usage.get("promptTokenCount", 0)
            cand_tokens = usage.get("candidatesTokenCount", 0)
            total_tokens = usage.get("totalTokenCount", 0)
            
            if total_tokens > 0:
                # Gemini 2.5 Flash pricing: $0.075 per 1M input, $0.30 per 1M output
                cost = (prompt_tokens * 0.075 + cand_tokens * 0.30) / 1_000_000
                provider_telemetry["antigravity"]["total_tokens"] += total_tokens
                provider_telemetry["antigravity"]["total_cost_usd"] += cost
                
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
    from liem_os.kernel.security import find_skills_root
    workspace_skills_dir = find_skills_root()
    if os.path.exists(workspace_skills_dir) and os.path.isdir(workspace_skills_dir):
        rel_folder = ".claude/skills" if ".claude" in workspace_skills_dir else ".agents/skills"
        for item in os.listdir(workspace_skills_dir):
            item_path = os.path.join(workspace_skills_dir, item)
            if os.path.isdir(item_path):
                skill_md = os.path.join(item_path, "SKILL.md")
                if os.path.exists(skill_md):
                    default_name = item.replace("-", " ").title()
                    name, description = parse_skill_metadata(skill_md, default_name)
                    if not any(s["name"] == name for s in skills):
                        skills.append({
                            "name": name,
                            "file": f"{rel_folder}/{item}/SKILL.md",
                            "domain": "WORKSPACE CUSTOMIZATION",
                            "description": description
                        })
            
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
    
    # Update task status in DB
    new_status = "completed" if req.action == "approve" else "cancelled"
    db.update_task_status(req.task_id, new_status, retry_count=5)
    
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

@app.get("/api/security/scan")
async def scan_security():
    from liem_os.kernel.security import find_skills_root
    skills_root = find_skills_root()
    
    try:
        results = await asyncio.to_thread(SkillSpectorScanner.scan_all_skills, skills_root)
        
        total_skills = len(results)
        vulnerable_count = 0
        warning_count = 0
        safe_count = 0
        total_findings = 0
        
        for r in results:
            rec = r.get("recommendation", "SAFE")
            score = r.get("risk_score", 0)
            findings_len = len(r.get("findings", []))
            total_findings += findings_len
            
            if rec != "SAFE" or score > 50:
                vulnerable_count += 1
            elif score > 30:
                warning_count += 1
            else:
                safe_count += 1
                
        overall_status = "SAFE"
        if vulnerable_count > 0:
            overall_status = "VULNERABLE"
        elif warning_count > 0:
            overall_status = "WARNING"
            
        return {
            "status": "success",
            "overall_status": overall_status,
            "metrics": {
                "total_skills": total_skills,
                "safe": safe_count,
                "warning": warning_count,
                "vulnerable": vulnerable_count,
                "total_findings": total_findings
            },
            "reports": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute security audit: {str(e)}")

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
