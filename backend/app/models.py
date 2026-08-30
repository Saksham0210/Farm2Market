import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey,
    Enum as SAEnum, Text
)
from sqlalchemy.orm import relationship

from .database import Base


def gen_uuid():
    return str(uuid.uuid4())


# ---------- Enums ----------

class UserRole(str, enum.Enum):
    farmer = "farmer"
    buyer = "buyer"
    logistics = "logistics"
    admin = "admin"


class BuyerType(str, enum.Enum):
    individual = "individual"
    bulk = "bulk"


class ProduceStatus(str, enum.Enum):
    available = "available"
    reserved = "reserved"
    sold_out = "sold_out"


class OrderType(str, enum.Enum):
    individual = "individual"
    bulk = "bulk"


class OrderStatus(str, enum.Enum):
    placed = "placed"
    matched = "matched"
    batched = "batched"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    paid = "paid"
    cancelled = "cancelled"


class VehicleType(str, enum.Enum):
    truck = "truck"
    mini_truck = "mini_truck"
    van = "van"
    bike = "bike"


class DeliveryStatus(str, enum.Enum):
    pending = "pending"
    assigned = "assigned"
    picked_up = "picked_up"
    in_transit = "in_transit"
    delivered = "delivered"


# ---------- Core ----------

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(SAEnum(UserRole), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    farmer_profile = relationship("FarmerProfile", back_populates="user", uselist=False)
    buyer_profile = relationship("BuyerProfile", back_populates="user", uselist=False)


class FarmerProfile(Base):
    __tablename__ = "farmer_profiles"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    farm_or_fpo_name = Column(String, nullable=False)
    pickup_location = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    user = relationship("User", back_populates="farmer_profile")
    produce_items = relationship("Produce", back_populates="farmer")


class BuyerProfile(Base):
    __tablename__ = "buyer_profiles"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    buyer_type = Column(SAEnum(BuyerType), nullable=False)
    business_name = Column(String, nullable=True)
    default_location = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    user = relationship("User", back_populates="buyer_profile")


class Produce(Base):
    __tablename__ = "produce"

    id = Column(String, primary_key=True, default=gen_uuid)
    farmer_id = Column(String, ForeignKey("farmer_profiles.id"), nullable=False)
    product_name = Column(String, nullable=False)
    quantity_available = Column(Float, nullable=False)
    unit = Column(String, default="kg")
    quality_grade = Column(String, default="A")
    price_per_unit = Column(Float, nullable=False)
    available_date = Column(DateTime, default=datetime.utcnow)
    pickup_location = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    status = Column(SAEnum(ProduceStatus), default=ProduceStatus.available)
    created_at = Column(DateTime, default=datetime.utcnow)

    farmer = relationship("FarmerProfile", back_populates="produce_items")
    order_items = relationship("OrderItem", back_populates="produce")


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=gen_uuid)
    buyer_id = Column(String, ForeignKey("buyer_profiles.id"), nullable=False)
    order_type = Column(SAEnum(OrderType), nullable=False)
    delivery_location = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    delivery_slot = Column(String, nullable=False)  # e.g. "2026-09-01|morning"
    status = Column(SAEnum(OrderStatus), default=OrderStatus.placed)
    total_amount = Column(Float, default=0.0)
    batch_id = Column(String, ForeignKey("delivery_batches.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    buyer = relationship("BuyerProfile")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    batch = relationship("DeliveryBatch", back_populates="orders")
    delivery = relationship("Delivery", back_populates="order", uselist=False)
    payment = relationship("Payment", back_populates="order", uselist=False)


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(String, primary_key=True, default=gen_uuid)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    produce_id = Column(String, ForeignKey("produce.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    produce = relationship("Produce", back_populates="order_items")


class DeliveryBatch(Base):
    __tablename__ = "delivery_batches"

    id = Column(String, primary_key=True, default=gen_uuid)
    area_key = Column(String, nullable=False)       # normalized location key
    delivery_slot = Column(String, nullable=False)
    status = Column(String, default="open")          # open | full | dispatched
    total_weight_kg = Column(Float, default=0.0)
    logistics_partner_id = Column(String, ForeignKey("logistics_partners.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="batch")
    logistics_partner = relationship("LogisticsPartner")


class LogisticsPartner(Base):
    __tablename__ = "logistics_partners"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    vehicle_type = Column(SAEnum(VehicleType), nullable=False)
    capacity_kg = Column(Float, nullable=False)
    cost_per_km = Column(Float, nullable=False)
    base_cost = Column(Float, default=0.0)
    is_available = Column(Boolean, default=True)
    supports_cold_chain = Column(Boolean, default=False)
    current_location = Column(String, nullable=True)
    rating = Column(Float, default=4.5)


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(String, primary_key=True, default=gen_uuid)
    order_id = Column(String, ForeignKey("orders.id"), unique=True, nullable=False)
    logistics_partner_id = Column(String, ForeignKey("logistics_partners.id"), nullable=True)
    distance_km = Column(Float, nullable=True)
    delivery_cost = Column(Float, nullable=True)
    otp = Column(String, nullable=True)
    status = Column(SAEnum(DeliveryStatus), default=DeliveryStatus.pending)
    route_sequence = Column(Text, nullable=True)  # comma separated stop names/order ids
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="delivery")
    logistics_partner = relationship("LogisticsPartner")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=gen_uuid)
    order_id = Column(String, ForeignKey("orders.id"), unique=True, nullable=False)
    total_amount = Column(Float, nullable=False)
    platform_fee = Column(Float, nullable=False)
    logistics_share = Column(Float, nullable=False)
    farmer_share = Column(Float, nullable=False)
    status = Column(String, default="pending")  # pending | settled
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="payment")
