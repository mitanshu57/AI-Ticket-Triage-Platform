import type { Ticket, TicketListResponse } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export async function listTickets(): Promise<TicketListResponse> {
  return json(await fetch(`${API_BASE}/api/v1/tickets`, { cache: "no-store" }));
}

export async function createTicket(input: {
  subject: string;
  body: string;
  requester_email: string;
}): Promise<Ticket> {
  return json(
    await fetch(`${API_BASE}/api/v1/tickets`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function triageTicket(id: string): Promise<Ticket> {
  return json(
    await fetch(`${API_BASE}/api/v1/tickets/${id}/triage`, { method: "POST" }),
  );
}

export function wsUrl(): string {
  return `${API_BASE.replace(/^http/, "ws")}/ws/tickets`;
}
