import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# Tenta pegar a URL do Render. Se não tiver, usa a Local (SQL Server)
DATABASE_URL = os.getenv("DATABASE_URL", "mssql+aioodbc://sa:Str0ngP@ssword!@localhost:1433/master?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes")

# CORREÇÃO CRÍTICA PARA O RENDER:
# O Render fornece "postgres://", mas o SQLAlchemy exige "postgresql+asyncpg://"
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session