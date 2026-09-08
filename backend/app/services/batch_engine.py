from sqlalchemy.orm import Session

from .. import models
from ..utils.geo import area_key, estimate_distance_km
from .logistics_engine import assign_logistics_for_batch


# ---------- MVP BATCHING RULES ----------

MIN_BATCH_WEIGHT_KG = 25.0

# Maximum distance allowed between farmer pickup points
# for them to be considered part of the same vehicle route.
MAX_PICKUP_DISTANCE_KM = 50.0


def _order_weight(order: models.Order) -> float:
    """Return total quantity/weight of an order."""
    return sum(item.quantity for item in order.items)


def _order_farmers(order: models.Order):
    """Return the farmers supplying this order."""
    farmers = []

    for item in order.items:
        if item.produce and item.produce.farmer:
            farmer = item.produce.farmer

            if farmer.id not in [f.id for f in farmers]:
                farmers.append(farmer)

    return farmers


def _farmers_compatible(
    batch_orders,
    new_order: models.Order,
) -> bool:
    """
    Check whether the farmer pickup locations are geographically
    compatible enough to use one vehicle.

    For the MVP we compare pickup points against each other.
    """

    existing_farmers = []

    for order in batch_orders:
        for farmer in _order_farmers(order):
            if farmer.id not in [f.id for f in existing_farmers]:
                existing_farmers.append(farmer)

    new_farmers = _order_farmers(new_order)

    # If we don't have farmer coordinates, allow the batch.
    # The existing geo.py fallback will handle distance calculations.
    all_farmers = existing_farmers + [
        f for f in new_farmers
        if f.id not in [x.id for x in existing_farmers]
    ]

    for i in range(len(all_farmers)):
        for j in range(i + 1, len(all_farmers)):

            f1 = all_farmers[i]
            f2 = all_farmers[j]

            distance = estimate_distance_km(
                f1.latitude,
                f1.longitude,
                f2.latitude,
                f2.longitude,
                f1.pickup_location,
                f2.pickup_location,
            )

            if distance > MAX_PICKUP_DISTANCE_KM:
                return False

    return True


def _vehicle_can_handle_batch(
    db: Session,
    total_weight_kg: float,
) -> bool:
    """Check whether at least one available vehicle can carry the batch."""

    partner = (
        db.query(models.LogisticsPartner)
        .filter(
            models.LogisticsPartner.is_available == True,  # noqa: E712
            models.LogisticsPartner.capacity_kg >= total_weight_kg,
        )
        .first()
    )

    return partner is not None


def try_batch_individual_order(
    db: Session,
    order: models.Order,
    order_weight_kg: float,
) -> models.DeliveryBatch:
    """
    MVP SMART BATCHING

    1. Same buyer delivery area
    2. Same delivery time slot
    3. Farmer pickup locations must be compatible
    4. Combined weight must reach 25 kg
    5. Combined weight must fit an available vehicle
    6. Products do NOT need to be the same

    If the conditions are not satisfied, the order remains
    in an open batch waiting for compatible orders.
    """

    key = area_key(order.delivery_location)

    # Find existing open batches in the same destination area
    # and same delivery slot.
    open_batches = (
        db.query(models.DeliveryBatch)
        .filter(
            models.DeliveryBatch.area_key == key,
            models.DeliveryBatch.delivery_slot == order.delivery_slot,
            models.DeliveryBatch.status == "open",
        )
        .all()
    )

    selected_batch = None

    for batch in open_batches:

        # Get current orders in this batch.
        batch_orders = (
            db.query(models.Order)
            .filter(models.Order.batch_id == batch.id)
            .all()
        )

        new_total_weight = batch.total_weight_kg + order_weight_kg

        # Vehicle capacity check
        if not _vehicle_can_handle_batch(db, new_total_weight):
            continue

        # Farmer pickup compatibility check
        if not _farmers_compatible(batch_orders, order):
            continue

        selected_batch = batch
        break

    # No compatible batch found → create a new open batch.
    if not selected_batch:
        selected_batch = models.DeliveryBatch(
            area_key=key,
            delivery_slot=order.delivery_slot,
            status="open",
            total_weight_kg=0.0,
        )

        db.add(selected_batch)
        db.flush()

    # Add order to batch.
    selected_batch.total_weight_kg += order_weight_kg
    order.batch_id = selected_batch.id
    order.status = models.OrderStatus.batched

    db.flush()

    # Check whether minimum batch weight has been reached.
    if selected_batch.total_weight_kg >= MIN_BATCH_WEIGHT_KG:

        # Let logistics engine assign the vehicle.
        assign_logistics_for_batch(db, selected_batch)

    return selected_batch


def request_direct_delivery(
    db: Session,
    order: models.Order,
    extra_cost_percent: float = 25.0,
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

            # Prevent negative weight.
            if batch.total_weight_kg < 0:
                batch.total_weight_kg = 0

    order.batch_id = None

    delivery = assign_logistics_for_order(
        db,
        order,
        sum(i.quantity for i in order.items),
    )

    if delivery and delivery.delivery_cost is not None:
        delivery.delivery_cost = round(
            delivery.delivery_cost
            * (1 + extra_cost_percent / 100),
            2,
        )

    db.commit()
    db.refresh(order)

    return order