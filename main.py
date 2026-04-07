"""
main.py
-------
Expenses REST API with automatic USD/UYU conversion.
Run with: uvicorn main:app --reload
Interactive docs at: http://localhost:8000/docs
"""

from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

import auth
import config
import database as db
import dolar_uy

# Validate config at startup — catches missing prod variables early
config.validate()
config.print_config()

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=config.APP_NAME,
    description="Track expenses in Uruguayan pesos and see their USD equivalent in real time.",
    version="1.0.0",
    # Disable interactive docs in production
    docs_url="/docs" if config.IS_DEV else None,
    redoc_url="/redoc" if config.IS_DEV else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()


# ── Schemas ───────────────────────────────────────────────────────────────────

VALID_CATEGORIES = [
    "food", "transport", "health", "entertainment",
    "clothing", "home", "education", "other",
]


class ExpenseRequest(BaseModel):
    amount_uyu:  float         = Field(..., gt=0, description="Amount in Uruguayan pesos")
    category:    str           = Field(..., description=f"One of: {', '.join(VALID_CATEGORIES)}")
    description: Optional[str] = Field(None, description="Optional note or description")
    date:        Optional[str] = Field(None, description="ISO 8601, e.g. '2026-05-20T14:30:00'. Defaults to now.")

    model_config = {"json_schema_extra": {
        "example": {"amount_uyu": 1500, "category": "food", "description": "Lunch downtown"}
    }}


class ExpenseResponse(BaseModel):
    id:          int
    amount_uyu:  float
    amount_usd:  float
    dollar_rate: float
    category:    str
    description: Optional[str]
    date:        str


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    id:       int
    username: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class MonthlySummary(BaseModel):
    month:     str
    count:     int
    total_uyu: float
    total_usd: float


class RateResponse(BaseModel):
    buy:        float
    sell:       float
    average:    float
    updated_at: str


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/auth/register", response_model=UserResponse, status_code=201, tags=["Auth"])
def register(body: UserRegisterRequest):
    """Creates a new user account."""
    if db.get_user_by_username(body.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
    user = db.create_user(body.username, auth.hash_password(body.password))
    return user


@app.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(form: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticates with username and password (form data).
    Returns a short-lived access token and a long-lived refresh token.
    """
    user = db.get_user_by_username(form.username)
    if not user or not auth.verify_password(form.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return {
        "access_token":  auth.create_access_token(user["username"]),
        "refresh_token": auth.create_refresh_token(user["username"]),
    }


@app.post("/auth/refresh", response_model=TokenResponse, tags=["Auth"])
def refresh(body: RefreshRequest):
    """Exchanges a valid refresh token for a new access token."""
    username = auth.decode_token(body.refresh_token, "refresh")
    user = db.get_user_by_username(username)
    if not user or not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return {
        "access_token":  auth.create_access_token(username),
        "refresh_token": auth.create_refresh_token(username),
    }


# ── Dollar ────────────────────────────────────────────────────────────────────

@app.get("/dollar", response_model=RateResponse, tags=["Dollar"])
def current_rate():
    """Returns the current USD/UYU exchange rate."""
    try:
        r = dolar_uy.get_dollar()
        return {"buy": r.buy, "sell": r.sell, "average": r.average, "updated_at": r.updated_at.isoformat()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Could not fetch exchange rate: {e}")


# ── Expenses ──────────────────────────────────────────────────────────────────

@app.post("/expenses", response_model=ExpenseResponse, status_code=201, tags=["Expenses"])
def create_expense(expense: ExpenseRequest, _: dict = Depends(auth.get_current_user)):
    """
    Records a new expense. Automatically fetches the current exchange rate
    and stores the USD equivalent alongside the rate used.
    """
    if expense.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Options: {', '.join(VALID_CATEGORIES)}",
        )
    try:
        rate = dolar_uy.get_dollar_cached()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Could not fetch exchange rate: {e}")

    date = None
    if expense.date:
        try:
            date = datetime.fromisoformat(expense.date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use ISO 8601.")

    return db.create_expense(
        amount_uyu  = expense.amount_uyu,
        amount_usd  = round(expense.amount_uyu / rate.buy, 2),
        dollar_rate = rate.sell,
        category    = expense.category,
        description = expense.description,
        date        = date,
    )


@app.get("/expenses", response_model=list[ExpenseResponse], tags=["Expenses"])
def list_expenses(
    month: Optional[str] = Query(None, description="Filter by month, format YYYY-MM. E.g. 2026-05"),
    _: dict = Depends(auth.get_current_user),
):
    """Lists all expenses, optionally filtered by month."""
    return db.list_expenses(month=month)


@app.get("/expenses/{expense_id}", response_model=ExpenseResponse, tags=["Expenses"])
def get_expense(expense_id: int, _: dict = Depends(auth.get_current_user)):
    """Returns a single expense by ID."""
    expense = db.get_expense(expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@app.delete("/expenses/{expense_id}", status_code=204, tags=["Expenses"])
def delete_expense(expense_id: int, _: dict = Depends(auth.get_current_user)):
    """Deletes an expense by ID."""
    if not db.delete_expense(expense_id):
        raise HTTPException(status_code=404, detail="Expense not found")


# ── Summary ───────────────────────────────────────────────────────────────────

@app.get("/summary/{month}", response_model=MonthlySummary, tags=["Summary"])
def monthly_summary(month: str, _: dict = Depends(auth.get_current_user)):
    """Returns total expenses for a given month in UYU and USD. Format: YYYY-MM"""
    return db.monthly_summary(month)


@app.get("/summary/{month}/categories", tags=["Summary"])
def summary_by_category(month: str, _: dict = Depends(auth.get_current_user)):
    """Returns monthly totals broken down by category."""
    return db.summary_by_category(month=month)

# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health():
    """Public endpoint to verify if API is running"""
    return {"status": "ok"}