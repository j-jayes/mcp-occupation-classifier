from mcp.server.fastmcp import FastMCP
from .search import SearchEngine
from .scb_api import SCBClient
from typing import List, Dict, Any
import os

# Initialize Server with network binding configuration
mcp = FastMCP(
    "SSYK Agent",
    host=os.getenv("FASTMCP_HOST", "127.0.0.1"),
    port=int(os.getenv("FASTMCP_PORT", "8000"))
)

# Initialize Components
search_engine = SearchEngine()
scb_client = SCBClient()

@mcp.tool()
def classify_occupation(title: str, description: str) -> List[Dict[str, Any]]:
    """
    Classifies an occupation based on title and description.
    Returns a list of matching SSYK codes with titles and similarity scores.
    
    Args:
        title: The job title (e.g., "Software Engineer")
        description: A description of the tasks and responsibilities.
    """
    query = f"{title}: {description}"
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
    mcp.run(transport="sse")
