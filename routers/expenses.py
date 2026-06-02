from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date, datetime

from database import get_db, Expense, User
from auth_utils import get_current_user

router = APIRouter()

VALID_CATEGORIES = ["Food", "Transport", "Housing", "Entertainment", "Shopping", "Health", "Other"]


# ── Schemas ────────────────────────────────────────────────────────────────────

class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: str
    date: date
    note: Optional[str] = ""

    @validator("title")
    def title_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

    @validator("amount")
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return round(v, 2)

    @validator("category")
    def category_valid(cls, v):
        if v not in VALID_CATEGORIES:
            raise ValueError(f"Category must be one of {VALID_CATEGORIES}")
        return v


class ExpenseOut(BaseModel):
    id: int
    title: str
    amount: float
    category: str
    date: date
    note: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[ExpenseOut])
def list_expenses(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Expense).filter(Expense.user_id == user.id)
    if category and category != "All":
        q = q.filter(Expense.category == category)
    if search:
        q = q.filter(Expense.title.ilike(f"%{search}%"))
    return q.order_by(Expense.date.desc()).all()


@router.post("/", response_model=ExpenseOut, status_code=201)
def create_expense(
    body: ExpenseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    expense = Expense(user_id=user.id, **body.dict())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=204)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    expense = db.query(Expense).filter(
        Expense.id == expense_id, Expense.user_id == user.id
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()


@router.get("/stats/summary")
def expense_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from sqlalchemy import func
    from datetime import timedelta

    today = date.today()
    month_start = today.replace(day=1)
    week_start  = today - timedelta(days=today.weekday())

    all_expenses = db.query(Expense).filter(Expense.user_id == user.id).all()

    month_total = sum(e.amount for e in all_expenses if e.date >= month_start)
    week_total  = sum(e.amount for e in all_expenses if e.date >= week_start)
    total_count = len(all_expenses)

    # Category breakdown (current month)
    cat_breakdown = {}
    for e in all_expenses:
        if e.date >= month_start:
            cat_breakdown[e.category] = cat_breakdown.get(e.category, 0) + e.amount

    # Last 6 months bar chart data
    monthly_data = {}
    for e in all_expenses:
        key = e.date.strftime("%b %Y")
        monthly_data[key] = monthly_data.get(key, 0) + e.amount

    return {
        "month_total": round(month_total, 2),
        "week_total": round(week_total, 2),
        "total_count": total_count,
        "category_breakdown": {k: round(v, 2) for k, v in cat_breakdown.items()},
        "monthly_data": monthly_data,
    }
