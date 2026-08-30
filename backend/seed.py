"""
Run once after the tables are created to seed a few logistics partners so
orders have something to be matched against.

    cd backend
    python seed.py
"""
from app.database import SessionLocal, engine, Base
from app import models

Base.metadata.create_all(bind=engine)

db = SessionLocal()

partners = [
    dict(name="GreenLine Trucking", vehicle_type=models.VehicleType.truck,
         capacity_kg=2000, cost_per_km=18, base_cost=150, supports_cold_chain=True,
         current_location="City Depot North"),
    dict(name="QuickHaul Mini Trucks", vehicle_type=models.VehicleType.mini_truck,
         capacity_kg=750, cost_per_km=12, base_cost=80, supports_cold_chain=False,
         current_location="City Depot East"),
    dict(name="LocalHop Delivery Van", vehicle_type=models.VehicleType.van,
         capacity_kg=300, cost_per_km=9, base_cost=40, supports_cold_chain=True,
         current_location="City Depot South"),
    dict(name="NeighbourGo Bikes", vehicle_type=models.VehicleType.bike,
         capacity_kg=25, cost_per_km=6, base_cost=15, supports_cold_chain=False,
         current_location="City Depot West"),
]

for p in partners:
    exists = db.query(models.LogisticsPartner).filter(models.LogisticsPartner.name == p["name"]).first()
    if not exists:
        db.add(models.LogisticsPartner(**p))

db.commit()
db.close()
print("Seeded logistics partners.")
