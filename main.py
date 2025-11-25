import os
import json
import asyncio # <--- Importante para o tempo de espera
import redis.asyncio as redis
from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


# Importações dos seus arquivos
from database import engine, Base, get_db, AsyncSessionLocal
from models import Feed, NewsItem
from services import update_feeds

app = FastAPI(title="Hardware Sniper Bot")

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(redis_url, decode_responses=True)

# --- FUNÇÃO DO LOOP AUTOMÁTICO ---
async def monitorar_automaticamente():
    """Roda infinitamente em background verificando preços a cada 5 minutos"""
    print("⏰ Monitoramento Automático INICIADO!")
    while True:
        try:
            # Cria uma nova sessão de banco apenas para essa verificação
            async with AsyncSessionLocal() as session:
                await update_feeds(session)
        except Exception as e:
            print(f"❌ Erro no monitoramento automático: {e}")
        
        # Espera 300 segundos (5 minutos) antes da próxima checagem
        # NÃO diminua muito isso para não ser bloqueado pelos sites (IP Ban)
        print("⏳ Aguardando 5 minutos para a próxima varredura...")
        await asyncio.sleep(300) 

@app.on_event("startup")
async def startup():
    # 1. Cria as tabelas do banco
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Inicia o robô automático em segundo plano
    asyncio.create_task(monitorar_automaticamente())

# --- ROTAS NORMAIS DA API (Opcionais agora, já que é automático) ---

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
    
    cached_news = await redis_client.get(cache_key)
    if cached_news:
        return {"source": "redis", "filter": busca, "data": json.loads(cached_news)}

    query = select(NewsItem).order_by(NewsItem.published_at.desc()).limit(20)
    if busca:
        query = query.where(NewsItem.title.contains(busca))

    result = await db.execute(query)
    news = result.scalars().all()
    news_data = [{"id": n.id, "title": n.title, "link": n.link} for n in news]

    if news_data:
        await redis_client.set(cache_key, json.dumps(news_data), ex=60)

    return {"source": "sql_server", "filter": busca, "data": news_data}

@app.post("/force-update/")
async def forcar_atualizacao(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Para quando você está ansioso e não quer esperar 5 minutos"""
    await redis_client.delete("latest_news")
    background_tasks.add_task(update_feeds, db)
    return {"message": "Atualização forçada iniciada!"}