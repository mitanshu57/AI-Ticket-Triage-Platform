"use client";

import { useState } from "react";
import { triageTicket } from "@/lib/api";
import type { Ticket } from "@/lib/types";

function Badge({ kind, children }: { kind: string; children: React.ReactNode }) {
  return <span className={`badge ${kind}`}>{children}</span>;
}

export function TicketDetail({
  ticket,
  onUpdated,
}: {
  ticket: Ticket;
  onUpdated: (t: Ticket) => void;
}) {
  const [busy, setBusy] = useState(false);

  async function runTriage() {
    setBusy(true);
    try {
      onUpdated(await triageTicket(ticket.id));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <h2>Ticket detail</h2>
      <div style={{ fontWeight: 600, fontSize: 16 }}>{ticket.subject}</div>
      <div className="citation">{ticket.requester_email}</div>

      <div style={{ margin: "12px 0" }}>
        <Badge kind="status">{ticket.status}</Badge>
        {ticket.priority && <Badge kind={ticket.priority}>{ticket.priority}</Badge>}
        {ticket.needs_review && <Badge kind="review">needs review</Badge>}
      </div>

      <div className="draft">{ticket.body}</div>

      <div style={{ marginTop: 16 }}>
        {ticket.category ? (
          <>
            <div className="kv">
              <span className="k">Category</span>
              {ticket.category}
            </div>
            <div className="kv">
              <span className="k">Sentiment</span>
              {ticket.sentiment}
            </div>
            <div className="kv">
              <span className="k">Assigned team</span>
              {ticket.assigned_team}
            </div>
            <div className="kv">
              <span className="k">Summary</span>
              {ticket.ai_summary}
            </div>

            <h2 style={{ marginTop: 16 }}>Suggested reply</h2>
            <div className="draft">{ticket.ai_draft_reply}</div>

            {ticket.ai_citations && ticket.ai_citations.length > 0 && (
              <div style={{ marginTop: 8 }}>
                {ticket.ai_citations.map((c) => (
                  <div className="citation" key={c.ref}>
                    [{c.ref}] {c.source_type}: {c.title} (score {c.score.toFixed(2)})
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <p className="citation">Not yet triaged.</p>
        )}

        <button onClick={runTriage} disabled={busy}>
          {busy ? "Triaging…" : "Run triage"}
        </button>
      </div>
    </div>
  );
}
