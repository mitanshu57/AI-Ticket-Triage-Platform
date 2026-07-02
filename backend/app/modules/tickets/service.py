"""Ticket service layer — all DB access for the tickets module lives here.

Keeping persistence logic out of the router is what lets other modules (e.g. the
Phase 2 triage worker) reuse ticket operations through a stable interface
(ADR-0002).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tickets.models import Ticket, TicketStatus
from app.modules.tickets.schemas import TicketCreate, TicketUpdate


async def create_ticket(session: AsyncSession, data: TicketCreate) -> Ticket:
    ticket = Ticket(
        subject=data.subject,
        body=data.body,
        requester_email=data.requester_email,
        status=TicketStatus.NEW,
    )
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def get_ticket(session: AsyncSession, ticket_id: uuid.UUID) -> Ticket | None:
    return await session.get(Ticket, ticket_id)


async def list_tickets(
    session: AsyncSession,
    *,
    status: TicketStatus | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Ticket], int]:
    """Return (items, total) for a filtered, paginated query."""
    filters = []
    if status is not None:
        filters.append(Ticket.status == status)
    if category is not None:
        filters.append(Ticket.category == category)

    items_stmt = (
        select(Ticket)
        .where(*filters)
        .order_by(Ticket.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    count_stmt = select(func.count()).select_from(Ticket).where(*filters)

    items = list((await session.scalars(items_stmt)).all())
    total = (await session.scalar(count_stmt)) or 0
    return items, total


async def update_ticket(
    session: AsyncSession, ticket: Ticket, data: TicketUpdate
) -> Ticket:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ticket, field, value)
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def delete_ticket(session: AsyncSession, ticket: Ticket) -> None:
    await session.delete(ticket)
    await session.commit()
