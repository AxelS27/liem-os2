import asyncio
import logging
import os
from typing import Dict, Any, Optional
from .event_bus import EventBus
from .vram_manager import VRAMManager
from liem_os.storage.db_interface import BaseStateRepository
from liem_os.kernel.security import SkillSpectorScanner

logger = logging.getLogger("LiemKernel")

class KernelEventLoop:
    """
    Main execution engine of LIEM OS.
    Handles startup, async event loops, checkpointing, and graceful shutdowns.
    """
    def __init__(self, db: BaseStateRepository, event_bus: EventBus, vram_manager: VRAMManager):
        self.db = db
        self.event_bus = event_bus
        self.vram_manager = vram_manager
        self.running = False
        self._loop_task: Optional[asyncio.Task] = None

    async def boot(self) -> None:
        logger.info("[Kernel] Booting LIEM OS engine...")
        self.running = True
        
        # Run security check on all loaded skills
        await self._run_security_audit()
        
        # Subscribe to task completion channel to trigger state machine checks
        self.event_bus.subscribe("task.status.completed", self._on_task_completed)
        self.event_bus.subscribe("task.status.failed", self._on_task_failed)
        logger.info("[Kernel] Boot complete. All core services online.")

    async def _run_security_audit(self) -> None:
        logger.info("[Kernel] Starting SkillSpector security audit on loaded skills...")
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        skills_root = os.path.join(project_root, ".claude", "skills")
        
        try:
            # Run in thread pool to prevent blocking event loop
            results = await asyncio.to_thread(SkillSpectorScanner.scan_all_skills, skills_root)
            
            vulnerable_skills = 0
            for report in results:
                name = report.get("skill_name")
                score = report.get("risk_score", 0)
                severity = report.get("severity", "LOW")
                rec = report.get("recommendation", "SAFE")
                
                if rec != "SAFE" or score > 50:
                    logger.warning(f"[Kernel] [SECURITY WARNING] Skill '{name}' is UNTRUSTED! Risk Score: {score}/100, Severity: {severity}. Please review immediately.")
                    vulnerable_skills += 1
                else:
                    logger.info(f"[Kernel] Skill '{name}' passed security audit. Risk Score: {score}/100 (Safe).")
                    
            if vulnerable_skills > 0:
                logger.warning(f"[Kernel] Security audit complete with {vulnerable_skills} warnings. System is ONLINE but compromised skills exist.")
            else:
                logger.info("[Kernel] Security audit complete. All skills passed verification.")
        except Exception as e:
            logger.error(f"[Kernel] Failed to run security audit: {e}")


    async def shutdown(self) -> None:
        logger.info("[Kernel] Shutting down LIEM OS engine...")
        self.running = False
        # Offload all loaded models to clean up GPU resources
        for model in list(self.vram_manager.loaded_models.keys()):
            self.vram_manager.unload_model(model)
        logger.info("[Kernel] Shutdown complete. VRAM freed.")

    async def _on_task_completed(self, event: Dict[str, Any]) -> None:
        task_id = event.get("task_id")
        agent_name = event.get("agent_name")
        logger.info(f"[Kernel] Event received: Task {task_id} completed by {agent_name}.")
        # Scale-to-zero: Unload the agent's LLM model immediately on completion
        self.vram_manager.unload_model(agent_name)

    async def _on_task_failed(self, event: Dict[str, Any]) -> None:
        task_id = event.get("task_id")
        agent_name = event.get("agent_name")
        logger.warning(f"[Kernel] Event received: Task {task_id} FAILED by {agent_name}.")
        # Scale-to-zero: Unload the agent's LLM model immediately on failure
        self.vram_manager.unload_model(agent_name)

    async def checkpoint_state(self, task_id: str, state_snapshot: Dict[str, Any]) -> None:
        """Saves current state and forces model offload (Scale-to-Zero for HITL)."""
        logger.info(f"[Kernel] Serializing and checkpointing task {task_id} to snapshot database.")
        self.db.save_snapshot(task_id, state_snapshot)
        
        # Determine the agent associated with this task
        task = self.db.get_task(task_id)
        if task:
            agent_name = task["target_agent"]
            logger.info(f"[Kernel] Task {task_id} entered WAITING/HITL. Scale-to-Zero trigger for {agent_name}.")
            self.vram_manager.unload_model(agent_name)
