import json
import asyncio
import os
import redis.asyncio as redis
from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import engine, Base, get_db, AsyncSessionLocal
from models import Feed, NewsItem
from services import update_feeds

app = FastAPI(title="Hardware Sniper Bot")

# Configuração Segura do Redis
# Se não tiver variável REDIS_URL, tenta localhost.
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
try:
    redis_client = redis.from_url(redis_url, decode_responses=True)
except:
    redis_client = None # Roda sem cache se o Redis falhar

# --- LOOP AUTOMÁTICO ---
async def monitorar_automaticamente():
    print("⏰ Monitoramento Automático INICIADO!")
    while True:
        try:
            async with AsyncSessionLocal() as session:
                await update_feeds(session)
        except Exception as e:
            print(f"❌ Erro no loop: {e}")
        
        # Espera 5 minutos (300 segundos)
        await asyncio.sleep(300)

@app.on_event("startup")
async def startup():
    # Cria tabelas no banco (Postgres ou SQL Server)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Inicia o robô
    asyncio.create_task(monitorar_automaticamente())

@app.post("/feeds/")
async def adicionar_feed(url: str, name: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    try:
        new_feed = Feed(url=url, name=name)
        db.add(new_feed)
        await db.commit()
        background_tasks.add_task(update_feeds, db)
        return {"message": "Feed adicionado!", "feed": name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/news/")
async def ler_noticias(busca: str = None, db: AsyncSession = Depends(get_db)):
    cache_key = f"news_{busca}" if busca else "news_geral"
    
    # Tenta Cache se o Redis estiver ativo
    if redis_client:
        try:
            cached_news = await redis_client.get(cache_key)
            if cached_news:
                return {"source": "redis", "filter": busca, "data": json.loads(cached_news)}
        except:
            pass # Ignora erro de redis

    query = select(NewsItem).order_by(NewsItem.published_at.desc()).limit(20)
    if busca:
        query = query.where(NewsItem.title.contains(busca))

    result = await db.execute(query)
    news = result.scalars().all()
    news_data = [{"id": n.id, "title": n.title, "link": n.link} for n in news]

    # Salva Cache se o Redis estiver ativo
    if redis_client and news_data:
        try:
            await redis_client.set(cache_key, json.dumps(news_data), ex=60)
        except:
            pass

    return {"source": "database", "filter": busca, "data": news_data}

@app.post("/force-update/")
async def forcar_atualizacao(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    if redis_client:
        try:
            await redis_client.delete("latest_news")
        except:
            pass
    background_tasks.add_task(update_feeds, db)
    return {"message": "Atualização forçada!"}