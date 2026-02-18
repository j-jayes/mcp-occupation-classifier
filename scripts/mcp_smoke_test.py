import anyio
import httpx
import os
import hashlib
from pathlib import Path
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession

DEFAULT_URL = "http://localhost:8000/mcp"


def _maybe_load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _key_fingerprint(key: str) -> str:
    if not key:
        return "<empty>"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _get_config() -> tuple[str, str]:
    # If the caller didn't export MCP_* vars, fall back to the repo's .env.
    repo_root = Path(__file__).resolve().parents[1]
    _maybe_load_dotenv(repo_root / ".env")

    url = os.getenv("MCP_SERVER_URL", DEFAULT_URL).strip() or DEFAULT_URL
    api_key = (os.getenv("MCP_API_KEY") or "").strip()
    return url, api_key


async def main() -> None:
    url, api_key = _get_config()
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    http_client = httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(60.0, connect=10.0))
    try:
        async with streamable_http_client(
            url,
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

                # Regression sanity check: short English title should not map to an unrelated code.
                ds_result = await session.call_tool(
                    "classify_occupation",
                    {
                        "title": "Data Scientist",
                    },
                )
                print("call_tool Data Scientist result", ds_result)
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code == 401:
            print("401 Unauthorized from MCP server")
            print("url", url)
            print("api_key_present", bool(api_key))
            print("api_key_len", len(api_key))
            print("api_key_sha256", _key_fingerprint(api_key))
        raise
    finally:
        await http_client.aclose()


if __name__ == "__main__":
    try:
        anyio.run(main)
    except* httpx.HTTPStatusError as exc_group:  # Python 3.11+
        url, api_key = _get_config()
        for exc in exc_group.exceptions:
            if exc.response is not None and exc.response.status_code == 401:
                print("401 Unauthorized from MCP server")
                print("url", url)
                print("api_key_present", bool(api_key))
                print("api_key_len", len(api_key))
                print("api_key_sha256", _key_fingerprint(api_key))
                break
        raise
