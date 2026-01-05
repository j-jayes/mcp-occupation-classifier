FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml ./
COPY src ./src

# Install dependencies
RUN uv sync

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/app/data

# Run MCP Server
CMD ["uv", "run", "python", "-m", "ssyk_mcp.server"]
