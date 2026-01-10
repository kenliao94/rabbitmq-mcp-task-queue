from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount

from mcp.server import Server
from mcp.server.experimental.task_context import ServerTaskContext
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import (
    CallToolResult, CreateTaskResult, TextContent, Tool, ToolExecution, TASK_REQUIRED,
)

from redis_task_store import RedisTaskStore
from rabbitmq_mcp_task_queue import RabbitMQTaskMessageQueue

server = Server("http-task-server")
task_store = RedisTaskStore()
task_queue = RabbitMQTaskMessageQueue()

server.experimental.enable_tasks(store=task_store, queue=task_queue)


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="long_operation",
            description="A long-running operation",
            inputSchema={"type": "object", "properties": {"duration": {"type": "number"}}},
            execution=ToolExecution(taskSupport=TASK_REQUIRED),
        )
    ]


async def handle_long_operation(arguments: dict) -> CreateTaskResult:
    ctx = server.request_context
    ctx.experimental.validate_task_mode(TASK_REQUIRED)

    duration = arguments.get("duration", 15)

    async def work(task: ServerTaskContext) -> CallToolResult:
        import anyio
        for i in range(int(duration)):
            await task.update_status(f"Step {i+1}/{int(duration)}")
            await anyio.sleep(1)
        return CallToolResult(content=[TextContent(type="text", text=f"Completed after {duration}s")])

    return await ctx.experimental.run_task(work)


@server.call_tool()
async def handle_tool(name: str, arguments: dict) -> CallToolResult | CreateTaskResult:
    if name == "long_operation":
        return await handle_long_operation(arguments)
    return CallToolResult(content=[TextContent(type="text", text=f"Unknown: {name}")], isError=True)


def create_app():
    session_manager = StreamableHTTPSessionManager(app=server)

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        await task_store.initialize()
        async with session_manager.run():
            yield
        await task_store.close()

    return Starlette(
        routes=[Mount("/mcp", app=session_manager.handle_request)],
        lifespan=lifespan,
    )


if __name__ == "__main__":
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)