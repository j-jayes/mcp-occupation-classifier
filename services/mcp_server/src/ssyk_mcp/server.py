import os
from typing import Any, Dict, List

from fastmcp import FastMCP

from .auth import build_auth
from .scb_api import SCBClient
from .search import SearchEngine


HOST = os.getenv("FASTMCP_HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", os.getenv("FASTMCP_PORT", "8000")))
_raw_mcp_path = os.getenv("FASTMCP_PATH", "/mcp")
if not _raw_mcp_path.startswith("/"):
    _raw_mcp_path = f"/{_raw_mcp_path}"
if _raw_mcp_path != "/" and _raw_mcp_path.endswith("/"):
    _raw_mcp_path = _raw_mcp_path[:-1]
MCP_PATH = _raw_mcp_path
BASE_URL = os.getenv("FASTMCP_BASE_URL", f"http://localhost:{PORT}")


auth = build_auth(base_url=BASE_URL)
mcp = FastMCP("SSYK MCP Server", auth=auth)

search_engine = SearchEngine()
scb_client = SCBClient()

@mcp.tool()
def classify_occupation(title: str, description: str | None = None) -> List[Dict[str, Any]]:
    """
    Classifies an occupation based on title and (optional) description.
    Returns a list of matching SSYK codes with titles and similarity scores.
    
    Args:
        title: The job title (e.g., "Software Engineer")
        description: Optional description of tasks and responsibilities.
    """
    # Avoid punctuation that can hurt simple BM25 tokenization; the search engine
    # will handle more robust tokenization internally.
    description = (description or "").strip()
    query = f"{title} {description}".strip() if description else title
    results = search_engine.search(query)
    return results

@mcp.tool()
def get_income_statistics(ssyk_code: str) -> Dict[str, Any]:
    """
    Fetches income statistics (median, 25th/75th percentile) for a given SSYK code
    from Statistics Sweden (SCB).
    
    Args:
        ssyk_code: The 4-digit SSYK code (e.g., "2512").
    """
    return scb_client.get_income_statistics(ssyk_code)

if __name__ == "__main__":
    # Preload data if running directly
    search_engine.load_data()
    # Copilot Studio requires Streamable HTTP (SSE is deprecated for new clients).
    mcp.run(transport="http", host=HOST, port=PORT, path=MCP_PATH)
