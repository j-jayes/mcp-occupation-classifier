# Microservices Refactoring Checklist - 2025-12-27

> Note: This checklist reflects an earlier phase. The repo has since moved to an MCP-server-only direction.

- [x] Create directory structure (`services/mcp_server`, `pipelines`)
- [x] Move MCP server code to `services/mcp_server`
- [x] Remove ADK agent service
- [x] Move data pipeline code to `pipelines`
- [x] Migrate MCP server from SSE to Streamable HTTP (`server.py`)
- [x] Create `Dockerfile` and `pyproject.toml` for MCP Server
- [x] Update Data Pipeline paths and imports
- [x] Create `docker-compose.yml`
- [ ] Verify local execution
