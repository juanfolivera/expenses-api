# Expenses API 💵

REST API to track expenses in Uruguayan pesos with automatic USD conversion.

## Stack

- **FastAPI** — REST API framework
- **PostgreSQL** (production) / **SQLite** (local dev)
- **DolarApi.com** — real-time USD/UYU rate (no API key needed)
- **python-jose** — JWT token generation and validation
- **passlib + bcrypt** — password hashing
- **python-dotenv** — environment-based configuration

---

## Project structure

```
expenses-api/
├── backend/
│   ├── main.py      # App entrypoint and API endpoints
│   ├── auth.py      # JWT utilities and get_current_user dependency
│   ├── database.py  # SQLite / PostgreSQL CRUD
│   ├── dolar_uy.py  # USD/UYU exchange rate client
│   ├── categories.py # Allowed expense categories and income sources
│   └── config.py    # Central configuration (reads from env vars)
├── frontend/
│   ├── web.py       # Website routes: login, dashboard, logout
│   ├── templates/   # Jinja2 templates
│   └── static/      # CSS (served at /static)
├── requirements.txt # Dependencies
├── Procfile         # Railway startup command
├── .env             # Local env variables — never commit this
├── .env.example     # Template to share with teammates
└── .gitignore
```

---

## Local development

### 1. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate   # Mac/Linux
# venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

The default `.env` works out of the box for local development — SQLite is used automatically when `DATABASE_URL` is not set.

### 3. Start the server

```bash
uvicorn backend.main:app --reload
```

Server runs at `http://localhost:8000`  
Interactive docs at `http://localhost:8000/docs`

---

## Environment variables

All configuration is managed through environment variables. Locally they are loaded from `.env`; in Railway they are set in the dashboard.

| Variable | Description | Dev default | Prod |
|---|---|---|---|
| `ENVIRONMENT` | `development` or `production` | `development` | `production` |
| `DEBUG` | Verbose logging + Swagger UI | `true` | `false` |
| `DATABASE_URL` | PostgreSQL connection URL | not set → SQLite | set by Railway |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins | `*` | your app's URL |
| `APP_NAME` | Display name in API docs | `Expenses API (dev)` | `Expenses API` |
| `DOLLAR_CACHE_TTL` | Seconds to cache the exchange rate | `60` | `300` |
| `JWT_SECRET_KEY` | Secret key to sign JWT tokens | insecure dev key | **must be set** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `30` | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `30` | `30` |

> `.env` is listed in `.gitignore` and should never be committed.  
> Commit `.env.example` instead — it's a safe, empty template.

---

## Deploy to Railway

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "first commit"
# create a repo on github.com, then:
git remote add origin https://github.com/YOUR_USER/expenses-api.git
git push -u origin main
```

### 2. Create project on Railway

1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Select your repository — Railway detects FastAPI automatically

### 3. Add PostgreSQL

1. Inside your Railway project, click **+ New → Database → PostgreSQL**
2. Railway injects `DATABASE_URL` into your app automatically

### 4. Set production environment variables

In your Railway project go to **Variables** and add:

```
ENVIRONMENT=production
APP_NAME=Expenses API
ALLOWED_ORIGINS=https://your-app-url.com
DOLLAR_CACHE_TTL=300
JWT_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
```

> `DEBUG` and `DATABASE_URL` don't need to be set manually —  
> `DEBUG` defaults to `false` in production, and `DATABASE_URL` is injected by Railway.

### 5. Done 🎉

Your API will be live at `https://your-project.up.railway.app`

> **Note:** Swagger UI (`/docs`) is disabled in production automatically.  
> To explore the API, run the project locally or temporarily set `DEBUG=true` in Railway.

---

## Endpoints

### Auth (public)

| Method | URL | Description |
|---|---|---|
| POST | `/auth/register` | Create a new user account |
| POST | `/auth/login` | Login and receive tokens |
| POST | `/auth/refresh` | Exchange a refresh token for a new access token |

### Expenses (requires token)

| Method | URL | Description |
|---|---|---|
| POST | `/expenses` | Record a new expense |
| GET | `/expenses` | List all expenses |
| GET | `/expenses?month=2026-05` | Filter by month |
| GET | `/expenses/{id}` | Get a single expense |
| DELETE | `/expenses/{id}` | Delete an expense |
| GET | `/summary/2026-05` | Monthly total in UYU and USD |
| GET | `/summary/2026-05/categories` | Breakdown by category |

### Incomes (requires token)

| Method | URL | Description |
|---|---|---|
| POST | `/incomes` | Record a new income (e.g. salary) |
| GET | `/incomes` | List all incomes |
| GET | `/incomes?month=2026-05` | Filter by month |
| GET | `/incomes/{id}` | Get a single income |
| DELETE | `/incomes/{id}` | Delete an income |

### Other (public)

| Method | URL | Description |
|---|---|---|
| GET | `/dollar` | Current USD/UYU exchange rate |
| GET | `/health` | API health check |

All protected endpoints require the header:
```
Authorization: Bearer <access_token>
```

## Categories

`food` · `transport` · `health` · `entertainment` · `clothing` · `home` · `education` · `other`

## Income sources

`salary` · `freelance` · `investment` · `gift` · `other`

---

## Example (curl)

```bash
# Register a new user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "juan", "password": "mysecretpass"}'

# Login — returns access_token and refresh_token
curl -X POST http://localhost:8000/auth/login \
  -F "username=juan" \
  -F "password=mysecretpass"

# Store the token
TOKEN="<access_token from login response>"

# Record an expense
curl -X POST http://localhost:8000/expenses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount_uyu": 1500, "category": "food", "description": "Lunch"}'

# Record your monthly salary
curl -X POST http://localhost:8000/incomes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount_uyu": 85000, "source": "salary", "description": "May salary"}'

# List expenses for May
curl http://localhost:8000/expenses?month=2026-05 \
  -H "Authorization: Bearer $TOKEN"

# Monthly summary
curl http://localhost:8000/summary/2026-05 \
  -H "Authorization: Bearer $TOKEN"

# Renew access token using refresh token
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'

# Current exchange rate (public, no token needed)
curl http://localhost:8000/dollar
```
