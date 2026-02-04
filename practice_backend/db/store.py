from schemas.items import ItemCreate, ItemRead

_ITEMS: list[ItemRead] = []
_NEXT_ID = 1


def list_items() -> list[ItemRead]:
    return _ITEMS


def create_item(payload: ItemCreate) -> ItemRead:
    global _NEXT_ID
    item = ItemRead(id=_NEXT_ID, **payload.dict())
    _ITEMS.append(item)
    _NEXT_ID += 1
    return item


def get_item(item_id: int) -> ItemRead | None:
    for item in _ITEMS:
        if item.id == item_id:
            return item
    return None
