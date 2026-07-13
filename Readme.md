```markdown
# Aegis 🛡️

**Abuse-Aware API Gateway** — production-inspired protection for your APIs.

Aegis sits in front of your backend services and makes intelligent, real-time decisions on every incoming request: allow, throttle, challenge, or ban. It combines multiple rate-limiting algorithms with a behavioural risk engine that adapts over time.

---

## How It Works

```
Client Request
      │
      ▼
┌─────────────────────┐
│   Ban Check         │  ← IP or API key banned? Reject immediately (403)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Sliding Window     │  ← Too many requests in the last N seconds? (429)
│  Rate Limiter       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Token Bucket       │  ← Burst absorbed? Still within sustained limit?
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Risk Engine        │  ← Accumulate score → throttle_light / throttle_heavy / ban
│  (Decay Scoring)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Audit Log          │  ← Every request logged to PostgreSQL
└──────────┬──────────┘
           │
           ▼
      Backend API
```

---

## Key Features

### Rate Limiting
- **Sliding Window** — per-IP and per-API-key request counting over a rolling time window
- **Token Bucket** — absorbs short bursts while enforcing a sustained rate; implemented with an atomic Lua script in Redis to eliminate race conditions
- **Burst Detection** — per-second spike detector using Redis INCR + auto-expiry

### Behavioural Risk Engine
- **Multi-dimensional scoring** — IP reputation and API key reputation tracked independently
- **Exponential decay** — scores decay automatically over time so legitimate users recover without manual intervention
- **Atomic score updates** — a single Lua script handles read → decay → add → write as one Redis operation
- **Graduated response** — `allow → throttle_light → throttle_heavy → banned` (no binary on/off)
- **Configurable signal weights** — each abuse signal (rate limit hit, 401, 403, 404, burst) contributes a tunable point value

### Authentication & Access Control
- **JWT authentication** with configurable algorithm and secret
- **Role-Based Access Control (RBAC)** — admin-only routes enforced via dependency injection
- **API Key management** — create, list, delete keys with per-key rate limits and optional expiry
- **Password hashing** via bcrypt

### Observability
- **Prometheus metrics** exposed on `/metrics` with rich labels
- **Audit logging** — every request written to PostgreSQL with IP, method, path, status code, risk score, and rate-limit flag
- **Risk score response header** — `X-RateLimit-Risk-Score` appended to every allowed response

---

## Tech Stack

| Layer              | Technology                          |
|--------------------|-------------------------------------|
| **API Framework**  | FastAPI                             |
| **Language**       | Python 3.11+                        |
| **Database**       | PostgreSQL (SQLAlchemy ORM)         |
| **Cache / Rate Limiting** | Redis (Lua scripting for atomicity) |
| **Auth**           | JWT (`python-jose`) + bcrypt (`passlib`) |
| **Metrics**        | Prometheus (`prometheus-client`)    |
| **Config**         | Pydantic Settings (`.env` file)     |
| **Container**      | Docker + Docker Compose             |

---

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.11+

### Run with Docker Compose

```bash
# Clone the repo
git clone https://github.com/youruser/aegis.git
cd aegis

# Copy and configure environment variables
cp app/.env.example app/.env

# Start all services (PostgreSQL, Redis)
docker-compose up -d
```

### Run Locally (Development)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start the gateway
uvicorn app.main:app --reload --port 8000
```

API docs are available at: http://localhost:8000/docs

---

## Configuration

All settings are driven by environment variables. Copy `app/.env.example` to `app/.env` and adjust:

```env
# Auth
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/aegis

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Rate Limiting
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60
TOKEN_BUCKET_CAPACITY=10
TOKEN_BUCKET_REFILL_RATE=1.0

# Risk Engine
RISK_DECAY_RATE=0.95
RISK_LIGHT_THROTTLE_THRESHOLD=30
RISK_HEAVY_THROTTLE_THRESHOLD=60
RISK_BAN_THRESHOLD=80
BAN_DURATION_SECONDS=3600

# Signal Weights
WEIGHT_RATE_LIMIT_SLIDING=20.0
WEIGHT_BURST_DETECTED=35.0
WEIGHT_INVALID_API_KEY=20.0
WEIGHT_STATUS_401=10.0
WEIGHT_STATUS_403=25.0
WEIGHT_STATUS_404=5.0
```

---

## API Reference

| Method | Path                  | Auth          | Description                          |
|--------|-----------------------|---------------|--------------------------------------|
| `POST` | `/auth/register`      | None          | Register a new user                  |
| `POST` | `/auth/login`         | None          | Login, receive JWT                   |
| `POST` | `/api-keys`           | JWT           | Create a new API key                 |
| `GET`  | `/api-keys`           | JWT           | List your API keys                   |
| `DELETE`| `/api-keys/{id}`     | JWT           | Delete an API key                    |
| `GET`  | `/analytics/summary`  | JWT (ADMIN)   | Audit log summary                    |
| `GET`  | `/metrics`            | None          | Prometheus metrics                   |

---

## Project Structure

```
app/
├── main.py               # FastAPI app, middleware registration, router wiring
├── config.py             # Pydantic settings — all config in one place
├── middleware/
│   └── rate_limiter.py   # Core middleware: ban check → rate limit → risk score → audit
├── services/
│   ├── risk_engine.py    # Exponential decay scoring, ban helpers, Lua script
│   ├── token_bucket.py   # Token bucket algorithm (atomic Lua script)
│   ├── burst_detector.py # Per-second burst spike detection
│   ├── rate_limiter.py   # Sliding window check orchestration
│   ├── auth_service.py   # Registration, login, JWT issuance
│   ├── api_key_service.py# CRUD for API keys
│   └── audit_service.py  # Audit log writes and summary queries
├── routes/
│   ├── auth.py           # /auth/register, /auth/login
│   ├── api_keys.py       # /api-keys CRUD
│   └── analytics.py      # /analytics/summary (admin only)
├── models/               # SQLAlchemy ORM models
├── schemas/              # Pydantic request/response schemas
├── security/             # JWT handler, password hashing
├── metrics/              # Prometheus counter/histogram/gauge definitions
├── redis/                # Redis connection singleton
└── database/             # SQLAlchemy engine, session factory
```

---

## Design Decisions

**Why Lua scripts for rate limiting?**  
The token bucket and risk score operations each require read → compute → write in Redis. Lua scripts execute as a single Redis command, making the operations atomic and race-free.

**Why exponential decay on risk scores?**  
It allows legitimate users to recover gracefully while keeping persistent abusers at elevated risk. This mirrors real-world reputation systems.

**Why multi-dimensional scoring (IP + API key)?**  
Tracking both independently makes evasion significantly harder (rotating proxies or keys alone is no longer sufficient).

---
