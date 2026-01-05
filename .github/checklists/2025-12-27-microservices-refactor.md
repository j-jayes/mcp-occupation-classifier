# Microservices Refactoring Checklist - 2025-12-27

- [x] Create directory structure (`services/mcp_server`, `services/adk_agent`, `pipelines`)
- [x] Move MCP server code to `services/mcp_server`
- [x] Move ADK agent code to `services/adk_agent`
- [x] Move data pipeline code to `pipelines`
- [x] Configure MCP Server for SSE (`server.py`)
- [x] Create `Dockerfile` and `pyproject.toml` for MCP Server
- [x] Configure ADK Agent for SSE (`agent.py`)
- [x] Create `Dockerfile` and `pyproject.toml` for ADK Agent
- [x] Update Data Pipeline paths and imports
- [x] Create `docker-compose.yml`
- [ ] Verify local execution
