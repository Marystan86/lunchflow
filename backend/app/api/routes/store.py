from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.api.deps import get_current_user
from backend.app.db import get_db
from backend.app.services import store_service
from backend.app.settings import settings


router = APIRouter(prefix="/store")


class PurchaseRequest(BaseModel):
    product_id: int
    qty: int = 1


def _ensure_store_enabled() -> None:
    if not settings.use_new_store_model:
        raise HTTPException(status_code=503, detail="new store model disabled")


@router.get("/summary")
async def get_store_summary(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    _ensure_store_enabled()
    summary = await store_service.get_user_store_summary(db, user_id=int(current_user["id"]))
    return summary


@router.get("/categories")
async def get_store_categories(db=Depends(get_db)) -> list[dict]:
    _ensure_store_enabled()
    categories = await store_service.list_categories(db)
    return categories


@router.get("/products")
async def get_store_products(
    category: str | None = Query(default=None),
    db=Depends(get_db),
) -> list[dict]:
    _ensure_store_enabled()
    products = await store_service.list_products(db, category_slug=category)
    return products


@router.post("/purchase")
async def post_store_purchase(
    payload: PurchaseRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    _ensure_store_enabled()
    result = await store_service.create_order(
        db,
        user_id=int(current_user["id"]),
        product_id=int(payload.product_id),
        qty=int(payload.qty),
    )
    await db.commit()
    return result
