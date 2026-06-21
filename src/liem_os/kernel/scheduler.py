import logging
from typing import Dict, Any
from .event_bus import EventBus
from liem_os.storage.db_interface import BaseStateRepository

logger = logging.getLogger("LiemScheduler")

class CoreScheduler:
    """
    Coordinates task execution, cyclic unhappy loops, and decaying temperature parameters.
    """
    def __init__(self, db: BaseStateRepository, event_bus: EventBus, max_retries: int = 5):
        self.db = db
        self.event_bus = event_bus
        self.max_retries = max_retries
        self.initial_temp = 0.7

    async def dispatch_task(self, task_id: str, target_agent: str, payload: Dict[str, Any], execution_id: str) -> None:
        """Saves and dispatches a new task."""
        logger.info(f"[Scheduler] Dispatching task {task_id} to {target_agent}.")
        self.db.save_task(
            task_id=task_id,
            execution_id=execution_id,
            target_agent=target_agent,
            status="pending",
            payload=payload,
            retry_count=0,
            temperature=self.initial_temp
        )
        await self.transition_task(task_id, "running")

    async def transition_task(self, task_id: str, new_status: str) -> None:
        """Updates task state and triggers event notification (avoiding polling)."""
        task = self.db.get_task(task_id)
        if not task:
            logger.error(f"[Scheduler] Task {task_id} not found.")
            return

        old_status = task["status"]
        logger.info(f"[Scheduler] Task {task_id} transitioning: {old_status} -> {new_status}.")
        
        self.db.update_task_status(
            task_id=task_id,
            status=new_status,
            retry_count=task["retry_count"],
            temperature=task["temperature"]
        )

        # Publish state transition to event bus (Pub/Sub)
        await self.event_bus.publish(f"task.status.{new_status}", {"task_id": task_id, "agent_name": task["target_agent"]})

    async def handle_validation_failure(self, task_id: str) -> None:
        """
        Handles validation fails (Unhappy Path Loop).
        Increments loop retry count, decays temperature, and escalates when limit is reached.
        """
        task = self.db.get_task(task_id)
        if not task:
            return

        current_retries = task["retry_count"] + 1
        agent_name = task["target_agent"]

        if current_retries > self.max_retries:
            logger.error(f"[Scheduler] Task {task_id} breached maximum loop iterations ({self.max_retries}). Aborting loop.")
            # Transition to failed
            await self.transition_task(task_id, "failed")
            # Emit loop failure escalation event
            await self.event_bus.publish("task.unhappy_loop.limit", {"task_id": task_id, "agent_name": agent_name})
            return

        # Decaying Temperature formula: T_new = max(0, T_initial - (i * 0.15))
        new_temp = max(0.0, self.initial_temp - (current_retries * 0.15))
        logger.warning(
            f"[Scheduler] Validation FAILED for task {task_id} (Iteration {current_retries}/{self.max_retries}). "
            f"Decaying temperature from {task['temperature']:.2f} -> {new_temp:.2f} to force convergence."
        )

        # Persist retry details
        self.db.update_task_status(
            task_id=task_id,
            status="running",  # Loop state back to running for developer
            retry_count=current_retries,
            temperature=new_temp
        )

        # Trigger re-execution
        await self.event_bus.publish("task.status.running", {"task_id": task_id, "agent_name": agent_name})
