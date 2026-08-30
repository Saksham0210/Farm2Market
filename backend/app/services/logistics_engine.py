from typing import List, Optional

from sqlalchemy.orm import Session

from .. import models
from ..utils.geo import estimate_distance_km
from ..utils.otp import generate_otp

COLD_CHAIN_KEYWORDS = {"milk", "paneer", "curd", "yogurt", "meat", "fish", "chicken", "egg", "cream"}


def _requires_cold_chain(order: models.Order) -> bool:
    for item in order.items:
        name = (item.produce.product_name or "").lower()
        if any(kw in name for kw in COLD_CHAIN_KEYWORDS):
            return True
    return False


def _find_best_partner(
    db: Session, weight_kg: float, distance_km: float, need_cold_chain: bool
) -> Optional[models.LogisticsPartner]:
    """SMART LOGISTICS SELECTION: compare cost, vehicle capacity, distance,
    availability, delivery time -> SELECT BEST / CHEAPEST OPTION."""
    query = db.query(models.LogisticsPartner).filter(
        models.LogisticsPartner.is_available == True,  # noqa: E712
        models.LogisticsPartner.capacity_kg >= weight_kg,
    )
    if need_cold_chain:
        query = query.filter(models.LogisticsPartner.supports_cold_chain == True)  # noqa: E712

    candidates = query.all()
    if not candidates:
        # relax the capacity constraint as a fallback so small ops still work
        candidates = db.query(models.LogisticsPartner).filter(
            models.LogisticsPartner.is_available == True  # noqa: E712
        ).all()
    if not candidates:
        return None

    def total_cost(p: models.LogisticsPartner) -> float:
        return p.base_cost + p.cost_per_km * distance_km

    # cheapest first, tie-broken by higher rating
    candidates.sort(key=lambda p: (total_cost(p), -p.rating))
    return candidates[0]


def assign_logistics_for_order(db: Session, order: models.Order, weight_kg: float) -> Optional[models.Delivery]:
    """Direct order processing path (bulk orders, or an individual order that
    opted out of batching): CALCULATE DELIVERY REQUIREMENT -> FIND LOGISTICS
    PARTNERS -> SMART LOGISTICS SELECTION -> SELECT BEST/CHEAPEST OPTION ->
    OPTIMIZE PICKUP + DELIVERY ROUTE."""
    anchor_produce = order.items[0].produce if order.items else None
    farmer = anchor_produce.farmer if anchor_produce else None

    distance = estimate_distance_km(
        farmer.latitude if farmer else None,
        farmer.longitude if farmer else None,
        order.latitude,
        order.longitude,
        farmer.pickup_location if farmer else "depot",
        order.delivery_location,
    )
    need_cold_chain = _requires_cold_chain(order)
    partner = _find_best_partner(db, weight_kg, distance, need_cold_chain)

    existing = db.query(models.Delivery).filter(models.Delivery.order_id == order.id).first()
    if existing:
        db.delete(existing)
        db.flush()

    delivery_cost = None
    partner_id = None
    if partner:
        delivery_cost = round(partner.base_cost + partner.cost_per_km * distance, 2)
        partner_id = partner.id

    pickup_label = farmer.pickup_location if farmer else "Depot"
    delivery = models.Delivery(
        order_id=order.id,
        logistics_partner_id=partner_id,
        distance_km=distance,
        delivery_cost=delivery_cost,
        otp=generate_otp(),
        status=models.DeliveryStatus.assigned if partner else models.DeliveryStatus.pending,
        route_sequence=f"{pickup_label} -> {order.delivery_location}",
    )
    db.add(delivery)
    order.status = models.OrderStatus.out_for_delivery if partner else models.OrderStatus.matched
    db.flush()
    return delivery


def assign_logistics_for_batch(db: Session, batch: models.DeliveryBatch) -> None:
    """Batched individual orders: one logistics partner serves multiple
    nearby stops -> OPTIMIZED DELIVERY ROUTE: Customer A -> B -> C -> D."""
    orders: List[models.Order] = (
        db.query(models.Order).filter(models.Order.batch_id == batch.id).all()
    )
    if not orders:
        return

    anchor_produce = orders[0].items[0].produce if orders[0].items else None
    farmer = anchor_produce.farmer if anchor_produce else None
    pickup_label = farmer.pickup_location if farmer else "Depot"

    stop_distances = []
    for o in orders:
        d = estimate_distance_km(
            farmer.latitude if farmer else None,
            farmer.longitude if farmer else None,
            o.latitude,
            o.longitude,
            pickup_label,
            o.delivery_location,
        )
        stop_distances.append((o, d))

    total_distance = sum(d for _, d in stop_distances)
    need_cold_chain = any(_requires_cold_chain(o) for o in orders)
    partner = _find_best_partner(db, batch.total_weight_kg, total_distance, need_cold_chain)

    if not partner:
        # Not enough logistics capacity right now; batch stays open for retry
        return

    batch.logistics_partner_id = partner.id
    batch.status = "dispatched"

    # Nearest-neighbour style route optimization (simple ascending-distance order)
    stop_distances.sort(key=lambda x: x[1])
    route_sequence = " -> ".join(
        [pickup_label] + [f"{o.delivery_location}" for o, _ in stop_distances]
    )

    total_cost = round(partner.base_cost + partner.cost_per_km * total_distance, 2)
    total_weight = sum(sum(i.quantity for i in o.items) for o in orders) or 1

    for o, d in stop_distances:
        order_weight = sum(i.quantity for i in o.items)
        share_cost = round(total_cost * (order_weight / total_weight), 2)

        existing = db.query(models.Delivery).filter(models.Delivery.order_id == o.id).first()
        if existing:
            db.delete(existing)
            db.flush()

        delivery = models.Delivery(
            order_id=o.id,
            logistics_partner_id=partner.id,
            distance_km=d,
            delivery_cost=share_cost,
            otp=generate_otp(),
            status=models.DeliveryStatus.assigned,
            route_sequence=route_sequence,
        )
        db.add(delivery)
        o.status = models.OrderStatus.out_for_delivery

    db.flush()
