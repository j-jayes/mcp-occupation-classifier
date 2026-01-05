from google.adk.agents import LlmAgent
from google.genai import types
import os
import base64
import io
import json
from typing import Union
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

# Define the MCP Tool Wrapper
async def call_ssyk_mcp_tool(tool_name: str, arguments: dict) -> str:
    """
    Calls a tool on the SSYK MCP Server via SSE.
    
    Args:
        tool_name: The name of the tool to call. Available tools:
                   - classify_occupation(title: str, description: str)
                   - get_income_statistics(ssyk_code: str)
        arguments: A dictionary of arguments for the tool.
    """
    # Configuration for the MCP Server
    mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000/sse")

    # Import MCP client bits lazily to avoid leaking non-pydantic types into
    # ADK Web's OpenAPI schema generation.
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async with sse_client(mcp_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Call the tool
            result = await session.call_tool(tool_name, arguments)
            
            # Return the text content
            if result.content and len(result.content) > 0:
                return result.content[0].text
            return "No output returned."

async def visualize_income_statistics(ssyk_code: str) -> Union[types.Part, str]:
    """
    Creates visualizations (box plot and table) for income statistics of a given SSYK code.
    
    Args:
        ssyk_code: The SSYK occupation code (e.g., "2422" for Financial analysts)
    
    Returns:
        A Part object containing the visualization image, or an error string.
    """
    # Get the income data directly from the MCP server
    mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000/sse")
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    
    try:
        async with sse_client(mcp_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("get_income_statistics", {"ssyk_code": ssyk_code})
                
                # Parse the result - it should be JSON text
                income_text = result.content[0].text if result.content else "{}"
                income_data = json.loads(income_text)
                
                # Check for error
                if "error" in income_data:
                    return f"❌ {income_data['error']}"
                
                # Extract data (Swedish keys)
                average = income_data.get("Månadslön", 0)
                median = income_data.get("Medianlön", 0)
                p10 = income_data.get("10:e percentilen", 0)
                p25 = income_data.get("25:e percentilen", 0)
                p75 = income_data.get("75:e percentilen", 0)
                p90 = income_data.get("90:e percentilen", 0)
                
                # Set style
                sns.set_style("whitegrid")
                sns.set_palette("husl")
                
                # Create figure with two subplots
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
                
                # Box and whisker plot data
                plot_data = [p10, p25, median, p75, p90]
                
                # Create boxplot
                box = ax1.boxplot([plot_data], vert=True, widths=0.5, patch_artist=True,
                                 boxprops=dict(facecolor='lightblue', alpha=0.7),
                                 medianprops=dict(color='red', linewidth=2),
                                 whiskerprops=dict(color='blue', linewidth=1.5),
                                 capprops=dict(color='blue', linewidth=1.5))
                
                ax1.set_ylabel('Monthly Salary (SEK)', fontsize=12, fontweight='bold')
                ax1.set_title(f'Income Distribution for SSYK {ssyk_code}', fontsize=14, fontweight='bold')
                ax1.set_xticklabels(['Salary Distribution'])
                ax1.grid(True, alpha=0.3)
                
                # Add value labels
                labels_text = ['10th', '25th', 'Median', '75th', '90th']
                for i, (val, label) in enumerate(zip(plot_data, labels_text)):
                    ax1.text(1.15, val, f'{label}: {val:,.0f} SEK', va='center', fontsize=9)
                
                # Table
                table_data = [
                    ['Average Monthly Salary', f'{average:,.0f} SEK'],
                    ['Median Monthly Salary', f'{median:,.0f} SEK'],
                    ['10th Percentile', f'{p10:,.0f} SEK'],
                    ['25th Percentile', f'{p25:,.0f} SEK'],
                    ['75th Percentile', f'{p75:,.0f} SEK'],
                    ['90th Percentile', f'{p90:,.0f} SEK']
                ]
                
                ax2.axis('tight')
                ax2.axis('off')
                
                table = ax2.table(cellText=table_data,
                                 colLabels=['Statistic', 'Value'],
                                 cellLoc='left',
                                 loc='center',
                                 colWidths=[0.6, 0.4])
                
                table.auto_set_font_size(False)
                table.set_fontsize(10)
                table.scale(1, 2)
                
                # Style header
                for i in range(2):
                    table[(0, i)].set_facecolor('#4CAF50')
                    table[(0, i)].set_text_props(weight='bold', color='white')
                
                # Alternate row colors
                for i in range(1, len(table_data) + 1):
                    for j in range(2):
                        if i % 2 == 0:
                            table[(i, j)].set_facecolor('#f0f0f0')
                
                ax2.set_title('Income Statistics Summary', fontsize=14, fontweight='bold', pad=20)
                
                plt.tight_layout()
                
                # Save to bytes buffer
                buffer = io.BytesIO()
                plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
                buffer.seek(0)
                image_bytes = buffer.read()
                plt.close()
                
                # Return as a Part object with image bytes (using keyword arguments)
                return types.Part.from_bytes(data=image_bytes, mime_type="image/png")
                
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"❌ Error creating visualization: {str(e)}\n\nDetails:\n{error_details}"

# Define the Agent
root_agent = LlmAgent(
    name="ssyk_advisor",
    description="An expert advisor on Swedish occupations and salaries.",
    model="gemini-2.5-flash", # Or any other supported model
    instruction="""
    You are a helpful assistant that helps users find Swedish occupation codes (SSYK) and salary information.
    
    You have access to tools that interface with a specialized MCP server and create visualizations.
    
    When a user asks about a job:
    1. First, use `call_ssyk_mcp_tool` to find the correct SSYK code and title.
       - Arguments: {"tool_name": "classify_occupation", "arguments": {"title": "...", "description": "..."}}
    
    2. When the user asks for salary information, you should call BOTH tools in sequence:
       a) FIRST: Call `call_ssyk_mcp_tool` with `get_income_statistics` to get the detailed text statistics
          - Arguments: {"tool_name": "get_income_statistics", "arguments": {"ssyk_code": "..."}}
          - Present this information clearly to the user
       b) THEN: Call `visualize_income_statistics` with the SSYK code to create and display the chart
          - Arguments: {"ssyk_code": "..."}
          - This will return an image - simply tell the user "Here is the income visualization:" and the image will be displayed automatically
       
    IMPORTANT: After calling `visualize_income_statistics`, the chart is automatically attached to your response.
    You do NOT need to describe the image or repeat the statistics - just acknowledge that the visualization has been created.
    Say something brief like "Here is the visualization of the income distribution:" and move on.
    """,
    tools=[call_ssyk_mcp_tool, visualize_income_statistics]
)

# Backwards-compat alias (some examples/tools refer to `agent`)
agent = root_agent
