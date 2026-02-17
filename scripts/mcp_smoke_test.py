import anyio
import httpx
import os
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession

URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp").strip()
API_KEY = (os.getenv("MCP_API_KEY") or "").strip()


async def main() -> None:
    headers: dict[str, str] = {}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    http_client = httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(60.0, connect=10.0))
    try:
        async with streamable_http_client(
            URL,
            http_client=http_client,
            terminate_on_close=False,
        ) as (
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
                        "title": "Systemutvecklare",
                        "description": "Utvecklar backend-API:er i Python",
                    },
                )
                print("call_tool result", result)
    finally:
        await http_client.aclose()


if __name__ == "__main__":
    anyio.run(main)
