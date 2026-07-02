"use client";

import { useCallback, useEffect, useState } from "react";
import { listTickets } from "@/lib/api";
import { useTicketStream } from "@/lib/useTicketStream";
import type { Ticket } from "@/lib/types";
import { NewTicketForm } from "@/components/NewTicketForm";
import { TicketDetail } from "@/components/TicketDetail";

export default function Home() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const upsert = useCallback((t: Ticket) => {
    setTickets((prev) => {
      const idx = prev.findIndex((x) => x.id === t.id);
      if (idx === -1) return [t, ...prev];
      const next = [...prev];
      next[idx] = t;
      return next;
    });
  }, []);

  useEffect(() => {
    listTickets()
      .then((r) => setTickets(r.items))
      .catch(() => setTickets([]));
  }, []);

  // Live updates from the worker / inline triage.
  const { connected } = useTicketStream((e) => upsert(e.ticket));

  const selected = tickets.find((t) => t.id === selectedId) ?? null;

  return (
    <>
      <div className="header">
        <h1>AI Ticket Triage</h1>
        <span className="citation">
          <span className={`dot ${connected ? "on" : "off"}`} />
          {connected ? "live" : "offline"}
        </span>
      </div>

      <div className="layout">
        <div>
          <div className="panel" style={{ marginBottom: 16 }}>
            <h2>New ticket</h2>
            <NewTicketForm
              onCreated={(t) => {
                upsert(t);
                setSelectedId(t.id);
              }}
            />
          </div>

          <div className="panel">
            <h2>Tickets ({tickets.length})</h2>
            {tickets.length === 0 && <div className="empty">No tickets yet.</div>}
            {tickets.map((t) => (
              <div
                key={t.id}
                className={`ticket ${t.id === selectedId ? "selected" : ""}`}
                onClick={() => setSelectedId(t.id)}
              >
                <div className="subj">{t.subject}</div>
                <div className="meta">
                  {t.status}
                  {t.category ? ` · ${t.category}` : ""}
                  {t.priority ? ` · ${t.priority}` : ""}
                  {t.needs_review ? " · ⚠ review" : ""}
                </div>
              </div>
            ))}
          </div>
        </div>

        {selected ? (
          <TicketDetail ticket={selected} onUpdated={upsert} />
        ) : (
          <div className="panel">
            <div className="empty">Select a ticket to view AI triage results.</div>
          </div>
        )}
      </div>
    </>
  );
}
