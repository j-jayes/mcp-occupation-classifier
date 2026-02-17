(() => {
  const messagesEl = document.getElementById("messages");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const sendBtn = document.getElementById("send-btn");
  const traceItemsEl = document.getElementById("trace-items");

  // Persist identifiers across page reloads within the same browser tab.
  const userId =
    sessionStorage.getItem("userId") ||
    (() => {
      const id = "u_" + crypto.randomUUID();
      sessionStorage.setItem("userId", id);
      return id;
    })();

  const sessionId =
    sessionStorage.getItem("sessionId") ||
    (() => {
      const id = "s_" + crypto.randomUUID();
      sessionStorage.setItem("sessionId", id);
      return id;
    })();

  function addMessage(text, role) {
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function clearTrace() {
    if (!traceItemsEl) return;
    traceItemsEl.innerHTML = "";
  }

  function addTraceEntry(summary, obj) {
    if (!traceItemsEl) return;

    const details = document.createElement("details");
    details.className = "trace-item";

    const sum = document.createElement("summary");
    sum.textContent = summary;
    details.appendChild(sum);

    const pre = document.createElement("pre");
    try {
      pre.textContent = JSON.stringify(obj, null, 2);
    } catch {
      pre.textContent = String(obj);
    }
    details.appendChild(pre);

    traceItemsEl.appendChild(details);
    traceItemsEl.scrollTop = traceItemsEl.scrollHeight;
  }

  function setLoading(on) {
    sendBtn.disabled = on;
    if (on) {
      addMessage("Thinking\u2026", "loading");
    } else {
      const loader = messagesEl.querySelector(".msg.loading");
      if (loader) loader.remove();
    }
  }

  async function streamChat(message) {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        user_id: userId,
        session_id: sessionId,
      }),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || res.statusText);
    }

    if (!res.body) {
      throw new Error("Streaming not supported by this browser");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    // We'll build the assistant response incrementally.
    let assistantEl = null;
    let assistantText = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line.
      const frames = buffer.split("\n\n");
      buffer = frames.pop() || "";

      for (const frame of frames) {
        const lines = frame.split("\n");
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const data = line.slice(5).trim();
          if (!data) continue;
          if (data === "[DONE]") return;

          let payload;
          try {
            payload = JSON.parse(data);
          } catch {
            continue;
          }

          if (payload.type === "assistant_text") {
            // Replace the loader with a live assistant bubble on first chunk.
            if (!assistantEl) {
              setLoading(false);
              assistantEl = addMessage("", "assistant");
            }
            assistantText += payload.text || "";
            assistantEl.textContent = assistantText;
          } else if (payload.type === "mcp_request") {
            const tool = payload.tool || {};
            const name = tool.name || "(unknown)";
            addTraceEntry(`\u2192 MCP ${name}`, tool);
          } else if (payload.type === "mcp_response") {
            const tool = payload.tool || {};
            const name = tool.name || "(unknown)";
            addTraceEntry(`\u2190 MCP ${name}`, tool);
          } else if (payload.type === "error") {
            throw new Error(payload.detail || payload.error || "Unknown error");
          }
        }
      }
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    addMessage(text, "user");
    input.value = "";
    clearTrace();
    setLoading(true);

    try {
      await streamChat(text);
      setLoading(false);
    } catch (err) {
      setLoading(false);
      addMessage("Error: " + err.message, "assistant");
    }
  });

  input.focus();
})();
