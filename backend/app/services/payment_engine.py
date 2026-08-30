from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..config import settings


def confirm_delivery(db: Session, order: models.Order, otp: str) -> models.Delivery:
    """DELIVERY CONFIRMATION (OTP / Digital Proof) -> triggers PAYMENT SETTLEMENT."""
    delivery = order.delivery
    if not delivery:
        raise HTTPException(status_code=404, detail="No delivery record for this order")
    if delivery.status == models.DeliveryStatus.delivered:
        raise HTTPException(status_code=400, detail="Delivery already confirmed")
    if delivery.otp != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    delivery.status = models.DeliveryStatus.delivered
    delivery.delivered_at = datetime.utcnow()
    order.status = models.OrderStatus.delivered
    db.flush()

    settle_payment(db, order)

    db.commit()
    db.refresh(delivery)
    return delivery


def settle_payment(db: Session, order: models.Order) -> models.Payment:
    """PAYMENT SETTLEMENT: split between Farmer/FPO and Logistics Partner,
    the platform's cut becomes PLATFORM REVENUE."""
    delivery = order.delivery
    logistics_cost = delivery.delivery_cost or 0.0 if delivery else 0.0

    platform_fee_from_produce = round(order.total_amount * settings.platform_fee_percent / 100, 2)
    logistics_markup = round(logistics_cost * settings.logistics_share_percent / 100, 2)

    farmer_share = round(order.total_amount - platform_fee_from_produce, 2)
    logistics_share = round(logistics_cost, 2)  # what the logistics partner actually receives
    platform_fee = round(platform_fee_from_produce + logistics_markup, 2)

    payment = db.query(models.Payment).filter(models.Payment.order_id == order.id).first()
    if not payment:
        payment = models.Payment(order_id=order.id)
        db.add(payment)

    payment.total_amount = order.total_amount
    payment.platform_fee = platform_fee
    payment.logistics_share = logistics_share
    payment.farmer_share = farmer_share
    payment.status = "settled"
    payment.settled_at = datetime.utcnow()

    order.status = models.OrderStatus.paid
    db.flush()
    return payment
