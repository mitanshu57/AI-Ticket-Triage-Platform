"""HTTP routes for the tickets module."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.tickets import service
from app.modules.tickets.models import TicketStatus
from app.modules.tickets.schemas import (
    TicketCreate,
    TicketList,
    TicketRead,
    TicketUpdate,
)
from app.modules.triage.dispatch import enqueue_triage

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


async def _get_or_404(session: AsyncSession, ticket_id: uuid.UUID):
    ticket = await service.get_ticket(session, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreate, session: AsyncSession = Depends(get_session)
) -> TicketRead:
    ticket = await service.create_ticket(session, payload)
    from app.core.metrics import inc_ticket_created

    inc_ticket_created()
    # Auto-triage asynchronously when a worker is available; otherwise the
    # ticket stays NEW and can be triaged via POST /{id}/triage.
    await enqueue_triage(session, ticket)
    return TicketRead.model_validate(ticket)


@router.get("", response_model=TicketList)
async def list_tickets(
    session: AsyncSession = Depends(get_session),
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TicketList:
    items, total = await service.list_tickets(
        session, status=status_filter, category=category, limit=limit, offset=offset
    )
    return TicketList(
        items=[TicketRead.model_validate(t) for t in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{ticket_id}", response_model=TicketRead)
async def get_ticket(
    ticket_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> TicketRead:
    ticket = await _get_or_404(session, ticket_id)
    return TicketRead.model_validate(ticket)


@router.patch("/{ticket_id}", response_model=TicketRead)
async def update_ticket(
    ticket_id: uuid.UUID,
    payload: TicketUpdate,
    session: AsyncSession = Depends(get_session),
) -> TicketRead:
    ticket = await _get_or_404(session, ticket_id)
    updated = await service.update_ticket(session, ticket, payload)
    # When a ticket is resolved, index it so it becomes retrievable prior art
    # for future tickets (ADR-0007).
    if updated.status == TicketStatus.RESOLVED:
        from app.modules.retrieval.service import index_resolved_ticket

        await index_resolved_ticket(session, updated)
    return TicketRead.model_validate(updated)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(
    ticket_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    ticket = await _get_or_404(session, ticket_id)
    await service.delete_ticket(session, ticket)
