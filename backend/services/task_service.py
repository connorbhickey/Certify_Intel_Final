"""
Certify Intel - Background AI Task Service

Wraps the _ai_tasks dict pattern from main.py into a service class.
Uses in-memory dict for task state (needed for background coroutine mutations)
and the cache layer for pruning/TTL support.

Usage:
    from services.task_service import task_service
    task_id = task_service.create(user_id=1, page_context="dashboard", task_type="summary")
    task_service.update(task_id, status="completed", result={...})
    task = task_service.get(task_id)
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskService:
    """Manages background AI task state with auto-pruning."""

    def __init__(self, prune_after_hours: int = 1):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._prune_after = timedelta(hours=prune_after_hours)

    @property
    def tasks(self) -> Dict[str, Dict[str, Any]]:
        """Direct access to the underlying dict (for backward compatibility)."""
        return self._tasks

    def create(
        self,
        task_id: str,
        user_id: int,
        page_context: str = "unknown",
        task_type: str = "generic",
    ) -> Dict[str, Any]:
        """Create a new background task entry."""
        task = {
            "status": "running",
            "page_context": page_context,
            "user_id": user_id,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
            "task_type": task_type,
            "read_at": None,
        }
        self._tasks[task_id] = task
        return task

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID. Returns None if not found."""
        return self._tasks.get(task_id)

    def update(self, task_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Update fields on an existing task."""
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task.update(kwargs)
        return task

    def mark_completed(
        self,
        task_id: str,
        result: Any = None,
        error: str = None,
    ):
        """Mark a task as completed or failed."""
        task = self._tasks.get(task_id)
        if task is None:
            return
        if error:
            task["status"] = "failed"
            task["error"] = error
        else:
            task["status"] = "completed"
            task["result"] = result
        task["completed_at"] = datetime.utcnow().isoformat()

    def get_pending_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Get running + completed-unread tasks for a user."""
        pending = []
        for tid, task in self._tasks.items():
            if task.get("user_id") != user_id:
                continue
            if task["status"] == "running" or (
                task["status"] == "completed"
                and task.get("read_at") is None
            ):
                pending.append({"task_id": tid, **task})

        # Sort newest first
        pending.sort(
            key=lambda t: t.get("started_at", ""), reverse=True
        )

        # Auto-prune stale tasks
        self.prune()
        return pending

    def prune(self):
        """Remove completed/failed tasks that have been read and are older than threshold."""
        cutoff = datetime.utcnow() - self._prune_after
        stale_ids = [
            tid
            for tid, task in self._tasks.items()
            if task.get("status") in ("completed", "failed")
            and task.get("read_at")
            and isinstance(task.get("read_at"), str)
            and datetime.fromisoformat(task["read_at"]) < cutoff
        ]
        for tid in stale_ids:
            del self._tasks[tid]
        if stale_ids:
            logger.debug("Pruned %d stale AI tasks", len(stale_ids))

    def count(self) -> int:
        """Return the number of tracked tasks."""
        return len(self._tasks)


# Singleton instance
task_service = TaskService()
