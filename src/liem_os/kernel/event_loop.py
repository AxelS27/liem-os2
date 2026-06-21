import asyncio
import logging
from typing import Dict, Any
from .event_bus import EventBus
from .vram_manager import VRAMManager
from liem_os.storage.db_interface import BaseStateRepository

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
        # Subscribe to task completion channel to trigger state machine checks
        self.event_bus.subscribe("task.status.completed", self._on_task_completed)
        self.event_bus.subscribe("task.status.failed", self._on_task_failed)
        logger.info("[Kernel] Boot complete. All core services online.")

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
