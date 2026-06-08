from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = (
    "postgresql://postgres:password@localhost:5433/gateway"
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autoflush=False,
    autocommit=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
        
# Verify connection
def test_Connection():
    try:
        engine.connect()
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {e}")
        
