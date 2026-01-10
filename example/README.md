# MCP Task Queue Example

This example demonstrates MCP (Model Context Protocol) task execution using Redis for task storage and RabbitMQ for message queuing.

## Running the Example

1. **Start the infrastructure stack:**
   ```bash
   docker compose up
   ```

2. **Start the MCP server:**
   ```bash
   uv run mcp_server.py
   ```

3. **Run the MCP client:**
   ```bash
   uv run mcp_client.py
   ```

## What it does

- The client calls a `long_operation` tool that runs for a specified duration
- Tasks are stored in Redis with automatic TTL expiration
- Task status updates are tracked and can be polled
- The server returns task results when complete

## Services

- **Redis** (port 6379): Task storage
- **RabbitMQ** (port 5672): Message queue
- **RabbitMQ Management** (port 15672): Web UI (guest/guest)
- **MCP Server** (port 8000): HTTP task server