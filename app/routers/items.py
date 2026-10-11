from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc
from sqlmodel import Session, func, select

from ..database import get_session
from ..models import Item, ItemDescription, User
from ..schemas import ItemCreate, ItemDescriptionCreate, ItemDescriptionRead, ItemRead, ItemUpdate, PaginatedItems
from ..security import get_current_user

router = APIRouter(prefix="/items", tags=["items"])


def owned_item(item_id: int, user: User, session: Session) -> Item:
    item = session.get(Item, item_id)
    if item is None or item.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="You do not own this item")
    return item


@router.post("/", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(request: ItemCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> Item:
    item = Item(owner_id=user.id, name=request.name, status=request.status)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/", response_model=PaginatedItems)
def read_items(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = None,
    item_status: str | None = Query(default=None, alias="status"),
    sort_by: str = Query(default="created_at", pattern="^(created_at|name|updated_at)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> PaginatedItems:
    query = select(Item).where(Item.deleted_at.is_(None))
    if user.role != "admin":
        query = query.where(Item.owner_id == user.id)
    if item_status:
        query = query.where(Item.status == item_status)
    if search:
        query = query.where(Item.name.contains(search))
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    sort_column = getattr(Item, sort_by)
    query = query.order_by((asc if sort_order == "asc" else desc)(sort_column))
    items = list(session.exec(query.offset(offset).limit(limit)))
    return PaginatedItems(items=items, limit=limit, offset=offset, total=total)


@router.get("/{item_id}", response_model=ItemRead)
def read_item(item_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> Item:
    return owned_item(item_id, user, session)


@router.patch("/{item_id}", response_model=ItemRead)
def update_item(item_id: int, request: ItemUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> Item:
    item = owned_item(item_id, user, session)
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    item.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> None:
    item = owned_item(item_id, user, session)
    item.deleted_at = datetime.now(timezone.utc)
    session.add(item)
    session.commit()


@router.post("/{item_id}/descriptions", response_model=ItemDescriptionRead, status_code=201)
def create_description(item_id: int, request: ItemDescriptionCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> ItemDescription:
    owned_item(item_id, user, session)
    description = ItemDescription(item_id=item_id, locale=request.locale, content=request.content)
    session.add(description)
    session.commit()
    session.refresh(description)
    return description


@router.get("/{item_id}/descriptions", response_model=list[ItemDescriptionRead])
def read_descriptions(item_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> list[ItemDescription]:
    owned_item(item_id, user, session)
    return list(session.exec(select(ItemDescription).where(ItemDescription.item_id == item_id)))


@router.delete("/{item_id}/descriptions/{description_id}", status_code=204)
def delete_description(item_id: int, description_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> None:
    owned_item(item_id, user, session)
    description = session.get(ItemDescription, description_id)
    if description is None or description.item_id != item_id:
        raise HTTPException(status_code=404, detail="Description not found")
    session.delete(description)
    session.commit()
