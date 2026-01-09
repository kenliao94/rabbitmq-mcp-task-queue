# rabbitmq-mcp-task-queue

RabbitMQ-based TaskMessageQueue implementation for the Model Context Protocol (MCP).

## Features

- **Persistent Message Storage**: Uses RabbitMQ for reliable, distributed message queuing
- **Task Isolation**: Each task gets its own dedicated queue (`mcp:queue:{task_id}`)
- **Async/Await Support**: Built with modern Python async patterns
- **Automatic Queue Management**: Queues are created on-demand and cleaned up automatically
- **Production Ready**: Durable queues with persistent message delivery

## Installation

```bash
pip install rabbitmq-mcp-task-queue
```

## Requirements

- Python 3.11+
- RabbitMQ server (local or remote)
- MCP SDK 1.3.0+

## Quick Start

```python
from rabbitmq_mcp_task_queue import RabbitMQTaskMessageQueue
from mcp.server import Server

# Initialize the queue
queue = RabbitMQTaskMessageQueue(rabbitmq_url="amqp://localhost:5672")

# Use with MCP server
server = Server("my-server")
server.experimental.enable_tasks(queue=queue)
```

## Configuration

### RabbitMQ Connection

```python
# Local RabbitMQ
queue = RabbitMQTaskMessageQueue()

# Remote RabbitMQ with credentials
queue = RabbitMQTaskMessageQueue(
    rabbitmq_url="amqp://user:password@rabbitmq.example.com:5672/vhost"
)
```

### Queue Naming

Queues are automatically named using the pattern: `mcp:queue:{task_id}`

## Usage with MCP Server

```python
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from rabbitmq_mcp_task_queue import RabbitMQTaskMessageQueue

server = Server("task-server")
queue = RabbitMQTaskMessageQueue(rabbitmq_url="amqp://localhost:5672")

server.experimental.enable_tasks(queue=queue)

# Define your tools and handlers
@server.call_tool()
async def handle_tool(name: str, arguments: dict):
    # Your tool implementation
    pass
```

## API Reference

### RabbitMQTaskMessageQueue

#### Constructor

```python
RabbitMQTaskMessageQueue(rabbitmq_url: str = "amqp://localhost:5672")
```

**Parameters:**
- `rabbitmq_url`: AMQP connection URL for RabbitMQ

#### Methods

- `async enqueue(task_id: str, message: QueuedMessage) -> None`: Add message to queue
- `async dequeue(task_id: str) -> QueuedMessage | None`: Remove and return next message
- `async peek(task_id: str) -> QueuedMessage | None`: View next message without removing
- `async is_empty(task_id: str) -> bool`: Check if queue is empty
- `async clear(task_id: str) -> list[QueuedMessage]`: Remove all messages
- `async wait_for_message(task_id: str) -> None`: Wait for message availability
- `close() -> None`: Close RabbitMQ connection

## Architecture

### Message Persistence

- All queues are declared as **durable**
- Messages are published with **delivery_mode=2** (persistent)
- Ensures messages survive RabbitMQ restarts

### Connection Management

- Lazy connection initialization
- Automatic reconnection on connection loss
- Single channel per queue instance

### Message Format

Messages are serialized as JSON with the following structure:

```json
{
  "type": "request|notification",
  "message": {...},
  "timestamp": "2024-01-01T00:00:00",
  "original_request_id": "..."
}
```

## Development

### Setup

```bash
git clone https://github.com/yourusername/mcp-task-rmq-queue.git
cd mcp-task-rmq-queue
uv venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
uv pip install -e .
```

### Running Tests

```bash
pytest tests/
```

### Building

```bash
python -m build
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/mcp-task-rmq-queue/issues
- MCP Documentation: https://modelcontextprotocol.io
