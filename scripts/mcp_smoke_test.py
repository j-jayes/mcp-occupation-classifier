import anyio
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession

URL = "https://ssyk-mcp-420199586073.europe-west1.run.app/mcp"


async def main() -> None:
    async with streamable_http_client(URL, terminate_on_close=False) as (
        read,
        write,
        get_session_id,
    ):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            print("initialized", info)

            tools = await session.list_tools()
            print("tools", [t.name for t in tools.tools])

            result = await session.call_tool(
                "classify_occupation",
                {
                    "title": "Software engineer",
                    "description": "Builds backend APIs in Python",
                },
            )
            print("call_tool result", result)


if __name__ == "__main__":
    anyio.run(main)
