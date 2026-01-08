"""
RabbitMQ implementation of TaskMessageQueue.
"""

import json

import anyio
import pika
from pika.adapters.blocking_connection import BlockingChannel

from mcp.shared.experimental.tasks.message_queue import QueuedMessage, TaskMessageQueue


class RabbitMQTaskMessageQueue(TaskMessageQueue):
    """
    RabbitMQ-based implementation of TaskMessageQueue.
    
    Uses RabbitMQ queues for persistent, distributed message storage.
    Each task gets its own queue: mcp:queue:{task_id}
    """

    def __init__(self, rabbitmq_url: str = "amqp://localhost:5672") -> None:
        self.rabbitmq_url = rabbitmq_url
        self._connection: pika.BlockingConnection | None = None
        self._channel: BlockingChannel | None = None
        self._events: dict[str, anyio.Event] = {}

    def _get_connection(self) -> pika.BlockingConnection:
        """Get or create RabbitMQ connection."""
        if self._connection is None or self._connection.is_closed:
            params = pika.URLParameters(self.rabbitmq_url)
            self._connection = pika.BlockingConnection(params)
            self._channel = self._connection.channel()
        return self._connection

    def _get_channel(self) -> BlockingChannel:
        """Get RabbitMQ channel."""
        self._get_connection()
        return self._channel

    def _get_queue_name(self, task_id: str) -> str:
        """Generate queue name for task."""
        return f"mcp:queue:{task_id}"

    def _ensure_queue(self, task_id: str) -> None:
        """Ensure queue exists for task."""
        channel = self._get_channel()
        queue_name = self._get_queue_name(task_id)
        channel.queue_declare(queue=queue_name, durable=True)

    def _serialize_message(self, message: QueuedMessage) -> str:
        """Serialize QueuedMessage to JSON."""
        data = {
            "type": message.type,
            "message": message.message.model_dump(),
            "timestamp": message.timestamp.isoformat(),
            "original_request_id": message.original_request_id,
        }
        return json.dumps(data)

    def _deserialize_message(self, body: bytes) -> QueuedMessage:
        """Deserialize JSON to QueuedMessage."""
        from datetime import datetime
        from mcp.types import JSONRPCNotification, JSONRPCRequest
        
        data = json.loads(body)
        
        # Reconstruct message object
        if data["type"] == "request":
            msg = JSONRPCRequest.model_validate(data["message"])
        else:
            msg = JSONRPCNotification.model_validate(data["message"])
        
        return QueuedMessage(
            type=data["type"],
            message=msg,
            timestamp=datetime.fromisoformat(data["timestamp"]),
            original_request_id=data.get("original_request_id"),
        )

    async def enqueue(self, task_id: str, message: QueuedMessage) -> None:
        """Add a message to the queue."""
        self._ensure_queue(task_id)
        channel = self._get_channel()
        queue_name = self._get_queue_name(task_id)
        
        body = self._serialize_message(message)
        channel.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=body,
            properties=pika.BasicProperties(delivery_mode=2)  # Persistent
        )
        
        await self.notify_message_available(task_id)

    async def dequeue(self, task_id: str) -> QueuedMessage | None:
        """Remove and return the next message."""
        self._ensure_queue(task_id)
        channel = self._get_channel()
        queue_name = self._get_queue_name(task_id)
        
        method, properties, body = channel.basic_get(queue=queue_name, auto_ack=True)
        if method is None:
            return None
        
        return self._deserialize_message(body)

    async def peek(self, task_id: str) -> QueuedMessage | None:
        """Return the next message without removing it."""
        self._ensure_queue(task_id)
        channel = self._get_channel()
        queue_name = self._get_queue_name(task_id)
        
        method, properties, body = channel.basic_get(queue=queue_name, auto_ack=False)
        if method is None:
            return None
        
        # Reject to put it back in queue
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        return self._deserialize_message(body)

    async def is_empty(self, task_id: str) -> bool:
        """Check if the queue is empty."""
        self._ensure_queue(task_id)
        channel = self._get_channel()
        queue_name = self._get_queue_name(task_id)
        
        result = channel.queue_declare(queue=queue_name, durable=True, passive=True)
        return result.method.message_count == 0

    async def clear(self, task_id: str) -> list[QueuedMessage]:
        """Remove and return all messages."""
        messages = []
        while True:
            msg = await self.dequeue(task_id)
            if msg is None:
                break
            messages.append(msg)
        return messages

    async def wait_for_message(self, task_id: str) -> None:
        """Wait until a message is available."""
        if not await self.is_empty(task_id):
            return
        
        self._events[task_id] = anyio.Event()
        event = self._events[task_id]
        
        if not await self.is_empty(task_id):
            return
        
        await event.wait()

    async def notify_message_available(self, task_id: str) -> None:
        """Signal that a message is available."""
        if task_id in self._events:
            self._events[task_id].set()

    def close(self) -> None:
        """Close RabbitMQ connection."""
        if self._connection and not self._connection.is_closed:
            self._connection.close()
