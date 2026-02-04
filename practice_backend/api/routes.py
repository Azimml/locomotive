from fastapi import APIRouter, HTTPException

from schemas.items import ItemCreate, ItemRead
from db.store import create_item, list_items, get_item
from api.ai import router as ai_router

router = APIRouter(tags=["items"])
router.include_router(ai_router, prefix="/ai", tags=["ai"])


@router.get("/items", response_model=list[ItemRead])
def items_list():
    return list_items()


@router.post("/items", response_model=ItemRead, status_code=201)
def items_create(payload: ItemCreate):
    return create_item(payload)


@router.get("/items/{item_id}", response_model=ItemRead)
def items_get(item_id: int):
    item = get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
