import json
import os
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .agent import root_agent

try:
    from litellm.exceptions import RateLimitError as LiteLLMRateLimitError  # type: ignore
except Exception:  # pragma: no cover
    LiteLLMRateLimitError = None  # type: ignore

try:
    from openai import RateLimitError as OpenAIRateLimitError  # type: ignore
except Exception:  # pragma: no cover
    OpenAIRateLimitError = None  # type: ignore

APP_NAME = "occupation_advisor"
HOST = os.getenv("ADK_HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", os.getenv("ADK_PORT", "8080")))

_MCP_TOOL_NAMES = {"classify_occupation", "get_income_statistics"}

session_service = InMemorySessionService()

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="SSYK Occupation Advisor", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/health")
async def health():
    return {"status": "ok"}


async def _ensure_session(user_id: str, session_id: str):
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
    return session


async def _read_json_body(request: Request) -> dict:
    """Read JSON body robustly.

    Some clients (notably Windows PowerShell) may send UTF-16 encoded JSON by default.
    Starlette expects UTF-8 and can raise UnicodeDecodeError.
    """
    try:
        body = await request.json()
        if isinstance(body, dict):
            return body
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
    except UnicodeDecodeError:
        raw = await request.body()
        for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16le", "utf-16be"):
            try:
                parsed = json.loads(raw.decode(encoding))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON encoding. Send UTF-8 (recommended) or UTF-16.",
        )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e.msg}")


@app.post("/api/chat")
async def chat(request: Request):
    """Non-streaming chat. Body: {message, user_id?, session_id?}"""
    body = await _read_json_body(request)
    message = body.get("message", "")
    user_id = body.get("user_id", "default_user")
    session_id = body.get("session_id", "default_session")

    await _ensure_session(user_id, session_id)

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    content = types.Content(
        role="user",
        parts=[types.Part(text=message)],
    )

    final_text = ""
    try:
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=content
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = event.content.parts[0].text
                break
    except Exception as e:
        if LiteLLMRateLimitError is not None and isinstance(e, LiteLLMRateLimitError):
            raise HTTPException(status_code=429, detail=str(e))
        if OpenAIRateLimitError is not None and isinstance(e, OpenAIRateLimitError):
            raise HTTPException(status_code=429, detail=str(e))
        raise

    return {"response": final_text}


@app.post("/api/chat/stream")
async def chat_stream(request: Request):
    """SSE streaming chat. Body: {message, user_id?, session_id?}"""
    body = await _read_json_body(request)
    message = body.get("message", "")
    user_id = body.get("user_id", "default_user")
    session_id = body.get("session_id", "default_session")

    await _ensure_session(user_id, session_id)

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    content = types.Content(
        role="user",
        parts=[types.Part(text=message)],
    )

    async def event_generator():
        try:
            async for event in runner.run_async(
                user_id=user_id, session_id=session_id, new_message=content
            ):
                # 1) MCP tool calls (function calls)
                for fc in event.get_function_calls():
                    if fc.name in _MCP_TOOL_NAMES:
                        payload = {
                            "type": "mcp_request",
                            "tool": {
                                "id": fc.id,
                                "name": fc.name,
                                "args": fc.args or {},
                            },
                        }
                        yield f"data: {json.dumps(payload)}\n\n"

                # 2) MCP tool responses (function responses)
                for fr in event.get_function_responses():
                    if fr.name in _MCP_TOOL_NAMES:
                        payload = {
                            "type": "mcp_response",
                            "tool": {
                                "id": fr.id,
                                "name": fr.name,
                                "response": fr.response or {},
                            },
                        }
                        yield f"data: {json.dumps(payload)}\n\n"

                # 3) Assistant text chunks
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            payload = {
                                "type": "assistant_text",
                                "text": part.text,
                                "is_final": event.is_final_response(),
                            }
                            yield f"data: {json.dumps(payload)}\n\n"

                if event.is_final_response():
                    break
        except Exception as e:
            if LiteLLMRateLimitError is not None and isinstance(e, LiteLLMRateLimitError):
                payload = {"type": "error", "error": "rate_limited", "detail": str(e)}
                yield f"data: {json.dumps(payload)}\n\n"
            elif OpenAIRateLimitError is not None and isinstance(e, OpenAIRateLimitError):
                payload = {"type": "error", "error": "rate_limited", "detail": str(e)}
                yield f"data: {json.dumps(payload)}\n\n"
            else:
                payload = {"type": "error", "error": "internal_error"}
                yield f"data: {json.dumps(payload)}\n\n"
            yield "data: [DONE]\n\n"
            return
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
