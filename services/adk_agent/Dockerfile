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
EXPOSE 9090

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV MCP_SERVER_URL="http://mcp-server:8000/sse"

# Run ADK Web
WORKDIR /app/src
CMD ["uv", "run", "adk", "web", "--host", "0.0.0.0", "--port", "9090"]
