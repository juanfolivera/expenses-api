# Expenses API 💵

REST API to track expenses in Uruguayan pesos with automatic USD conversion.

## Stack

- **FastAPI** — REST API framework
- **PostgreSQL** (production) / **SQLite** (local dev)
- **DolarApi.com** — real-time USD/UYU rate (no API key needed)
- **python-dotenv** — environment-based configuration

---

## Project structure

```
expenses-api/
├── main.py          # API endpoints
├── database.py      # SQLite / PostgreSQL CRUD
├── dolar_uy.py      # USD/UYU exchange rate client
├── config.py        # Central configuration (reads from env vars)
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
uvicorn main:app --reload
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
```

> `DEBUG` and `DATABASE_URL` don't need to be set manually —  
> `DEBUG` defaults to `false` in production, and `DATABASE_URL` is injected by Railway.

### 5. Done 🎉

Your API will be live at `https://your-project.up.railway.app`

> **Note:** Swagger UI (`/docs`) is disabled in production automatically.  
> To explore the API, run the project locally or temporarily set `DEBUG=true` in Railway.

---

## Endpoints

| Method | URL | Description |
|---|---|---|
| GET | `/dollar` | Current USD/UYU exchange rate |
| POST | `/expenses` | Record a new expense |
| GET | `/expenses` | List all expenses |
| GET | `/expenses?month=2026-05` | Filter by month |
| GET | `/expenses/{id}` | Get a single expense |
| DELETE | `/expenses/{id}` | Delete an expense |
| GET | `/summary/2026-05` | Monthly total in UYU and USD |
| GET | `/summary/2026-05/categories` | Breakdown by category |

## Categories

`food` · `transport` · `health` · `entertainment` · `clothing` · `home` · `education` · `other`

---

## Example (curl)

```bash
# Record an expense
curl -X POST http://localhost:8000/expenses \
  -H "Content-Type: application/json" \
  -d '{"amount_uyu": 1500, "category": "food", "description": "Lunch"}'

# List expenses for May
curl http://localhost:8000/expenses?month=2026-05

# Monthly summary
curl http://localhost:8000/summary/2026-05

# Current exchange rate
curl http://localhost:8000/dollar
```
