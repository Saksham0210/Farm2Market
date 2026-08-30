from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..utils.security import get_current_user, require_role

router = APIRouter(prefix="/produce", tags=["produce"])


def _farmer_profile(db: Session, user: models.User) -> models.FarmerProfile:
    profile = db.query(models.FarmerProfile).filter(models.FarmerProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Farmer profile not found for this account")
    return profile


@router.post("", response_model=schemas.ProduceOut, status_code=201)
def add_produce(
    payload: schemas.ProduceCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.UserRole.farmer)),
):
    """ADD PRODUCE DETAILS -> LIST PRODUCE ON PLATFORM."""
    farmer = _farmer_profile(db, user)
    produce = models.Produce(
        farmer_id=farmer.id,
        product_name=payload.product_name,
        quantity_available=payload.quantity_available,
        unit=payload.unit,
        quality_grade=payload.quality_grade,
        price_per_unit=payload.price_per_unit,
        available_date=payload.available_date or datetime.utcnow(),
        pickup_location=payload.pickup_location,
        latitude=payload.latitude if payload.latitude is not None else farmer.latitude,
        longitude=payload.longitude if payload.longitude is not None else farmer.longitude,
        status=models.ProduceStatus.available,
    )
    db.add(produce)
    db.commit()
    db.refresh(produce)
    return produce


@router.get("", response_model=List[schemas.ProduceOut])
def browse_marketplace(
    product_name: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """BUYER MARKETPLACE: Browse Products / Search / Compare Suppliers."""
    query = db.query(models.Produce).filter(models.Produce.status == models.ProduceStatus.available)
    if product_name:
        query = query.filter(models.Produce.product_name.ilike(f"%{product_name}%"))
    return query.order_by(models.Produce.created_at.desc()).all()


@router.get("/mine", response_model=List[schemas.ProduceOut])
def my_produce(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.UserRole.farmer)),
):
    farmer = _farmer_profile(db, user)
    return db.query(models.Produce).filter(models.Produce.farmer_id == farmer.id).order_by(
        models.Produce.created_at.desc()
    ).all()


@router.get("/{produce_id}", response_model=schemas.ProduceOut)
def get_produce(produce_id: str, db: Session = Depends(get_db)):
    produce = db.query(models.Produce).filter(models.Produce.id == produce_id).first()
    if not produce:
        raise HTTPException(status_code=404, detail="Produce not found")
    return produce
