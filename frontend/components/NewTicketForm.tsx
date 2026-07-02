"use client";

import { useState } from "react";
import { createTicket } from "@/lib/api";
import type { Ticket } from "@/lib/types";

export function NewTicketForm({ onCreated }: { onCreated: (t: Ticket) => void }) {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [email, setEmail] = useState("user@example.com");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const ticket = await createTicket({
        subject,
        body,
        requester_email: email,
      });
      onCreated(ticket);
      setSubject("");
      setBody("");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <label>Subject</label>
      <input value={subject} onChange={(e) => setSubject(e.target.value)} required />
      <label>Body</label>
      <textarea
        value={body}
        rows={4}
        onChange={(e) => setBody(e.target.value)}
        required
      />
      <label>Requester email</label>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <button disabled={busy || !subject || !body}>
        {busy ? "Submitting…" : "Submit ticket"}
      </button>
      {error && <p style={{ color: "var(--red)" }}>{error}</p>}
    </form>
  );
}
