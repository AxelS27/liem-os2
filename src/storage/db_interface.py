from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseStateRepository(ABC):
    """
    Abstract state repository defining the persistence contract for LIEM OS.
    Allows easy swapping between SQLite (local development) and PostgreSQL (production).
    """

    @abstractmethod
    def save_execution(self, execution_id: str, status: str, metadata: Dict[str, Any]) -> None:
        """Saves or updates an execution state machine trace."""
        pass

    @abstractmethod
    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves execution trace info."""
        pass

    @abstractmethod
    def save_task(self, task_id: str, execution_id: str, target_agent: str, status: str, payload: Dict[str, Any], retry_count: int, temperature: float) -> None:
        """Saves a work unit/task state."""
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a task by ID."""
        pass

    @abstractmethod
    def update_task_status(self, task_id: str, status: str, retry_count: int = 0, temperature: float = 0.7) -> None:
        """Updates the status, retry count, and temperature of an active task."""
        pass

    @abstractmethod
    def get_active_tasks(self, execution_id: str) -> List[Dict[str, Any]]:
        """Returns all tasks associated with an execution."""
        pass

    @abstractmethod
    def save_snapshot(self, task_id: str, state_data: Dict[str, Any]) -> None:
        """Saves a state snapshot for Scale-to-Zero Pause-and-Resume hydration."""
        pass

    @abstractmethod
    def get_snapshot(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves snapshot data to resume a task."""
        pass

    @abstractmethod
    def clear_snapshot(self, task_id: str) -> None:
        """Deletes a snapshot after the task is resumed."""
        pass
