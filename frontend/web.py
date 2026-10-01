"""
web.py
------
Server-rendered website: login, registration, dashboard and logout.

The website uses a signed session cookie (SessionMiddleware in main.py) instead
of JWTs — the browser never sees a token. Every form carries a CSRF token that
is checked against the one stored in the session.
"""

import secrets
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from backend import auth, config, dolar_uy
from backend import database as db
from backend.categories import VALID_CATEGORIES, VALID_INCOME_SOURCES

router = APIRouter(include_in_schema=False)

DESCRIPTION_MAX = 200  # characters, for expense and income descriptions

STATIC_DIR = Path(__file__).parent / "static"


def static_url(path: str) -> str:
    """URL for a file in static/, versioned by its mtime to bust browser caches."""
    version = int((STATIC_DIR / path).stat().st_mtime)
    return f"/static/{path}?v={version}"


templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals["static_url"] = static_url
templates.env.filters["money"] = lambda value: f"{value:,.2f}"
templates.env.globals["app_name"] = config.APP_NAME
templates.env.globals["categories"] = VALID_CATEGORIES
templates.env.globals["income_sources"] = VALID_INCOME_SOURCES
templates.env.globals["description_max"] = DESCRIPTION_MAX
templates.env.globals["account_rules"] = {
    "username_min": auth.USERNAME_MIN,
    "username_max": auth.USERNAME_MAX,
    "password_min": auth.PASSWORD_MIN,
}


# ── Session helpers ───────────────────────────────────────────────────────────


def _current_user(request: Request) -> dict | None:
    """Returns the logged-in user, or None. Clears stale sessions."""
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    user = db.get_user_by_id(user_id)
    if not user or not user["is_active"]:
        request.session.clear()
        return None
    return user


def _csrf_token(request: Request) -> str:
    """Returns the session's CSRF token, creating one if needed."""
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_urlsafe(32)
    return request.session["csrf"]


def _valid_csrf(request: Request, token: str) -> bool:
    expected = request.session.get("csrf")
    return bool(expected) and secrets.compare_digest(expected, token)


def _redirect(url: str) -> RedirectResponse:
    # 303 so the browser follows a POST with a GET
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


def _render_login(request: Request, error: str | None = None, status_code=200):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"csrf_token": _csrf_token(request), "error": error},
        status_code=status_code,
    )


# ── Auth ──────────────────────────────────────────────────────────────────────


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if _current_user(request):
        return _redirect("/")
    return _render_login(request)


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(""),
):
    if not _valid_csrf(request, csrf_token):
        return _render_login(request, "Your session expired. Please try again.", 400)

    user = db.get_user_by_username(username)
    if not user or not auth.verify_password(password, user["hashed_password"]):
        return _render_login(request, "Incorrect username or password.", 401)
    if not user["is_active"]:
        return _render_login(request, "This account is inactive.", 403)

    # Start a fresh session on login (prevents session fixation)
    request.session.clear()
    request.session["user_id"] = user["id"]
    return _redirect("/")


def _render_register(
    request: Request, error: str | None = None, username: str = "", status_code=200
):
    return templates.TemplateResponse(
        request,
        "register.html",
        {"csrf_token": _csrf_token(request), "error": error, "username": username},
        status_code=status_code,
    )


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if _current_user(request):
        return _redirect("/")
    return _render_register(request)


@router.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    csrf_token: str = Form(""),
):
    if not _valid_csrf(request, csrf_token):
        return _render_register(
            request, "Your session expired. Please try again.", username, 400
        )

    if not auth.USERNAME_MIN <= len(username) <= auth.USERNAME_MAX:
        error = (
            f"Username must be {auth.USERNAME_MIN} to {auth.USERNAME_MAX} characters."
        )
        return _render_register(request, error, username, 400)
    if len(password) < auth.PASSWORD_MIN:
        error = f"Password must be at least {auth.PASSWORD_MIN} characters."
        return _render_register(request, error, username, 400)
    if password != password_confirm:
        return _render_register(request, "Passwords don't match.", username, 400)
    if db.get_user_by_username(username):
        return _render_register(request, "That username is taken.", username, 409)

    user = db.create_user(username, auth.hash_password(password))

    # Log the new user in with a fresh session
    request.session.clear()
    request.session["user_id"] = user["id"]
    return _redirect("/")


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form("")):
    if _valid_csrf(request, csrf_token):
        request.session.clear()
    return _redirect("/login")


# ── Dashboard ─────────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, month: str | None = None):
    user = _current_user(request)
    if not user:
        return _redirect("/login")

    # Ignore anything that isn't a valid YYYY-MM month
    month_label = None
    if month:
        try:
            month_label = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        except ValueError:
            month = None

    expenses = db.list_expenses(user["id"], month=month)
    incomes = db.list_incomes(user["id"], month=month)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "csrf_token": _csrf_token(request),
            "flash": request.session.pop("flash", None),
            "entries": _combined_entries(incomes, expenses),
            "month": month,
            "month_label": month_label,
            "expenses_count": len(expenses),
            "incomes_count": len(incomes),
            "totals": _totals(incomes, expenses),
            "chart": _monthly_chart(user["id"]),
        },
    )


def _combined_entries(incomes: list[dict], expenses: list[dict]) -> list[dict]:
    """Incomes and expenses in one list, newest first, tagged with their kind."""
    entries = [{**e, "kind": "expense", "label": e["category"]} for e in expenses]
    entries += [{**i, "kind": "income", "label": i["source"]} for i in incomes]
    return sorted(entries, key=lambda e: e["date"], reverse=True)


def _totals(incomes: list[dict], expenses: list[dict]) -> dict:
    """Income, expense and net (income - expenses) totals in both currencies."""

    def total(rows: list[dict], key: str) -> float:
        # Round so float noise can't show up as e.g. "-0.00"
        return round(sum(r[key] for r in rows), 2)

    result = {}
    for currency in ("uyu", "usd"):
        key = f"amount_{currency}"
        income, spent = total(incomes, key), total(expenses, key)
        result[currency] = {
            "income": income,
            "expenses": spent,
            "net": round(income - spent, 2),
        }
    return result


CHART_MONTHS = 12


def _monthly_chart(user_id: int) -> dict | None:
    """
    Expense totals for the last CHART_MONTHS months (including this one),
    with empty months filled in as 0. None if there's nothing to plot.
    """
    today = datetime.now()
    months = []
    for back in range(CHART_MONTHS - 1, -1, -1):
        # Walk back from the current month, handling the year boundary
        year, month = divmod(today.year * 12 + today.month - 1 - back, 12)
        months.append(f"{year:04d}-{month + 1:02d}")

    totals = {r["month"]: r for r in db.monthly_totals(user_id, since_month=months[0])}
    if not totals:
        return None

    empty = {"total_uyu": 0.0, "total_usd": 0.0}
    return {
        "months": months,
        "labels": [datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in months],
        "uyu": [totals.get(m, empty)["total_uyu"] for m in months],
        "usd": [totals.get(m, empty)["total_usd"] for m in months],
    }


# ── New entry ─────────────────────────────────────────────────────────────────


def _parse_amount(raw: str) -> Decimal | None:
    """Parses a positive decimal amount, rounded to cents. None if invalid."""
    try:
        amount = Decimal(raw.strip().replace(",", "."))
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount <= 0:
        return None
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@router.post("/entries")
def create_entry(
    request: Request,
    kind: str = Form(...),
    amount: str = Form(...),
    currency: str = Form(...),
    category: str = Form(""),
    source: str = Form(""),
    description: str = Form(""),
    csrf_token: str = Form(""),
):
    user = _current_user(request)
    if not user:
        return _redirect("/login")
    if not _valid_csrf(request, csrf_token):
        request.session["flash"] = ("error", "Your session expired. Please try again.")
        return _redirect("/")

    value = _parse_amount(amount)
    if kind not in ("expense", "income") or currency not in ("UYU", "USD") or not value:
        request.session["flash"] = ("error", "Please enter a valid amount.")
        return _redirect("/")
    if (kind == "expense" and category not in VALID_CATEGORIES) or (
        kind == "income" and source not in VALID_INCOME_SOURCES
    ):
        field = "category" if kind == "expense" else "source"
        request.session["flash"] = ("error", f"Please choose a {field}.")
        return _redirect("/")
    description = description.strip()
    if len(description) > DESCRIPTION_MAX:
        error = f"Description must be at most {DESCRIPTION_MAX} characters."
        request.session["flash"] = ("error", error)
        return _redirect("/")

    try:
        rate = dolar_uy.get_dollar_cached()
    except Exception:
        request.session["flash"] = ("error", "Could not fetch the exchange rate.")
        return _redirect("/")

    # Same conversion as the JSON API: USD = UYU / buy rate
    if currency == "UYU":
        amount_uyu = float(value)
        amount_usd = round(amount_uyu / rate.buy, 2)
    else:
        amount_usd = float(value)
        amount_uyu = round(amount_usd * rate.buy, 2)

    entry = {
        "user_id": user["id"],
        "amount_uyu": amount_uyu,
        "amount_usd": amount_usd,
        "dollar_rate": rate.sell,
        "description": description or None,
    }
    if kind == "expense":
        db.create_expense(**entry, category=category)
    else:
        db.create_income(**entry, source=source)

    request.session["flash"] = ("success", f"{kind.capitalize()} added.")
    return _redirect("/")


@router.post("/entries/{kind}/{entry_id}/delete")
def delete_entry(
    request: Request,
    kind: str,
    entry_id: int,
    month: str = Form(""),
    csrf_token: str = Form(""),
):
    user = _current_user(request)
    if not user:
        return _redirect("/login")

    # Return to the month being viewed (only a valid YYYY-MM, never a raw URL)
    try:
        back = "/?month=" + datetime.strptime(month, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        back = "/"

    if not _valid_csrf(request, csrf_token):
        request.session["flash"] = ("error", "Your session expired. Please try again.")
        return _redirect(back)

    delete = {"expense": db.delete_expense, "income": db.delete_income}.get(kind)
    # Deletes are scoped to the user, so another user's id just reads as not found
    if not delete or not delete(entry_id, user["id"]):
        request.session["flash"] = ("error", "That entry no longer exists.")
        return _redirect(back)

    request.session["flash"] = ("success", f"{kind.capitalize()} deleted.")
    return _redirect(back)
