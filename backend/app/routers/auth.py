from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..utils.security import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(db: Session, user: models.User) -> schemas.UserOut:
    buyer_type = None
    if user.role == models.UserRole.buyer:
        profile = db.query(models.BuyerProfile).filter(models.BuyerProfile.user_id == user.id).first()
        if profile:
            buyer_type = profile.buyer_type
    return schemas.UserOut(id=user.id, name=user.name, email=user.email, role=user.role, buyer_type=buyer_type)


@router.post("/register", response_model=schemas.Token, status_code=201)
def register(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()

    if payload.role == models.UserRole.farmer:
        if not payload.farm_or_fpo_name or not payload.pickup_location:
            raise HTTPException(status_code=400, detail="Farmer registration requires farm_or_fpo_name and pickup_location")
        profile = models.FarmerProfile(
            user_id=user.id,
            farm_or_fpo_name=payload.farm_or_fpo_name,
            pickup_location=payload.pickup_location,
            latitude=payload.latitude,
            longitude=payload.longitude,
        )
        db.add(profile)

    elif payload.role == models.UserRole.buyer:
        if not payload.buyer_type:
            raise HTTPException(status_code=400, detail="Buyer registration requires buyer_type")
        profile = models.BuyerProfile(
            user_id=user.id,
            buyer_type=payload.buyer_type,
            business_name=payload.business_name,
            default_location=payload.default_location,
            latitude=payload.latitude,
            longitude=payload.longitude,
        )
        db.add(profile)

    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id, "role": user.role.value})
    return schemas.Token(access_token=token, user=_user_out(db, user))


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token({"sub": user.id, "role": user.role.value})
    return schemas.Token(access_token=token, user=_user_out(db, user))


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _user_out(db, current_user)
