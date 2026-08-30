from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..utils.security import get_current_user, require_role
from ..services.payment_engine import confirm_delivery

router = APIRouter(tags=["logistics"])


@router.post("/logistics-partners", response_model=schemas.LogisticsPartnerOut, status_code=201)
def register_partner(
    payload: schemas.LogisticsPartnerCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.UserRole.admin, models.UserRole.logistics)),
):
    """FIND LOGISTICS PARTNERS pool: Truck / Mini Truck / Van / Local Delivery Partner."""
    partner = models.LogisticsPartner(**payload.model_dump())
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner


@router.get("/logistics-partners", response_model=List[schemas.LogisticsPartnerOut])
def list_partners(db: Session = Depends(get_db)):
    return db.query(models.LogisticsPartner).all()


@router.get("/orders/{order_id}/delivery", response_model=schemas.DeliveryOut)
def get_delivery(order_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    delivery = db.query(models.Delivery).filter(models.Delivery.order_id == order_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="No delivery record yet for this order")
    return delivery


@router.post("/orders/{order_id}/confirm-delivery", response_model=schemas.DeliveryOut)
def confirm_delivery_endpoint(
    order_id: str,
    payload: schemas.DeliveryConfirm,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """DELIVERY CONFIRMATION (OTP / Digital Proof) -> triggers PAYMENT SETTLEMENT."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return confirm_delivery(db, order, payload.otp)
