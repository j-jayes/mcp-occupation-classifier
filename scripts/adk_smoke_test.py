import argparse
import json
import time
import re
from typing import Any

import requests


def _iter_sse_lines(response: requests.Response):
    for raw in response.iter_lines(decode_unicode=True):
        if raw is None:
            continue
        line = raw.strip()
        if not line:
            continue
        if line.startswith("data: "):
            yield line[len("data: ") :]


def _extract_top_ssyk_from_classify_response(obj: dict[str, Any]) -> str | None:
    try:
        tool = obj.get("tool") or {}
        response = tool.get("response") or {}
        structured = response.get("structuredContent") or {}
        result = structured.get("result")
        if not isinstance(result, list) or not result:
            return None
        top = result[0]
        if not isinstance(top, dict):
            return None
        code = top.get("ssyk_code")
        if isinstance(code, str) and code.strip():
            return code.strip()
        return None
    except Exception:
        return None


def _extract_top_ssyk_from_assistant_text(text: str) -> str | None:
    # Common formatting in the agent response: "SSYK Code: 2511".
    m = re.search(r"SSYK\s*Code\s*[:#]?\s*(\d{4})", text, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    # Fallback: first 4-digit number.
    m = re.search(r"\b(\d{4})\b", text)
    if m:
        return m.group(1)
    return None


def _run_stream(url: str, payload: dict[str, Any], max_wait_s: float) -> str | None:
    """Run one SSE request; return the top SSYK code if found."""
    top_ssyk: str | None = None

    with requests.post(url, json=payload, stream=True, timeout=300) as r:
        print(f"status={r.status_code}")
        r.raise_for_status()

        start = time.time()
        for data in _iter_sse_lines(r):
            if data == "[DONE]":
                print("[DONE]")
                return top_ssyk

            try:
                obj = json.loads(data)
                print(json.dumps(obj, ensure_ascii=False))

                if isinstance(obj, dict) and obj.get("type") == "mcp_response":
                    tool = obj.get("tool") or {}
                    if tool.get("name") == "classify_occupation":
                        top_ssyk = top_ssyk or _extract_top_ssyk_from_classify_response(obj)

                if isinstance(obj, dict) and obj.get("type") == "assistant_text":
                    txt = obj.get("text")
                    if isinstance(txt, str) and txt:
                        top_ssyk = top_ssyk or _extract_top_ssyk_from_assistant_text(txt)

                if isinstance(obj, dict) and obj.get("type") == "error":
                    return top_ssyk
            except Exception:
                print(data)

            if time.time() - start > max_wait_s:
                print(f"timeout waiting for [DONE] after {max_wait_s}s")
                return top_ssyk


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test the ADK agent SSE endpoint")
    parser.add_argument("--url", default="http://127.0.0.1:8080/api/chat/stream")
    parser.add_argument("--message", default="Classify the occupation title: Data Scientist")
    parser.add_argument("--user-id", default="smoke")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--max-wait-s", type=float, default=90)
    args = parser.parse_args()

    session_id = args.session_id.strip() if isinstance(args.session_id, str) else ""
    if not session_id:
        session_id = f"smoke-{int(time.time())}"
        print(f"session_id={session_id}")

    payload: dict[str, Any] = {
        "message": args.message,
        "user_id": args.user_id,
        "session_id": session_id,
    }

    top_ssyk = _run_stream(args.url, payload, args.max_wait_s)

    if not top_ssyk:
        print("no top SSYK code found; skipping salary request")
        return

    print(f"requesting salary stats for SSYK {top_ssyk}")
    salary_payload: dict[str, Any] = {
        "message": f"Get income statistics for SSYK code {top_ssyk}.",
        "user_id": args.user_id,
        "session_id": session_id,
    }
    _run_stream(args.url, salary_payload, args.max_wait_s)


if __name__ == "__main__":
    main()
