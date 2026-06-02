from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Dict

from database import get_db, Budget, User
from auth_utils import get_current_user

router = APIRouter()

VALID_CATEGORIES = ["Food", "Transport", "Housing", "Entertainment", "Shopping", "Health", "Other", "total"]

DEFAULT_BUDGETS = {
    "total": 50000,
    "Food": 10000,
    "Transport": 5000,
    "Housing": 15000,
    "Entertainment": 5000,
    "Shopping": 7000,
    "Health": 5000,
    "Other": 3000,
}


class BudgetUpdate(BaseModel):
    budgets: Dict[str, float]


class BudgetOut(BaseModel):
    category: str
    amount: float

    class Config:
        from_attributes = True


@router.get("/", response_model=List[BudgetOut])
def get_budgets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    existing = {b.category: b for b in db.query(Budget).filter(Budget.user_id == user.id).all()}

    # Seed defaults for new users
    if not existing:
        for cat, amount in DEFAULT_BUDGETS.items():
            b = Budget(user_id=user.id, category=cat, amount=amount)
            db.add(b)
        db.commit()
        return [Budget(category=k, amount=v) for k, v in DEFAULT_BUDGETS.items()]

    # Return with any missing defaults
    result = []
    for cat in VALID_CATEGORIES:
        if cat in existing:
            result.append(existing[cat])
        else:
            b = Budget(user_id=user.id, category=cat, amount=DEFAULT_BUDGETS.get(cat, 0))
            db.add(b)
            result.append(b)
    db.commit()
    return result


@router.put("/")
def update_budgets(
    body: BudgetUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = {b.category: b for b in db.query(Budget).filter(Budget.user_id == user.id).all()}

    for cat, amount in body.budgets.items():
        if cat not in VALID_CATEGORIES:
            continue
        if cat in existing:
            existing[cat].amount = max(0, amount)
        else:
            db.add(Budget(user_id=user.id, category=cat, amount=max(0, amount)))

    db.commit()
    return {"message": "Budgets updated successfully"}
