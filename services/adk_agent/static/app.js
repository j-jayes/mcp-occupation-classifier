(() => {
  const messagesEl = document.getElementById("messages");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const sendBtn = document.getElementById("send-btn");
  const traceItemsEl = document.getElementById("trace-items");

  let salaryTurn = false;
  let salaryChartEl = null;

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

  function addSalaryChart({ ssyk_code, year, percentiles }) {
    if (!messagesEl) return;
    if (salaryChartEl) {
      salaryChartEl.remove();
      salaryChartEl = null;
    }

    const div = document.createElement("div");
    div.className = "msg salary-chart";

    const title = document.createElement("div");
    title.className = "salary-chart-title";
    title.textContent = "Salary distribution";

    const subtitle = document.createElement("div");
    subtitle.className = "salary-chart-subtitle";
    subtitle.textContent = `SSYK ${ssyk_code} · ${year} · SEK/month`;

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    div.appendChild(title);
    div.appendChild(subtitle);
    div.appendChild(svg);

    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    salaryChartEl = div;

    // Box-plot style chart for a single occupation.
    const p10 = percentiles?.p10 ?? null;
    const p25 = percentiles?.p25 ?? null;
    const median = percentiles?.median ?? null;
    const p75 = percentiles?.p75 ?? null;
    const p90 = percentiles?.p90 ?? null;

    // Require the core box values; whiskers are optional.
    if (p25 == null || median == null || p75 == null) {
      return;
    }

    const whiskerLow = p10 ?? p25;
    const whiskerHigh = p90 ?? p75;
    const minV = Math.min(whiskerLow, p25, median, p75, whiskerHigh);
    const maxV = Math.max(whiskerLow, p25, median, p75, whiskerHigh);

    const tooltipParts = [];
    if (p10 != null) tooltipParts.push(`p10: ${p10}`);
    tooltipParts.push(`p25: ${p25}`);
    tooltipParts.push(`median: ${median}`);
    tooltipParts.push(`p75: ${p75}`);
    if (p90 != null) tooltipParts.push(`p90: ${p90}`);
    const tooltipText = tooltipParts.join(" · ");
    div.title = tooltipText;

    const width = 520;
    const height = 140;
    const padding = { left: 36, right: 16, top: 12, bottom: 28 };
    const midY = 70;
    const boxH = 28;

    const root = d3.select(svg).attr("viewBox", `0 0 ${width} ${height}`);
    root.selectAll("*").remove();

    // Native hover tooltip for the whole chart.
    root.append("title").text(tooltipText);

    const x = d3
      .scaleLinear()
      .domain([minV, maxV])
      .nice()
      .range([padding.left, width - padding.right]);

    // Axis
    root
      .append("g")
      .attr("transform", `translate(0, ${height - padding.bottom})`)
      .call(d3.axisBottom(x).ticks(4).tickSizeOuter(0));

    // Whisker line
    root
      .append("line")
      .attr("x1", x(whiskerLow))
      .attr("x2", x(whiskerHigh))
      .attr("y1", midY)
      .attr("y2", midY)
      .attr("stroke", "#666")
      .attr("stroke-width", 2);

    // Whisker caps
    root
      .append("line")
      .attr("x1", x(whiskerLow))
      .attr("x2", x(whiskerLow))
      .attr("y1", midY - boxH / 2)
      .attr("y2", midY + boxH / 2)
      .attr("stroke", "#666")
      .attr("stroke-width", 2);

    root
      .append("line")
      .attr("x1", x(whiskerHigh))
      .attr("x2", x(whiskerHigh))
      .attr("y1", midY - boxH / 2)
      .attr("y2", midY + boxH / 2)
      .attr("stroke", "#666")
      .attr("stroke-width", 2);

    // Box (p25-p75)
    root
      .append("rect")
      .attr("x", x(p25))
      .attr("y", midY - boxH / 2)
      .attr("width", Math.max(1, x(p75) - x(p25)))
      .attr("height", boxH)
      .attr("fill", "#f7f7f7")
      .attr("stroke", "#666");

    // Median line
    root
      .append("line")
      .attr("x1", x(median))
      .attr("x2", x(median))
      .attr("y1", midY - boxH / 2)
      .attr("y2", midY + boxH / 2)
      .attr("stroke", "#0066cc")
      .attr("stroke-width", 3);
  }

  function isSalaryQuestion(text) {
    const t = (text || "").toLowerCase();
    return (
      t.includes("salary") ||
      t.includes("income") ||
      t.includes("pay") ||
      t.includes("median") ||
      t.includes("percentile") ||
      t.includes("lön") ||
      t.includes("inkomst")
    );
  }

  function extractIncomeStatsFromMcpToolResponse(toolResponse) {
    if (!toolResponse) return null;
    const structured = toolResponse.structuredContent;
    if (structured && typeof structured === "object") return structured;

    const content = toolResponse.content;
    if (Array.isArray(content) && content.length > 0) {
      const first = content[0];
      if (first && typeof first.text === "string") {
        try {
          return JSON.parse(first.text);
        } catch {
          return null;
        }
      }
    }
    return null;
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

    function stripUnsupportedMarkdown(text) {
      // UI renders plain text (textContent). Remove common Markdown markers that
      // otherwise show up literally.
      return (text || "")
        .replace(/\*\*/g, "")
        .replace(/__/g, "")
        .replace(/`/g, "");
    }

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
            assistantEl.textContent = stripUnsupportedMarkdown(assistantText);
          } else if (payload.type === "mcp_request") {
            const tool = payload.tool || {};
            const name = tool.name || "(unknown)";
            addTraceEntry(`\u2192 MCP ${name}`, tool);
          } else if (payload.type === "mcp_response") {
            const tool = payload.tool || {};
            const name = tool.name || "(unknown)";
            addTraceEntry(`\u2190 MCP ${name}`, tool);

            if (name === "get_income_statistics" && salaryTurn) {
              const stats = extractIncomeStatsFromMcpToolResponse(tool.response);
              if (stats && stats.ok === true && stats.percentiles) {
                addSalaryChart(stats);
              }
              salaryTurn = false;
            }
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
    salaryTurn = isSalaryQuestion(text);
    if (salaryChartEl) {
      salaryChartEl.remove();
      salaryChartEl = null;
    }
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
