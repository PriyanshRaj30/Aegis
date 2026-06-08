Client
   │
   ▼
FastAPI Gateway
   │
   ├──────── Redis
   │          │
   │          ├─ Rate Limits
   │          ├─ Risk Scores
   │          └─ Bans
   │
   ├──────── PostgreSQL
   │          │
   │          ├─ Users
   │          ├─ API Keys
   │          ├─ Audit Logs
   │          └─ Analytics
   │
   └──────── Backend Servicepython -m venv venv