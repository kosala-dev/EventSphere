from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, require_role
from models import UserInDB, UserModel, UserRole
from security import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY, create_access_token, hash_password, verify_password

router = APIRouter(prefix="", tags=["Authentication"])


class UserRegister(BaseModel):
    username: str
    email: str
    password: str


class ManagedAccountCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=12, max_length=72)
    role: Literal["admin", "staff"]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(user: UserRegister, db: Session = Depends(get_db)):
    existing_user = db.query(UserModel).filter(
        (UserModel.username == user.username) | (UserModel.email == user.email)
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already registered.")

    db_user = UserModel(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password),
        role=UserRole.attendee.value,
        is_active=True,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": "User registered successfully", "username": db_user.username, "role": db_user.role}


@router.post("/admin/users", status_code=status.HTTP_201_CREATED)
def create_managed_account(
    account: ManagedAccountCreate,
    db: Session = Depends(get_db),
    admin_user: UserInDB = Depends(require_role(UserRole.admin)),
):
    if len(account.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password must be no more than 72 UTF-8 bytes.")

    existing_user = db.query(UserModel).filter(
        (UserModel.username == account.username) | (UserModel.email == str(account.email))
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email is already registered.")

    db_user = UserModel(
        username=account.username,
        email=str(account.email),
        hashed_password=hash_password(account.password),
        role=account.role,
        is_active=True,
    )
    db.add(db_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username or email is already registered.") from None
    db.refresh(db_user)
    return {
        "message": f"{account.role.title()} account created.",
        "username": db_user.username,
        "email": db_user.email,
        "role": db_user.role,
    }


@router.post("/token", response_model=TokenResponse)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    access_token = create_access_token(
        {"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me")
def read_current_user(current_user: UserInDB = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }
