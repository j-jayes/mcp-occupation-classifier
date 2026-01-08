FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy server project files
COPY services/mcp_server/pyproject.toml ./pyproject.toml
COPY services/mcp_server/src ./src

# Bake data into the image (small dataset)
COPY data ./data

# Install dependencies
RUN uv sync

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/app/data

# Run MCP Server
CMD ["python", "-m", "ssyk_mcp.server"]

