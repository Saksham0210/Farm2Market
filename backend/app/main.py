from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .database import engine
from .routers import auth, produce, orders, logistics, payments

# Creates all tables in PostgreSQL if they don't already exist.
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Farm2Market API",
    description="Farmer/FPO -> Marketplace -> Smart Order Engine -> Logistics -> Delivery -> Payment Settlement",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your frontend's real origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(produce.router)
app.include_router(orders.router)
app.include_router(logistics.router)
app.include_router(payments.router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "Farm2Market API"}
