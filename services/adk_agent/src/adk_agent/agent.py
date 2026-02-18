import os

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPServerParams

from .prompt import SYSTEM_INSTRUCTION

def _coalesce_env(dst: str, src: str) -> None:
    """If env var `dst` is unset/blank, set it from `src` when available."""
    if (os.environ.get(dst) or "").strip():
        return
    value = (os.environ.get(src) or "").strip()
    if value:
        os.environ[dst] = value


# LiteLLM commonly expects AZURE_API_* env vars.
_coalesce_env("AZURE_API_BASE", "AZURE_OPENAI_ENDPOINT")
_coalesce_env("AZURE_API_KEY", "AZURE_OPENAI_API_KEY")
_coalesce_env("AZURE_API_VERSION", "AZURE_OPENAI_API_VERSION")

MCP_SERVER_URL = (os.environ.get("MCP_SERVER_URL", "http://mcp-server:8000/mcp") or "").strip()
MCP_API_KEY = (os.environ.get("MCP_API_KEY", "") or "").strip()
OPENAI_MODEL = (os.environ.get("OPENAI_MODEL", "openai/gpt-4o") or "").strip()

_headers: dict[str, str] = {}
if MCP_API_KEY:
    _headers["Authorization"] = f"Bearer {MCP_API_KEY}"

root_agent = Agent(
    model=LiteLlm(model=OPENAI_MODEL),
    name="occupation_advisor",
    instruction=SYSTEM_INSTRUCTION,
    tools=[
        McpToolset(
            connection_params=StreamableHTTPServerParams(
                url=MCP_SERVER_URL,
                headers=_headers,
            ),
        ),
    ],
)
