"""Knowledge-base endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.retrieval import service
from app.modules.retrieval.repository import get_knowledge_repository
from app.modules.retrieval.schemas import KBArticleCreate

router = APIRouter(prefix="/api/v1/kb", tags=["knowledge-base"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_kb_article(
    payload: KBArticleCreate, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    """Create a KB article: embed it and store it for retrieval."""
    article_id = await service.add_kb_article(session, payload.title, payload.content)
    return {"id": article_id, "title": payload.title}


@router.get("")
async def list_kb_articles(
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, str]]:
    repo = get_knowledge_repository(session)
    return [{"id": sid, "title": title} for sid, title in await repo.list_kb_articles()]
