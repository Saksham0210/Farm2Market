from sqlalchemy.orm import Session

from .. import models
from ..utils.geo import area_key
from .logistics_engine import assign_logistics_for_batch


# Thresholds that decide whether "enough orders / weight" exist for a batch
MIN_BATCH_WEIGHT_KG = 40.0
MIN_BATCH_ORDERS = 3


def try_batch_individual_order(
    db: Session,
    order: models.Order,
    order_weight_kg: float
) -> models.DeliveryBatch:

    """
    Find Nearby Orders (Same Area + Time Slot)
    -> Enough Orders / Weight for Delivery Batch?
         YES -> Create Batch and dispatch
         NO  -> leave batch open
    """

    key = area_key(order.delivery_location)

    batch = (
        db.query(models.DeliveryBatch)
        .filter(
            models.DeliveryBatch.area_key == key,
            models.DeliveryBatch.delivery_slot == order.delivery_slot,
            models.DeliveryBatch.status == "open",
        )
        .first()
    )

    if not batch:
        batch = models.DeliveryBatch(
            area_key=key,
            delivery_slot=order.delivery_slot,
            status="open",
            total_weight_kg=0.0,
        )

        db.add(batch)
        db.flush()

    batch.total_weight_kg += order_weight_kg
    order.batch_id = batch.id
    order.status = models.OrderStatus.batched

    db.flush()

    orders_in_batch = (
        db.query(models.Order)
        .filter(models.Order.batch_id == batch.id)
        .count()
    )

    if (
        batch.total_weight_kg >= MIN_BATCH_WEIGHT_KG
        or orders_in_batch >= MIN_BATCH_ORDERS
    ):
        assign_logistics_for_batch(db, batch)

    return batch


def request_direct_delivery(
    db: Session,
    order: models.Order,
    extra_cost_percent: float = 25.0
):
    """
    Customer chooses direct delivery instead of waiting for a batch.
    """

    from .logistics_engine import assign_logistics_for_order

    if order.batch_id:

        batch = (
            db.query(models.DeliveryBatch)
            .filter(
                models.DeliveryBatch.id == order.batch_id
            )
            .first()
        )

        if batch:
            batch.total_weight_kg -= sum(
                i.quantity for i in order.items
            )

    order.batch_id = None

    delivery = assign_logistics_for_order(
        db,
        order,
        sum(i.quantity for i in order.items)
    )

    if delivery and delivery.delivery_cost is not None:
        delivery.delivery_cost = round(
            delivery.delivery_cost
            * (1 + extra_cost_percent / 100),
            2
        )

    db.commit()
    db.refresh(order)

    return order