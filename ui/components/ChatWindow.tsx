"use client";

import { useState } from "react";
import { AgentTraceTimeline } from "./AgentTraceTimeline";
import { ReportCard } from "./ReportCard";

type Message =
  | { role: "user"; text: string }
  | { role: "agent"; traces: { node: string; summary: string }[]; final?: any };

export function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isRunning, setIsRunning] = useState(false);

  const sendMessage = async () => {
    if (!input.trim() || isRunning) return;

    const text = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    setIsRunning(true);

    const traceIndex = messages.length + 1;
    setMessages((prev) => [...prev, { role: "agent", traces: [] }]);

    try {
      const response = await fetch("/api/diagnose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response stream");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const json = line.slice(6).trim();
          if (!json) continue;

          try {
            const event = JSON.parse(json);
            if (event.node === "final") {
              setMessages((prev) => {
                const next = [...prev];
                const agentMsg = next[traceIndex] as { role: "agent"; traces: any[]; final?: any };
                agentMsg.final = event.result;
                return next;
              });
            } else {
              setMessages((prev) => {
                const next = [...prev];
                const agentMsg = next[traceIndex] as { role: "agent"; traces: any[] };
                agentMsg.traces = [...agentMsg.traces, { node: event.node, summary: event.summary }];
                return next;
              });
            }
          } catch {
            // ignore malformed lines
          }
        }
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "agent", traces: [{ node: "error", summary: String(err) }] },
      ]);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, gap: "16px" }}>
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "12px" }}>
        {messages.map((msg, idx) =>
          msg.role === "user" ? (
            <div
              key={idx}
              style={{
                alignSelf: "flex-end",
                maxWidth: "80%",
                padding: "10px 14px",
                background: "#003366",
                color: "#fff",
                borderRadius: "12px 12px 0 12px",
                fontSize: "0.95rem",
              }}
            >
              {msg.text}
            </div>
          ) : (
            <div
              key={idx}
              style={{
                alignSelf: "flex-start",
                maxWidth: "90%",
                padding: "10px 14px",
                background: "#ffffff",
                border: "1px solid #e5e7eb",
                borderRadius: "12px 12px 12px 0",
                fontSize: "0.95rem",
              }}
            >
              <div style={{ fontWeight: 600, color: "#003366", marginBottom: "4px" }}>
                Diagnostic Agent
              </div>
              {msg.traces.length > 0 && <AgentTraceTimeline traces={msg.traces} />}
              {msg.final && <ReportCard result={msg.final} />}
            </div>
          )
        )}
      </div>

      <div style={{ display: "flex", gap: "8px" }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder="Describe the incident in natural language..."
          disabled={isRunning}
          style={{
            flex: 1,
            padding: "12px 14px",
            border: "1px solid #d1d5db",
            borderRadius: "8px",
            fontSize: "0.95rem",
          }}
        />
        <button
          onClick={sendMessage}
          disabled={isRunning || !input.trim()}
          style={{
            padding: "12px 18px",
            background: isRunning ? "#9ca3af" : "#003366",
            color: "#fff",
            border: "none",
            borderRadius: "8px",
            fontWeight: 600,
            cursor: isRunning ? "not-allowed" : "pointer",
          }}
        >
          {isRunning ? "Running..." : "Send"}
        </button>
      </div>
    </div>
  );
}
