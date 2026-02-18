import json
import os
import time
import uuid
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
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

_session_locks: dict[tuple[str, str], asyncio.Lock] = {}


def _get_session_lock(user_id: str, session_id: str) -> asyncio.Lock:
    key = (user_id, session_id)
    lock = _session_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[key] = lock
    return lock

session_service = InMemorySessionService()

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    openai_model = os.getenv("OPENAI_MODEL", "")
    azure_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "")
    print(
        "ADK config "
        f"OPENAI_MODEL={openai_model!r} "
        f"AZURE_OPENAI_CHAT_DEPLOYMENT={azure_deployment!r} "
        f"AZURE_OPENAI_ENDPOINT={azure_endpoint!r} "
        f"AZURE_OPENAI_API_VERSION={azure_api_version!r}"
    )
    yield


app = FastAPI(title="SSYK Occupation Advisor", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


_JSON_UTF8 = "application/json; charset=utf-8"
_SSE_UTF8 = "text/event-stream; charset=utf-8"


@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"}, media_type=_JSON_UTF8)


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

    lock = _get_session_lock(user_id, session_id)

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
        async with lock:
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

    return JSONResponse({"response": final_text}, media_type=_JSON_UTF8)


@app.post("/api/chat/stream")
async def chat_stream(request: Request):
    """SSE streaming chat. Body: {message, user_id?, session_id?}"""
    body = await _read_json_body(request)
    message = body.get("message", "")
    user_id = body.get("user_id", "default_user")
    session_id = body.get("session_id", "default_session")

    request_id = uuid.uuid4().hex[:8]
    start_t = time.perf_counter()
    print(
        f"[{request_id}] /api/chat/stream start user_id={user_id} session_id={session_id} "
        f"message_len={len(message or '')}"
    )

    await _ensure_session(user_id, session_id)

    lock = _get_session_lock(user_id, session_id)

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
        first_assistant_t: float | None = None
        try:
            async with lock:
                async for event in runner.run_async(
                    user_id=user_id, session_id=session_id, new_message=content
                ):
                    # 1) MCP tool calls (function calls)
                    for fc in event.get_function_calls():
                        if fc.name in _MCP_TOOL_NAMES:
                            now = time.perf_counter()
                            print(
                                f"[{request_id}] mcp_request tool={fc.name} tool_call_id={fc.id} elapsed_s={now - start_t:.3f}"
                            )
                            payload = {
                                "type": "mcp_request",
                                "tool": {
                                    "id": fc.id,
                                    "name": fc.name,
                                    "args": fc.args or {},
                                },
                            }
                            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                    # 2) MCP tool responses (function responses)
                    for fr in event.get_function_responses():
                        if fr.name in _MCP_TOOL_NAMES:
                            now = time.perf_counter()
                            print(
                                f"[{request_id}] mcp_response tool={fr.name} tool_call_id={fr.id} elapsed_s={now - start_t:.3f}"
                            )
                            payload = {
                                "type": "mcp_response",
                                "tool": {
                                    "id": fr.id,
                                    "name": fr.name,
                                    "response": fr.response or {},
                                },
                            }
                            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                    # 3) Assistant text chunks
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                if first_assistant_t is None:
                                    first_assistant_t = time.perf_counter()
                                    print(
                                        f"[{request_id}] assistant_first_text elapsed_s={first_assistant_t - start_t:.3f}"
                                    )
                                payload = {
                                    "type": "assistant_text",
                                    "text": part.text,
                                    "is_final": event.is_final_response(),
                                }
                                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                    if event.is_final_response():
                        now = time.perf_counter()
                        print(f"[{request_id}] final_response elapsed_s={now - start_t:.3f}")
                        break
        except asyncio.CancelledError:
            now = time.perf_counter()
            print(f"[{request_id}] chat_stream cancelled elapsed_s={now - start_t:.3f}")
            raise
        except Exception as e:
            now = time.perf_counter()
            print(
                f"[{request_id}] chat_stream error type={type(e).__name__} elapsed_s={now - start_t:.3f} msg={e}"
            )
            if LiteLLMRateLimitError is not None and isinstance(e, LiteLLMRateLimitError):
                payload = {"type": "error", "error": "rate_limited", "detail": str(e)}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            elif OpenAIRateLimitError is not None and isinstance(e, OpenAIRateLimitError):
                payload = {"type": "error", "error": "rate_limited", "detail": str(e)}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            else:
                payload = {"type": "error", "error": "internal_error"}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return
        yield "data: [DONE]\n\n"
        end_t = time.perf_counter()
        print(f"[{request_id}] /api/chat/stream done elapsed_s={end_t - start_t:.3f}")

    return StreamingResponse(event_generator(), media_type=_SSE_UTF8)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
