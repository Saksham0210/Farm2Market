from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from .. import models
from ..utils.geo import estimate_distance_km
from ..utils.otp import generate_otp


COLD_CHAIN_KEYWORDS = {
    "milk",
    "paneer",
    "curd",
    "yogurt",
    "meat",
    "fish",
    "chicken",
    "egg",
    "cream",
}


def _requires_cold_chain(order: models.Order) -> bool:
    for item in order.items:
        name = (item.produce.product_name or "").lower()

        if any(kw in name for kw in COLD_CHAIN_KEYWORDS):
            return True

    return False


def _find_best_partner(
    db: Session,
    weight_kg: float,
    distance_km: float,
    need_cold_chain: bool,
) -> Optional[models.LogisticsPartner]:

    query = db.query(models.LogisticsPartner).filter(
        models.LogisticsPartner.is_available == True,  # noqa: E712
        models.LogisticsPartner.capacity_kg >= weight_kg,
    )

    if need_cold_chain:
        query = query.filter(
            models.LogisticsPartner.supports_cold_chain == True  # noqa: E712
        )

    candidates = query.all()

    if not candidates:
        # Fallback for demo/small operations
        candidates = (
            db.query(models.LogisticsPartner)
            .filter(models.LogisticsPartner.is_available == True)  # noqa: E712
            .all()
        )

    if not candidates:
        return None

    def total_cost(partner: models.LogisticsPartner) -> float:
        return partner.base_cost + partner.cost_per_km * distance_km

    # Cheapest route first, then higher-rated partner
    candidates.sort(
        key=lambda p: (
            total_cost(p),
            -p.rating,
        )
    )

    return candidates[0]


def _order_weight(order: models.Order) -> float:
    return sum(item.quantity for item in order.items)


def _order_pickup_points(
    order: models.Order,
) -> List[Tuple[str, Optional[float], Optional[float]]]:
    """
    Return all farmer pickup points involved in this order.

    An order can contain products from multiple farmers.
    """

    points = []

    seen = set()

    for item in order.items:
        produce = item.produce

        if not produce or not produce.farmer:
            continue

        farmer = produce.farmer

        key = (
            farmer.id,
            farmer.pickup_location,
        )

        if key in seen:
            continue

        seen.add(key)

        points.append(
            (
                farmer.pickup_location,
                farmer.latitude,
                farmer.longitude,
            )
        )

    return points


def _distance_between_points(
    point_a: Tuple[str, Optional[float], Optional[float]],
    point_b: Tuple[str, Optional[float], Optional[float]],
) -> float:

    label_a, lat_a, lon_a = point_a
    label_b, lat_b, lon_b = point_b

    return estimate_distance_km(
        lat_a,
        lon_a,
        lat_b,
        lon_b,
        label_a,
        label_b,
    )


def _optimize_batch_route(
    orders: List[models.Order],
) -> Tuple[List[str], float]:
    """
    SIMPLE MVP ROUTE OPTIMIZATION

    1. Collect all unique farmer pickup points.
    2. Start from the first pickup point.
    3. Visit the nearest unvisited pickup point.
    4. After all pickups are collected, visit buyer delivery locations
       using nearest-neighbour ordering.
    5. Return route labels + total route distance.

    This is a heuristic, not a full commercial routing engine.
    """

    pickup_points = []

    seen_pickups = set()

    for order in orders:
        for point in _order_pickup_points(order):
            key = (
                point[0],
                point[1],
                point[2],
            )

            if key not in seen_pickups:
                seen_pickups.add(key)
                pickup_points.append(point)

    if not pickup_points:
        pickup_points = [
            ("Depot", None, None)
        ]

    delivery_points = []

    for order in orders:
        delivery_points.append(
            (
                order.delivery_location,
                order.latitude,
                order.longitude,
                order.id,
            )
        )

    route_labels = []
    total_distance = 0.0

    # ---------------------------------------------------------
    # PART 1: OPTIMIZE FARMER PICKUPS
    # ---------------------------------------------------------

    current_pickup = pickup_points[0]

    route_labels.append(current_pickup[0])

    remaining_pickups = pickup_points[1:]

    while remaining_pickups:

        nearest = min(
            remaining_pickups,
            key=lambda point: _distance_between_points(
                current_pickup,
                point,
            ),
        )

        distance = _distance_between_points(
            current_pickup,
            nearest,
        )

        total_distance += distance

        current_pickup = nearest
        route_labels.append(nearest[0])

        remaining_pickups.remove(nearest)

    # ---------------------------------------------------------
    # PART 2: OPTIMIZE BUYER DELIVERIES
    # ---------------------------------------------------------

    if pickup_points:
        last_pickup = current_pickup

        current_location = (
            last_pickup[0],
            last_pickup[1],
            last_pickup[2],
        )
    else:
        current_location = (
            "Depot",
            None,
            None,
        )

    remaining_deliveries = delivery_points.copy()

    while remaining_deliveries:

        nearest_delivery = min(
            remaining_deliveries,
            key=lambda delivery: estimate_distance_km(
                current_location[1],
                current_location[2],
                delivery[1],
                delivery[2],
                current_location[0],
                delivery[0],
            ),
        )

        distance = estimate_distance_km(
            current_location[1],
            current_location[2],
            nearest_delivery[1],
            nearest_delivery[2],
            current_location[0],
            nearest_delivery[0],
        )

        total_distance += distance

        route_labels.append(nearest_delivery[0])

        current_location = (
            nearest_delivery[0],
            nearest_delivery[1],
            nearest_delivery[2],
        )

        remaining_deliveries.remove(nearest_delivery)

    return route_labels, round(total_distance, 2)


# ----------------------------------------------------------------
# DIRECT DELIVERY
# ----------------------------------------------------------------

def assign_logistics_for_order(
    db: Session,
    order: models.Order,
    weight_kg: float,
) -> Optional[models.Delivery]:

    """
    DIRECT DELIVERY

    Used for:
    - bulk orders
    - orders that choose direct delivery
    """

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

    partner = _find_best_partner(
        db,
        weight_kg,
        distance,
        need_cold_chain,
    )

    existing = (
        db.query(models.Delivery)
        .filter(models.Delivery.order_id == order.id)
        .first()
    )

    if existing:
        db.delete(existing)
        db.flush()

    delivery_cost = None
    partner_id = None

    if partner:
        delivery_cost = round(
            partner.base_cost
            + partner.cost_per_km * distance,
            2,
        )

        partner_id = partner.id

    pickup_label = (
        farmer.pickup_location
        if farmer
        else "Depot"
    )

    delivery = models.Delivery(
        order_id=order.id,
        logistics_partner_id=partner_id,
        distance_km=distance,
        delivery_cost=delivery_cost,
        otp=generate_otp(),
        status=(
            models.DeliveryStatus.assigned
            if partner
            else models.DeliveryStatus.pending
        ),
        route_sequence=(
            f"{pickup_label} -> "
            f"{order.delivery_location}"
        ),
    )

    db.add(delivery)

    order.status = (
        models.OrderStatus.out_for_delivery
        if partner
        else models.OrderStatus.matched
    )

    db.flush()

    return delivery


# ----------------------------------------------------------------
# BATCH DELIVERY
# ----------------------------------------------------------------

def assign_logistics_for_batch(
    db: Session,
    batch: models.DeliveryBatch,
) -> None:

    """
    BATCH DELIVERY

    One vehicle handles:

        Farmer pickup 1
              ↓
        Farmer pickup 2
              ↓
        Farmer pickup 3
              ↓
        Buyer delivery 1
              ↓
        Buyer delivery 2
              ↓
        Buyer delivery 3

    The route is optimized using a simple nearest-neighbour
    heuristic.

    The total vehicle cost is calculated from the complete route
    and then shared between orders according to their weight.
    """

    orders: List[models.Order] = (
        db.query(models.Order)
        .filter(models.Order.batch_id == batch.id)
        .all()
    )

    if not orders:
        return

    # ---------------------------------------------------------
    # CALCULATE OPTIMIZED ROUTE
    # ---------------------------------------------------------

    route_labels, total_distance = _optimize_batch_route(
        orders
    )

    # ---------------------------------------------------------
    # COLD CHAIN REQUIREMENT
    # ---------------------------------------------------------

    need_cold_chain = any(
        _requires_cold_chain(order)
        for order in orders
    )

    # ---------------------------------------------------------
    # FIND BEST VEHICLE
    # ---------------------------------------------------------

    partner = _find_best_partner(
        db,
        batch.total_weight_kg,
        total_distance,
        need_cold_chain,
    )

    if not partner:
        # Keep batch open for another attempt
        return

    # ---------------------------------------------------------
    # DISPATCH BATCH
    # ---------------------------------------------------------

    batch.logistics_partner_id = partner.id
    batch.status = "dispatched"

    # ---------------------------------------------------------
    # CALCULATE TOTAL COST
    # ---------------------------------------------------------

    total_cost = round(
        partner.base_cost
        + partner.cost_per_km * total_distance,
        2,
    )

    total_weight = sum(
        _order_weight(order)
        for order in orders
    )

    if total_weight <= 0:
        total_weight = 1

    route_sequence = " -> ".join(route_labels)

    # ---------------------------------------------------------
    # CREATE DELIVERY FOR EACH BUYER
    # ---------------------------------------------------------

    for order in orders:

        order_weight = _order_weight(order)

        # Share total vehicle cost according to order weight
        share_cost = round(
            total_cost
            * (order_weight / total_weight),
            2,
        )

        existing = (
            db.query(models.Delivery)
            .filter(
                models.Delivery.order_id == order.id
            )
            .first()
        )

        if existing:
            db.delete(existing)
            db.flush()

        delivery = models.Delivery(
            order_id=order.id,
            logistics_partner_id=partner.id,

            # Store the customer's approximate route share
            # of the overall optimized route.
            distance_km=round(
                total_distance
                * (order_weight / total_weight),
                2,
            ),

            delivery_cost=share_cost,

            otp=generate_otp(),

            status=models.DeliveryStatus.assigned,

            route_sequence=route_sequence,
        )

        db.add(delivery)

        order.status = models.OrderStatus.out_for_delivery

    db.flush()