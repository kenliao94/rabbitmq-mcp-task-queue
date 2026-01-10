import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult


async def main():
    # Connect to a streamable HTTP server
    async with streamable_http_client("http://localhost:8000/mcp") as (
        read_stream,
        write_stream,
        _,
    ):
        # Create a session using the client streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("Tools:", [t.name for t in tools.tools])

            # Call tool as task
            result = await session.experimental.call_tool_as_task(
                "long_operation",
                {"duration": 7},
                ttl=60000,
            )
            print(f"result: {result}")

            task_id = result.task.taskId
            print(f"task_id: {task_id}")
            
            # Poll until complete
            async for status in session.experimental.poll_task(task_id):
                print(f"Status: {status.status} - {status.statusMessage or ''}")

            # Get result
            final = await session.experimental.get_task_result(task_id, CallToolResult)
            print(f"Result: {final.content[0].text}")



if __name__ == "__main__":
    asyncio.run(main())