"""
Seed development/test data.

Run from the backend folder:

    python seed.py

Creates:
- 3 test users
- Farmer profile
- Buyer profile
- Logistics partner
"""

from app.database import SessionLocal, engine, Base
from app import models
from app.utils.security import hash_password


# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

db = SessionLocal()


# ---------- TEST USERS ----------

test_users = [
    {
        "name": "Test Farmer",
        "email": "farmer@test.com",
        "password": "Test123!",
        "role": models.UserRole.farmer,
    },
    {
        "name": "Test Buyer",
        "email": "buyer@test.com",
        "password": "Test123!",
        "role": models.UserRole.buyer,
    },
    {
        "name": "Test Logistics",
        "email": "logistics@test.com",
        "password": "Test123!",
        "role": models.UserRole.logistics,
    },
]


for data in test_users:

    # Don't create the user if it already exists
    user = (
        db.query(models.User)
        .filter(models.User.email == data["email"])
        .first()
    )

    if user:
        print(f"Already exists: {data['email']}")
        continue

    user = models.User(
        name=data["name"],
        email=data["email"],
        hashed_password=hash_password(data["password"]),
        role=data["role"],
    )

    db.add(user)
    db.flush()

    # Farmer profile
    if data["role"] == models.UserRole.farmer:
        profile = models.FarmerProfile(
            user_id=user.id,
            farm_or_fpo_name="Test Farm",
            pickup_location="Delhi",
        )
        db.add(profile)

    # Buyer profile
    elif data["role"] == models.UserRole.buyer:
        profile = models.BuyerProfile(
            user_id=user.id,
            buyer_type=models.BuyerType.individual,
            default_location="Delhi",
        )
        db.add(profile)

    print(f"Created: {data['email']}")


# ---------- LOGISTICS PARTNERS ----------

partners = [
    dict(
        name="GreenLine Trucking",
        vehicle_type=models.VehicleType.truck,
        capacity_kg=2000,
        cost_per_km=18,
        base_cost=150,
        supports_cold_chain=True,
        current_location="City Depot North",
    ),
    dict(
        name="QuickHaul Mini Trucks",
        vehicle_type=models.VehicleType.mini_truck,
        capacity_kg=750,
        cost_per_km=12,
        base_cost=80,
        supports_cold_chain=False,
        current_location="City Depot East",
    ),
    dict(
        name="LocalHop Delivery Van",
        vehicle_type=models.VehicleType.van,
        capacity_kg=300,
        cost_per_km=9,
        base_cost=40,
        supports_cold_chain=True,
        current_location="City Depot South",
    ),
    dict(
        name="NeighbourGo Bikes",
        vehicle_type=models.VehicleType.bike,
        capacity_kg=25,
        cost_per_km=6,
        base_cost=15,
        supports_cold_chain=False,
        current_location="City Depot West",
    ),
]


for p in partners:

    exists = (
        db.query(models.LogisticsPartner)
        .filter(models.LogisticsPartner.name == p["name"])
        .first()
    )

    if not exists:
        db.add(models.LogisticsPartner(**p))


db.commit()
db.close()

print("\nSeed completed successfully!")
print("Test accounts:")
print("Farmer:    farmer@test.com / Test123!")
print("Buyer:     buyer@test.com / Test123!")
print("Logistics: logistics@test.com / Test123!")