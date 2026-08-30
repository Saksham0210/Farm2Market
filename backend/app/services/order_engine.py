from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..utils.geo import area_key
from .logistics_engine import assign_logistics_for_order
from .batch_engine import try_batch_individual_order


def create_order(db: Session, buyer: models.BuyerProfile, payload: schemas.OrderCreate) -> models.Order:
    """
    Implements: SAVE ORDER -> SMART ORDER ENGINE
      - Match farmer/FPO inventory
      - Check quantity availability
      - Check buyer location / delivery time (recorded on the order)
      - Calculate total demand (total_amount)
    Then branches BULK vs INDIVIDUAL.
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    order = models.Order(
        buyer_id=buyer.id,
        order_type=payload.order_type,
        delivery_location=payload.delivery_location,
        latitude=payload.latitude,
        longitude=payload.longitude,
        delivery_slot=payload.delivery_slot,
        status=models.OrderStatus.placed,
    )
    db.add(order)
    db.flush()  # get order.id before adding items

    total_amount = 0.0
    total_weight = 0.0
    order_items: List[models.OrderItem] = []

    for item in payload.items:
        produce = db.query(models.Produce).filter(models.Produce.id == item.produce_id).first()
        if not produce:
            raise HTTPException(status_code=404, detail=f"Produce {item.produce_id} not found")
        if produce.status == models.ProduceStatus.sold_out:
            raise HTTPException(status_code=400, detail=f"{produce.product_name} is sold out")
        if item.quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be greater than zero")
        if produce.quantity_available < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Only {produce.quantity_available}{produce.unit} of {produce.product_name} available",
            )

        subtotal = round(item.quantity * produce.price_per_unit, 2)
        order_item = models.OrderItem(
            order_id=order.id,
            produce_id=produce.id,
            quantity=item.quantity,
            unit_price=produce.price_per_unit,
            subtotal=subtotal,
        )
        db.add(order_item)
        order_items.append(order_item)

        # Deduct matched inventory immediately (reserve stock)
        produce.quantity_available -= item.quantity
        if produce.quantity_available <= 0:
            produce.status = models.ProduceStatus.sold_out

        total_amount += subtotal
        total_weight += item.quantity

    order.total_amount = round(total_amount, 2)
    order.status = models.OrderStatus.matched
    db.flush()

    # BULK OR INDIVIDUAL branch
    if payload.order_type == models.OrderType.bulk:
        # Direct order processing -> straight to logistics calculation
        assign_logistics_for_order(db, order, total_weight)
    else:
        # Find nearby orders (same area + time slot) for batching
        try_batch_individual_order(db, order, total_weight)

    db.commit()
    db.refresh(order)
    return order
