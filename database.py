import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# Tenta pegar a URL do ambiente (Nuvem). Se não tiver, usa a local (Docker/SQL Server)
# IMPORTANTE: No Render, a variável costuma vir como 'postgres://', mas o SQLAlchemy precisa de 'postgresql+asyncpg://'
DATABASE_URL = os.getenv("postgresql://neondb_owner:SuaSenha@ep-late-credit.../neondb?sslmode=require", "mssql+aioodbc://sa:Str0ngP@ssword!@localhost:1433/master?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes")

# Correção para o Render (bug conhecido do SQLAlchemy com URLs antigas do Postgres)
if DATABASE_URL.startswith("postgres://"):
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