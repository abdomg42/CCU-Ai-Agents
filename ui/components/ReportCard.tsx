"use client";

import { MappingBadge } from "./MappingBadge";

interface ReportCardProps {
  result: any;
}

export function ReportCard({ result }: ReportCardProps) {
  const root = result?.root_cause || {};
  const mapping = result?.ticket_mapping || {};
  const reportId = result?.report_path?.split("/")?.pop()?.split(".")?.[0] ?? "";
  const incidentId = reportId || result?.incident_id || "unknown";
  const recipients = result?.email_recipients || [];

  return (
    <div
      style={{
        marginTop: "12px",
        padding: "16px",
        background: "#ffffff",
        border: "1px solid #d1d5db",
        borderRadius: "10px",
        boxShadow: "0 2px 6px rgba(0,0,0,0.05)",
      }}
    >
      <div style={{ fontSize: "1rem", fontWeight: 700, color: "#003366", marginBottom: "8px" }}>
        Diagnostic Report
      </div>

      <div style={{ marginBottom: "12px" }}>
        <MappingBadge
          status={mapping.status}
          ticketId={mapping.ticket_id}
          score={mapping.similarity_score}
        />
      </div>

      <div style={{ fontSize: "0.875rem", color: "#374151", marginBottom: "12px" }}>
        <strong>Root cause:</strong> {root.cause || "undetermined"}
        <br />
        <strong>Confidence:</strong> {root.confidence || "N/A"}
      </div>

      <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
        <a
          href={`http://localhost:8000/reports/${reportId}`}
          download
          style={{
            display: "inline-block",
            padding: "8px 14px",
            background: "#003366",
            color: "#fff",
            borderRadius: "6px",
            textDecoration: "none",
            fontSize: "0.875rem",
            fontWeight: 600,
          }}
        >
          Download PDF report
        </a>

        {recipients.length > 0 && result?.email_sent && (
          <span
            style={{
              fontSize: "0.8rem",
              padding: "4px 10px",
              background: "#d1fae5",
              color: "#065f46",
              borderRadius: "999px",
            }}
          >
            Email sent to {recipients.join(", ")}
          </span>
        )}
      </div>
    </div>
  );
}
