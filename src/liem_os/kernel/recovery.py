import logging
from typing import Dict, Any
from .event_bus import EventBus
from .event_loop import KernelEventLoop
from liem_os.storage.db_interface import BaseStateRepository

logger = logging.getLogger("LiemRecovery")

class RecoveryManager:
    """
    Handles agent failure mitigation, fallback models, HITL suspensions, and graph re-planning.
    """
    def __init__(self, db: BaseStateRepository, event_bus: EventBus, kernel: KernelEventLoop):
        self.db = db
        self.event_bus = event_bus
        self.kernel = kernel
        self._register_listeners()

    def _register_listeners(self) -> None:
        self.event_bus.subscribe("task.unhappy_loop.limit", self.escalate_unhappy_loop)

    async def escalate_unhappy_loop(self, event: Dict[str, Any]) -> None:
        task_id = event.get("task_id")
        agent_name = event.get("agent_name")
        logger.error(f"[Recovery] Escalation received for task {task_id} handled by {agent_name}!")

        # Step 1: Model Fallback
        logger.info(f"[Recovery] [STRATEGY 1] Fallback: Switching {agent_name} from local model to cloud API (Gemini 1.5 Pro)...")
        # In a real system, the runner config would update the LLM endpoint configuration here.
        
        # Step 2: HITL suspension
        logger.info(f"[Recovery] [STRATEGY 2] Suspending task {task_id}. Scale-to-Zero model offload initiated.")
        snapshot = {
            "task_id": task_id,
            "agent": agent_name,
            "failed_reason": "Unhappy loop limit reached (5 retries)."
        }
        await self.kernel.checkpoint_state(task_id, snapshot)
        logger.warning(
            f"[Recovery] HITL Alert dispatched to @axel: "
            f"\"Task {task_id} failed 5 consecutive validation runs. Please intervene or edit the code manually.\""
        )

        # Step 3: DAG Re-planning
        logger.info(f"[Recovery] [STRATEGY 3] Querying Core Planner to reconstruct the task DAG and bypass the bottleneck.")
