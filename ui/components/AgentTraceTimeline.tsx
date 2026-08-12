"use client";

interface TraceEvent {
  node: string;
  summary: string;
}

interface AgentTraceTimelineProps {
  traces: TraceEvent[];
}

export function AgentTraceTimeline({ traces }: AgentTraceTimelineProps) {
  return (
    <div
      style={{
        marginTop: "12px",
        padding: "12px",
        background: "#f9fafb",
        border: "1px solid #e5e7eb",
        borderRadius: "8px",
      }}
    >
      <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#6b7280", marginBottom: "8px" }}>
        AGENT TRACE
      </div>
      {traces.map((trace, idx) => (
        <div
          key={idx}
          style={{
            display: "flex",
            gap: "10px",
            padding: "6px 0",
            borderBottom: idx < traces.length - 1 ? "1px dashed #e5e7eb" : "none",
          }}
        >
          <div
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: "#003366",
              marginTop: "6px",
              flexShrink: 0,
            }}
          />
          <div>
            <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#003366" }}>
              {trace.node}
            </div>
            <div style={{ fontSize: "0.8rem", color: "#374151" }}>{trace.summary}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
