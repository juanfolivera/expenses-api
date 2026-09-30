"""
web.py
------
Server-rendered website: login, dashboard and logout.

The website uses a signed session cookie (SessionMiddleware in main.py) instead
of JWTs — the browser never sees a token. Every form carries a CSRF token that
is checked against the one stored in the session.
"""

import secrets
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import auth
import config
import database as db

router = APIRouter(include_in_schema=False)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["money"] = lambda value: f"{value:,.2f}"
templates.env.globals["app_name"] = config.APP_NAME


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
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "csrf_token": _csrf_token(request),
            "expenses": expenses,
            "month": month,
            "month_label": month_label,
            "total_uyu": sum(e["amount_uyu"] for e in expenses),
            "total_usd": sum(e["amount_usd"] for e in expenses),
        },
    )
