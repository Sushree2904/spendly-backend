"""
AI Insights Engine
------------------
Two modes:
  1. Rule-based  — always works, zero dependencies
  2. Ollama      — set OLLAMA_URL env var to enable richer natural-language summaries
"""
import os
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date, timedelta
from typing import List, Dict
import httpx

from database import get_db, Expense, Budget, User
from auth_utils import get_current_user

router   = APIRouter()
OLLAMA   = os.getenv("OLLAMA_URL", "")   # e.g. "http://localhost:11434"


# ── Rule-based insight engine ──────────────────────────────────────────────────

def rule_based_insights(expenses: List[Expense], budgets: Dict[str, float]) -> List[dict]:
    insights = []
    today       = date.today()
    month_start = today.replace(day=1)
    week_start  = today - timedelta(days=today.weekday())

    month_expenses = [e for e in expenses if e.date >= month_start]
    week_expenses  = [e for e in expenses if e.date >= week_start]

    # 1. Top spending category
    cat_totals: Dict[str, float] = {}
    for e in month_expenses:
        cat_totals[e.category] = cat_totals.get(e.category, 0) + e.amount
    if cat_totals:
        top_cat = max(cat_totals, key=cat_totals.get)
        insights.append({
            "type": "info",
            "icon": "📊",
            "title": "Top Category This Month",
            "message": f"You spent the most on {top_cat} (₹{cat_totals[top_cat]:,.0f}) this month.",
        })

    # 2. Week over week comparison
    prev_week_start = week_start - timedelta(days=7)
    prev_week = [e for e in expenses if prev_week_start <= e.date < week_start]
    curr_week_total = sum(e.amount for e in week_expenses)
    prev_week_total = sum(e.amount for e in prev_week)
    if prev_week_total > 0:
        diff_pct = ((curr_week_total - prev_week_total) / prev_week_total) * 100
        if diff_pct > 20:
            insights.append({
                "type": "warning",
                "icon": "📈",
                "title": "Spending Up This Week",
                "message": f"This week's spending is {diff_pct:.0f}% higher than last week. Consider reviewing your expenses.",
            })
        elif diff_pct < -20:
            insights.append({
                "type": "success",
                "icon": "📉",
                "title": "Great Savings This Week!",
                "message": f"You're spending {abs(diff_pct):.0f}% less than last week. Keep it up!",
            })

    # 3. Budget warnings per category
    total_budget = budgets.get("total", 0)
    total_spent  = sum(e.amount for e in month_expenses)
    if total_budget > 0:
        pct = (total_spent / total_budget) * 100
        if pct >= 100:
            insights.append({
                "type": "danger",
                "icon": "🚨",
                "title": "Monthly Budget Exceeded!",
                "message": f"You've spent ₹{total_spent:,.0f} out of ₹{total_budget:,.0f} budget ({pct:.0f}%). Immediate action needed.",
            })
        elif pct >= 80:
            insights.append({
                "type": "warning",
                "icon": "⚠️",
                "title": "Budget Alert",
                "message": f"You've used {pct:.0f}% of your monthly budget. Only ₹{total_budget - total_spent:,.0f} remaining.",
            })

    # 4. Category-level budget check
    for cat, budget_amt in budgets.items():
        if cat == "total" or budget_amt == 0:
            continue
        spent = cat_totals.get(cat, 0)
        if spent > budget_amt:
            insights.append({
                "type": "danger",
                "icon": "❌",
                "title": f"{cat} Budget Exceeded",
                "message": f"You've exceeded your {cat} budget by ₹{spent - budget_amt:,.0f}.",
            })

    # 5. Streak / encouragement
    if not month_expenses:
        insights.append({
            "type": "info",
            "icon": "🎯",
            "title": "No Expenses Yet",
            "message": "Start logging your expenses to get personalized insights!",
        })
    elif total_budget > 0 and (total_spent / total_budget) < 0.5:
        days_left = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day - today.day
        insights.append({
            "type": "success",
            "icon": "🎉",
            "title": "On Track!",
            "message": f"You've only used {(total_spent/total_budget*100):.0f}% of your budget with {days_left} days left. Excellent discipline!",
        })

    # 6. Frequent small purchases
    food_count = sum(1 for e in month_expenses if e.category == "Food")
    if food_count > 15:
        insights.append({
            "type": "tip",
            "icon": "💡",
            "title": "Frequent Food Purchases",
            "message": f"You've logged {food_count} food expenses this month. Meal prepping could save you money!",
        })

    return insights


# ── Ollama integration (optional) ──────────────────────────────────────────────

async def ollama_summary(context: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{OLLAMA}/api/generate", json={
                "model": "llama3.2",
                "prompt": f"""You are a financial advisor. Analyze this expense data and give 2-3 actionable tips in plain English (max 100 words):

{context}

Keep it friendly, practical, and specific.""",
                "stream": False,
            })
            if resp.status_code == 200:
                return resp.json().get("response", "")
    except Exception:
        pass
    return ""


# ── Route ──────────────────────────────────────────────────────────────────────

@router.get("/")
async def get_insights(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    expenses = db.query(Expense).filter(Expense.user_id == user.id).all()
    budgets_raw = db.query(Budget).filter(Budget.user_id == user.id).all()
    budgets = {b.category: b.amount for b in budgets_raw}

    insights = rule_based_insights(expenses, budgets)

    # Optional Ollama enrichment
    ai_summary = ""
    if OLLAMA and expenses:
        today = date.today()
        month_start = today.replace(day=1)
        month_exp = [e for e in expenses if e.date >= month_start]
        if month_exp:
            cat_summary = {}
            for e in month_exp:
                cat_summary[e.category] = cat_summary.get(e.category, 0) + e.amount
            context = f"Monthly budget: ₹{budgets.get('total', 0):,.0f}\n"
            context += f"Total spent this month: ₹{sum(cat_summary.values()):,.0f}\n"
            context += "Category breakdown:\n"
            for cat, amt in cat_summary.items():
                context += f"  {cat}: ₹{amt:,.0f} (budget: ₹{budgets.get(cat, 0):,.0f})\n"
            ai_summary = await ollama_summary(context)

    return {
        "insights": insights,
        "ai_summary": ai_summary,
        "ollama_enabled": bool(OLLAMA),
    }
