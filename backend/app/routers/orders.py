from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..utils.security import get_current_user, require_role
from ..services.order_engine import create_order
from ..services.batch_engine import request_direct_delivery

router = APIRouter(prefix="/orders", tags=["orders"])


def _buyer_profile(db: Session, user: models.User) -> models.BuyerProfile:
    profile = db.query(models.BuyerProfile).filter(models.BuyerProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Buyer profile not found for this account")
    return profile


@router.post("", response_model=schemas.OrderOut, status_code=201)
def place_order(
    payload: schemas.OrderCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.UserRole.buyer)),
):
    """PLACE ORDER -> SAVE ORDER IN DATABASE -> SMART ORDER ENGINE."""
    buyer = _buyer_profile(db, user)

    expected_type = models.OrderType.bulk if buyer.buyer_type == models.BuyerType.bulk else models.OrderType.individual
    if payload.order_type != expected_type:
        raise HTTPException(
            status_code=400,
            detail=f"Your account is a {buyer.buyer_type.value} buyer; order_type must be '{expected_type.value}'",
        )

    return create_order(db, buyer, payload)


@router.get("/mine", response_model=List[schemas.OrderOut])
def my_orders(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.UserRole.buyer)),
):
    buyer = _buyer_profile(db, user)
    return db.query(models.Order).filter(models.Order.buyer_id == buyer.id).order_by(
        models.Order.created_at.desc()
    ).all()

@router.get("/logistics", response_model=List[schemas.OrderOut])
def logistics_orders(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.UserRole.logistics)),
):
    """Return orders that have a logistics delivery assigned."""
    orders = (
        db.query(models.Order)
        .join(models.Delivery, models.Delivery.order_id == models.Order.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )
    return orders

@router.get("/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/{order_id}/request-direct-delivery", response_model=schemas.OrderOut)
def choose_direct_delivery(
    order_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.UserRole.buyer)),
):
    """Customer Options -> 'Direct Delivery, Pay Extra Cost' for an order
    still waiting on its batch to fill up."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != models.OrderStatus.batched:
        raise HTTPException(status_code=400, detail="Order is not currently waiting in a batch")

    return request_direct_delivery(db, order)
