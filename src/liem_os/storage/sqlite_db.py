import sqlite3
import json
import os
from typing import Dict, Any, List, Optional
from liem_os.storage.db_interface import BaseStateRepository

class SQLiteStateRepository(BaseStateRepository):
    """
    SQLite implementation of BaseStateRepository.
    Uses WAL mode for concurrent operations.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable Write-Ahead Logging (WAL) mode
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS executions (
                execution_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                metadata TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                target_agent TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                retry_count INTEGER NOT NULL DEFAULT 0,
                temperature REAL NOT NULL DEFAULT 0.7,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (execution_id) REFERENCES executions(execution_id) ON DELETE CASCADE
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                task_id TEXT PRIMARY KEY,
                state_data TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
            );
            """)
            conn.commit()

    def save_execution(self, execution_id: str, status: str, metadata: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO executions (execution_id, status, metadata) VALUES (?, ?, ?)",
                (execution_id, status, json.dumps(metadata))
            )
            conn.commit()

    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM executions WHERE execution_id = ?", (execution_id,)).fetchone()
            if row:
                return {
                    "execution_id": row["execution_id"],
                    "status": row["status"],
                    "metadata": json.loads(row["metadata"]),
                    "timestamp": row["timestamp"]
                }
            return None

    def save_task(self, task_id: str, execution_id: str, target_agent: str, status: str, payload: Dict[str, Any], retry_count: int, temperature: float) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tasks (task_id, execution_id, target_agent, status, payload, retry_count, temperature) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (task_id, execution_id, target_agent, status, json.dumps(payload), retry_count, temperature)
            )
            conn.commit()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row:
                return {
                    "task_id": row["task_id"],
                    "execution_id": row["execution_id"],
                    "target_agent": row["target_agent"],
                    "status": row["status"],
                    "payload": json.loads(row["payload"]),
                    "retry_count": row["retry_count"],
                    "temperature": row["temperature"],
                    "timestamp": row["timestamp"]
                }
            return None

    def update_task_status(self, task_id: str, status: str, retry_count: int = 0, temperature: float = 0.7) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, retry_count = ?, temperature = ? WHERE task_id = ?",
                (status, retry_count, temperature, task_id)
            )
            conn.commit()

    def get_active_tasks(self, execution_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM tasks WHERE execution_id = ?", (execution_id,)).fetchall()
            return [
                {
                    "task_id": r["task_id"],
                    "execution_id": r["execution_id"],
                    "target_agent": r["target_agent"],
                    "status": r["status"],
                    "payload": json.loads(r["payload"]),
                    "retry_count": r["retry_count"],
                    "temperature": r["temperature"],
                    "timestamp": r["timestamp"]
                }
                for r in rows
            ]

    def save_snapshot(self, task_id: str, state_data: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO snapshots (task_id, state_data) VALUES (?, ?)",
                (task_id, json.dumps(state_data))
            )
            conn.commit()

    def get_snapshot(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM snapshots WHERE task_id = ?", (task_id,)).fetchone()
            if row:
                return json.loads(row["state_data"])
            return None

    def clear_snapshot(self, task_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM snapshots WHERE task_id = ?", (task_id,))
            conn.commit()
