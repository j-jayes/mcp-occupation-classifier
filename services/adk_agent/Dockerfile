FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY services/adk_agent/pyproject.toml ./pyproject.toml
COPY services/adk_agent/uv.lock ./uv.lock
COPY services/adk_agent/src ./src
COPY services/adk_agent/static ./static

# Install dependencies
RUN uv sync --frozen

# Expose port
EXPOSE 8080

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Run the ADK agent API server
CMD ["python", "-m", "adk_agent.app"]
