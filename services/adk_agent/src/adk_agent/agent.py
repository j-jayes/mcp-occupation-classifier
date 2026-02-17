import os

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPServerParams

from .prompt import SYSTEM_INSTRUCTION

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mcp-server:8000/mcp")
MCP_API_KEY = os.environ.get("MCP_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "openai/gpt-4o")

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
