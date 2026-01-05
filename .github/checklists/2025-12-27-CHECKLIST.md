# Implementation Checklist

## 1. Data Pipeline Refactoring
- [ ] Move ingestion logic to `src/data_pipeline/`
- [ ] Create `ingest_all.py`
    - [ ] Download SSYK taxonomy
    - [ ] Fetch *all* SCB income stats (batch/iterate)
    - [ ] Save `income_stats.json`
    - [ ] Generate embeddings & save `ssyk_data.parquet`

## 2. MCP Server Update
- [ ] Modify `src/ssyk_mcp/server.py`
    - [ ] Load `income_stats.json` on startup
    - [ ] Update `get_income_statistics` to use local JSON lookup
    - [ ] Ensure `classify_occupation` uses `ssyk_data.parquet`

## 3. ADK Agent Implementation
- [ ] Create `agents/ssyk_advisor/agent.py`
    - [ ] Define `LlmAgent` (Gemini)
    - [ ] Implement `call_ssyk_mcp` tool (using `mcp` python client)
    - [ ] Register tool with agent

## 4. Docker & ADK Web
- [ ] Create `Dockerfile` (Single container for simplicity initially)
- [ ] Create `docker-compose.yml`
- [ ] Verify `adk web` works with the agent

## 5. Verification
- [ ] Run ingestion
- [ ] Run `adk web`
- [ ] Test chat interaction
