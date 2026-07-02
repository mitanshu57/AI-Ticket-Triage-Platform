"""WebSocket route for live ticket updates (ADR-0008/0009)."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.modules.realtime.broker import get_broker
from app.modules.realtime.events import TICKETS_CHANNEL

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/tickets")
async def tickets_ws(websocket: WebSocket) -> None:
    """Stream ticket events to the client until it disconnects.

    Backed by the pub/sub broker, so triage results pushed from the worker (or
    inline) arrive here in real time.
    """
    await websocket.accept()
    broker = get_broker()
    try:
        async for message in broker.subscribe(TICKETS_CHANNEL):
            await websocket.send_text(message)
    except WebSocketDisconnect:
        return
