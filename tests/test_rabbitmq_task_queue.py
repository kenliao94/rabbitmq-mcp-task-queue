"""Tests for RabbitMQTaskMessageQueue."""

import pytest
from datetime import datetime
from mcp.types import JSONRPCRequest
from mcp.shared.experimental.tasks.message_queue import QueuedMessage
from rabbitmq_mcp_task_queue import RabbitMQTaskMessageQueue


@pytest.fixture
def queue():
    """Create a queue instance for testing."""
    q = RabbitMQTaskMessageQueue(rabbitmq_url="amqp://localhost:5672")
    yield q
    q.close()


@pytest.fixture
def sample_message():
    """Create a sample queued message."""
    request = JSONRPCRequest(
        jsonrpc="2.0",
        id=1,
        method="test_method",
        params={"key": "value"}
    )
    return QueuedMessage(
        type="request",
        message=request,
        timestamp=datetime.now(),
        original_request_id="test-request-id"
    )


@pytest.mark.asyncio
async def test_enqueue_dequeue(queue, sample_message):
    """Test basic enqueue and dequeue operations."""
    task_id = "test-task-1"
    
    await queue.enqueue(task_id, sample_message)
    result = await queue.dequeue(task_id)
    
    assert result is not None
    assert result.type == sample_message.type
    assert result.original_request_id == sample_message.original_request_id


@pytest.mark.asyncio
async def test_is_empty(queue, sample_message):
    """Test is_empty method."""
    task_id = "test-task-2"
    
    assert await queue.is_empty(task_id)
    
    await queue.enqueue(task_id, sample_message)
    assert not await queue.is_empty(task_id)
    
    await queue.dequeue(task_id)
    assert await queue.is_empty(task_id)


@pytest.mark.asyncio
async def test_peek(queue, sample_message):
    """Test peek method."""
    task_id = "test-task-3"
    
    await queue.enqueue(task_id, sample_message)
    
    peeked = await queue.peek(task_id)
    assert peeked is not None
    assert not await queue.is_empty(task_id)
    
    dequeued = await queue.dequeue(task_id)
    assert dequeued is not None


@pytest.mark.asyncio
async def test_clear(queue, sample_message):
    """Test clear method."""
    task_id = "test-task-4"
    
    await queue.enqueue(task_id, sample_message)
    await queue.enqueue(task_id, sample_message)
    
    messages = await queue.clear(task_id)
    assert len(messages) == 2
    assert await queue.is_empty(task_id)
