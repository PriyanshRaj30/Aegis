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

app = FastAPI(title="Aegis API Gateway")

Base.metadata.create_all(bind=engine)

# app.include_router(auth_router, prefix="/auth") #/auth
app.include_router(auth_router) #/auth


@app.get("/")
async def root():
    return {"message": "Aegis API is running"}


