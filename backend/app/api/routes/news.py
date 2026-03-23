from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_current_user, require_admin
from backend.app.db import get_db
from backend.app.models.schemas import NewsCreateRequest, NewsListResponse, NewsPublic
from backend.app.services import news_service


router = APIRouter(prefix="/news")


@router.get("/public", response_model=NewsListResponse)
async def get_news_feed_public(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
) -> NewsListResponse:
    items = await news_service.list_public_feed(db=db, limit=limit, offset=offset)
    return NewsListResponse(items=[NewsPublic(**item) for item in items])


@router.get("", response_model=NewsListResponse)
async def get_news_feed(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> NewsListResponse:
    items = await news_service.list_feed(db=db, user=current_user, limit=limit, offset=offset)
    return NewsListResponse(items=[NewsPublic(**item) for item in items])


@router.post("", response_model=NewsPublic)
async def create_news_post(
    payload: NewsCreateRequest,
    admin_user: dict = Depends(require_admin),
    db=Depends(get_db),
) -> NewsPublic:
    item = await news_service.create_admin_post(db=db, admin_user=admin_user, payload=payload)
    return NewsPublic(**item)


@router.patch("/{news_id}/pin", response_model=NewsPublic)
async def pin_news(
    news_id: int,
    admin_user: dict = Depends(require_admin),
    db=Depends(get_db),
) -> NewsPublic:
    _ = admin_user
    item = await news_service.pin_news(db=db, news_id=news_id, is_pinned=True)
    return NewsPublic(**item)


@router.patch("/{news_id}/deactivate", response_model=NewsPublic)
async def deactivate_news(
    news_id: int,
    admin_user: dict = Depends(require_admin),
    db=Depends(get_db),
) -> NewsPublic:
    _ = admin_user
    item = await news_service.deactivate_news(db=db, news_id=news_id)
    return NewsPublic(**item)
