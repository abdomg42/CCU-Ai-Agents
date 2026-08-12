"use client";

interface MappingBadgeProps {
  status: string;
  ticketId?: string;
  score?: number;
}

export function MappingBadge({ status, ticketId, score }: MappingBadgeProps) {
  const isLinked = status === "linked_to_existing";
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "8px",
        padding: "6px 12px",
        borderRadius: "999px",
        fontSize: "0.875rem",
        fontWeight: 600,
        background: isLinked ? "#fff2cc" : "#e6f2ff",
        color: isLinked ? "#806000" : "#004080",
      }}
    >
      {isLinked
        ? `Similar incident found (ticket #${ticketId ?? "N/A"})`
        : `New ticket created (#${ticketId ?? "N/A"})`}
      {score !== undefined && score > 0 && (
        <span style={{ fontSize: "0.75rem", opacity: 0.8 }}>
          score {score.toFixed(2)}
        </span>
      )}
    </div>
  );
}
