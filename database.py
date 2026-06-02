"""
Database configuration.
Uses MySQL if DATABASE_URL is set, otherwise falls back to SQLite for easy local dev.
"""
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# Default to SQLite for easy demo/development — swap to MySQL in production:
# DATABASE_URL = "mysql+pymysql://user:password@localhost:3306/expense_tracker"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./expense_tracker.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─── Models ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(100), nullable=False)
    email      = Column(String(150), unique=True, index=True, nullable=False)
    password   = Column(String(255), nullable=False)  # bcrypt hash
    created_at = Column(DateTime, default=datetime.utcnow)

    expenses = relationship("Expense", back_populates="owner", cascade="all, delete-orphan")
    budgets  = relationship("Budget",  back_populates="owner", cascade="all, delete-orphan")


class Expense(Base):
    __tablename__ = "expenses"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    title      = Column(String(200), nullable=False)
    amount     = Column(Float, nullable=False)
    category   = Column(String(50), nullable=False)
    date       = Column(Date, nullable=False)
    note       = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="expenses")


class Budget(Base):
    __tablename__ = "budgets"

    id       = Column(Integer, primary_key=True, index=True)
    user_id  = Column(Integer, ForeignKey("users.id"), nullable=False)
    category = Column(String(50), nullable=False)   # "total" for overall budget
    amount   = Column(Float, nullable=False, default=0.0)

    owner = relationship("User", back_populates="budgets")


# ─── Helpers ───────────────────────────────────────────────────────────────────

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
