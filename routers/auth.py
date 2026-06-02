from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.orm import Session

from database import get_db, User
from auth_utils import hash_password, verify_password, create_token, get_current_user

router = APIRouter()

DEMO_EMAIL    = "user@demo.com"
DEMO_PASSWORD = "demo123"
DEMO_NAME     = "Demo User"


# ── Schemas ────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

    @validator("name")
    def name_not_empty(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v.strip()

    @validator("password")
    def password_strong_enough(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=TokenOut, status_code=201)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=body.name,
        email=body.email,
        password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id, user.email)
    return TokenOut(access_token=token, user=UserOut.from_orm(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    # Demo account — auto-create if missing
    if body.email == DEMO_EMAIL and body.password == DEMO_PASSWORD:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if not user:
            user = User(
                name=DEMO_NAME,
                email=DEMO_EMAIL,
                password=hash_password(DEMO_PASSWORD),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        token = create_token(user.id, user.email)
        return TokenOut(access_token=token, user=UserOut.from_orm(user))

    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(user.id, user.email)
    return TokenOut(access_token=token, user=UserOut.from_orm(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
