# backend/app/db.py (example)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

DB_URL = settings.DB_URL

engine = create_engine(DB_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async_engine = create_async_engine(settings.ASYNC_DB_URL)
# Création d'une "usine" à sessions asynchrones, comme dans votre exemple
AsyncSessionFactory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# La dépendance FastAPI utilise l'usine pour créer une session par requête
async def get_async_db():
    async with AsyncSessionFactory() as session:
        yield session
