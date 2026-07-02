export interface Citation {
  ref: number;
  source_type: string;
  source_id: string;
  title: string;
  score: number;
}

export interface Ticket {
  id: string;
  subject: string;
  body: string;
  requester_email: string;
  status: string;
  category: string | null;
  priority: string | null;
  sentiment: string | null;
  assigned_team: string | null;
  ai_summary: string | null;
  ai_draft_reply: string | null;
  ai_citations: Citation[] | null;
  needs_review: boolean;
  created_at: string;
  updated_at: string;
}

export interface TicketListResponse {
  items: Ticket[];
  total: number;
  limit: number;
  offset: number;
}

export interface TicketEvent {
  event: string;
  ticket: Ticket;
}
