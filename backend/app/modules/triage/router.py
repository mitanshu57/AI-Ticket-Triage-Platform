"""HTTP routes for triggering triage.

If a queue is configured the work is enqueued (202, ticket → TRIAGING) and the
worker publishes the result over WebSocket. Otherwise triage runs inline (200)
and the result is published from here.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.realtime.events import publish_ticket_event
from app.modules.tickets import service as ticket_service
from app.modules.tickets.schemas import TicketRead
from app.modules.triage import service as triage_service
from app.modules.triage.dispatch import enqueue_triage

router = APIRouter(prefix="/api/v1/tickets", tags=["triage"])


@router.post("/{ticket_id}/triage", response_model=TicketRead)
async def triage_ticket_endpoint(
    ticket_id: uuid.UUID,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TicketRead:
    """Run AI triage on a ticket (async if a worker is available, else inline)."""
    ticket = await ticket_service.get_ticket(session, ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
        )

    if await enqueue_triage(session, ticket):
        # Accepted for async processing; worker will publish when done.
        response.status_code = status.HTTP_202_ACCEPTED
    else:
        await triage_service.triage_ticket(session, ticket)
        await publish_ticket_event(ticket)

    return TicketRead.model_validate(ticket)
