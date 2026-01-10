"""
Redis implementation of TaskStore.
"""

import json
from datetime import datetime, timedelta, timezone

import anyio
import redis.asyncio as redis

from mcp.shared.experimental.tasks.helpers import create_task_state, is_terminal
from mcp.shared.experimental.tasks.store import TaskStore
from mcp.types import Result, Task, TaskMetadata, TaskStatus


class RedisTaskStore(TaskStore):
    """Redis-based TaskStore implementation."""

    def __init__(self, redis_url: str = "redis://localhost:6379", page_size: int = 10):
        self.redis_url = redis_url
        self._page_size = page_size
        self._redis: redis.Redis | None = None
        self._update_events: dict[str, anyio.Event] = {}

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        self._redis = redis.from_url(self.redis_url, decode_responses=True)

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()

    def _task_key(self, task_id: str) -> str:
        return f"task:{task_id}"

    def _result_key(self, task_id: str) -> str:
        return f"result:{task_id}"

    def _calculate_expiry_seconds(self, ttl_ms: int | None) -> int | None:
        """Calculate expiry in seconds from TTL in milliseconds."""
        if ttl_ms is None:
            return None
        return max(1, ttl_ms // 1000)  # At least 1 second

    async def create_task(
        self,
        metadata: TaskMetadata,
        task_id: str | None = None,
    ) -> Task:
        """Create a new task with the given metadata."""
        task = create_task_state(metadata, task_id)
        
        task_key = self._task_key(task.taskId)
        exists = await self._redis.exists(task_key)
        if exists:
            raise ValueError(f"Task with ID {task.taskId} already exists")
        
        # Store task data
        await self._redis.set(task_key, task.model_dump_json())
        
        # Set TTL if specified
        if metadata.ttl:
            ttl_seconds = self._calculate_expiry_seconds(metadata.ttl)
            if ttl_seconds:
                await self._redis.expire(task_key, ttl_seconds)
        
        return Task(**task.model_dump())

    async def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        task_data = await self._redis.get(self._task_key(task_id))
        if task_data is None:
            return None
        
        return Task.model_validate_json(task_data)

    async def update_task(
        self,
        task_id: str,
        status: TaskStatus | None = None,
        status_message: str | None = None,
    ) -> Task:
        """Update a task's status and/or message."""
        task_key = self._task_key(task_id)
        task_data = await self._redis.get(task_key)
        
        if task_data is None:
            raise ValueError(f"Task with ID {task_id} not found")
        
        task = Task.model_validate_json(task_data)
        
        # Check terminal state transition
        if status is not None and status != task.status and is_terminal(task.status):
            raise ValueError(f"Cannot transition from terminal status '{task.status}'")
        
        status_changed = False
        if status is not None and task.status != status:
            task.status = status
            status_changed = True
        
        if status_message is not None:
            task.statusMessage = status_message
        
        task.lastUpdatedAt = datetime.now(timezone.utc)
        
        # Update in Redis
        await self._redis.set(task_key, task.model_dump_json())
        
        # Set TTL for terminal states
        if status is not None and is_terminal(status) and task.ttl is not None:
            ttl_seconds = self._calculate_expiry_seconds(task.ttl)
            if ttl_seconds:
                await self._redis.expire(task_key, ttl_seconds)
        
        if status_changed:
            await self.notify_update(task_id)
        
        return Task(**task.model_dump())

    async def store_result(self, task_id: str, result: Result) -> None:
        """Store the result for a task."""
        task_exists = await self._redis.exists(self._task_key(task_id))
        if not task_exists:
            raise ValueError(f"Task with ID {task_id} not found")
        
        result_key = self._result_key(task_id)
        await self._redis.set(result_key, result.model_dump_json())
        
        # Copy TTL from task to result
        ttl = await self._redis.ttl(self._task_key(task_id))
        if ttl > 0:
            await self._redis.expire(result_key, ttl)

    async def get_result(self, task_id: str) -> Result | None:
        """Get the stored result for a task."""
        result_data = await self._redis.get(self._result_key(task_id))
        if result_data is None:
            return None
        
        return Result.model_validate_json(result_data)

    async def list_tasks(
        self,
        cursor: str | None = None,
    ) -> tuple[list[Task], str | None]:
        """List tasks with pagination."""
        pattern = "task:*"
        scan_cursor = int(cursor) if cursor else 0
        
        keys, next_cursor = await self._redis.scan(
            cursor=scan_cursor, 
            match=pattern, 
            count=self._page_size
        )
        
        tasks = []
        for key in keys:
            task_data = await self._redis.get(key)
            if task_data:
                tasks.append(Task.model_validate_json(task_data))
        
        # Sort by creation time (newest first)
        tasks.sort(key=lambda t: t.createdAt, reverse=True)
        
        return tasks[:self._page_size], str(next_cursor) if next_cursor else None

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task and its result."""
        task_key = self._task_key(task_id)
        result_key = self._result_key(task_id)
        
        deleted_count = await self._redis.delete(task_key, result_key)
        return deleted_count > 0

    async def wait_for_update(self, task_id: str) -> None:
        """Wait until the task status changes."""
        task = await self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task with ID {task_id} not found")
        
        self._update_events[task_id] = anyio.Event()
        event = self._update_events[task_id]
        await event.wait()

    async def notify_update(self, task_id: str) -> None:
        """Signal that a task has been updated."""
        if task_id in self._update_events:
            self._update_events[task_id].set()