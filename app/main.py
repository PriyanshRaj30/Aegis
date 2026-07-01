# . app/main.py
# Bootstrap the app:

# Create FastAPI() app instance
# Call Base.metadata.create_all(bind=engine) to auto-create tables
# Register the auth router with app.include_router(auth_router, prefix="/auth")
from fastapi import FastAPI

from app.database.connection import Base, engine
from app.models.user import User
from app.models.roles import Role


from app.routes.auth import router as auth_router


from app.models.api_key import ApiKey       
from app.routes.api_keys import router as api_keys_router


from app.middleware.rate_limiter import RateLimitMiddleware

from app.models.audit_log import AuditLog          
from app.routes.analytics import router as analytics_router


app = FastAPI(title="Aegis API Gateway")

app.add_middleware(RateLimitMiddleware)

Base.metadata.create_all(bind=engine)

# app.include_router(auth_router, prefix="/auth") #/auth
app.include_router(auth_router) #/auth

app.include_router(api_keys_router)

app.include_router(analytics_router)

@app.get("/")
async def root():
    return {"message": "Aegis API is running"}

