from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field

from .models import UserRole, BuyerType, ProduceStatus, OrderType, OrderStatus, VehicleType, DeliveryStatus


# ---------- Auth / Users ----------

class UserRegister(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    password: str = Field(min_length=6)
    role: UserRole

    # farmer-specific
    farm_or_fpo_name: Optional[str] = None
    pickup_location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # buyer-specific
    buyer_type: Optional[BuyerType] = None
    business_name: Optional[str] = None
    default_location: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: UserRole
    buyer_type: Optional[BuyerType] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Produce ----------

class ProduceCreate(BaseModel):
    product_name: str
    quantity_available: float
    unit: str = "kg"
    quality_grade: str = "A"
    price_per_unit: float
    available_date: Optional[datetime] = None
    pickup_location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ProduceOut(BaseModel):
    id: str
    farmer_id: str
    product_name: str
    quantity_available: float
    unit: str
    quality_grade: str
    price_per_unit: float
    available_date: datetime
    pickup_location: str
    status: ProduceStatus

    class Config:
        from_attributes = True


# ---------- Orders ----------

class OrderItemCreate(BaseModel):
    produce_id: str
    quantity: float


class OrderCreate(BaseModel):
    order_type: OrderType
    delivery_location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    delivery_slot: str  # "YYYY-MM-DD|morning|afternoon|evening"
    items: List[OrderItemCreate]


class OrderItemOut(BaseModel):
    id: str
    produce_id: str
    quantity: float
    unit_price: float
    subtotal: float

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: str
    buyer_id: str
    order_type: OrderType
    delivery_location: str
    delivery_slot: str
    status: OrderStatus
    total_amount: float
    batch_id: Optional[str] = None
    items: List[OrderItemOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Logistics ----------

class LogisticsPartnerCreate(BaseModel):
    name: str
    vehicle_type: VehicleType
    capacity_kg: float
    cost_per_km: float
    base_cost: float = 0.0
    supports_cold_chain: bool = False
    current_location: Optional[str] = None


class LogisticsPartnerOut(BaseModel):
    id: str
    name: str
    vehicle_type: VehicleType
    capacity_kg: float
    cost_per_km: float
    is_available: bool
    rating: float

    class Config:
        from_attributes = True


class DeliveryOut(BaseModel):
    id: str
    order_id: str
    logistics_partner_id: Optional[str] = None
    distance_km: Optional[float] = None
    delivery_cost: Optional[float] = None
    status: DeliveryStatus
    otp: Optional[str] = None

    class Config:
        from_attributes = True


class DeliveryConfirm(BaseModel):
    otp: str


# ---------- Payments ----------

class PaymentOut(BaseModel):
    id: str
    order_id: str
    total_amount: float
    platform_fee: float
    logistics_share: float
    farmer_share: float
    status: str

    class Config:
        from_attributes = True
