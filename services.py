import feedparser
import asyncio
import httpx
from bs4 import BeautifulSoup  # Nova importação para achar imagens
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import Feed, NewsItem

# ---------------------------------------------------------
# CONFIGURAÇÃO DO DISCORD
# ---------------------------------------------------------
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1442718193662693438/pu30bsXfYWn8AdAVDq0VsmfA6nonyxUZYAIAxet1boBAJ79EqGkWaNooCeUwan4XpXMr"  # <--- COLE SEU LINK AQUI

# 🎯 SNIPER MODE:
# Removi "Promoção", "Oferta", "Black Friday".
# Agora ele só apita se for O NOME DA PEÇA.
KEYWORDS = [
    # NVIDIA
    "RTX 4060", "RTX 4070", "RTX 4080", "RTX 4090", "RTX 50", 
    
    # AMD
    "RX 6600", "RX 6750", "RX 7600", "RX 7700", "RX 7800",
    
    # PROCESSADORES
    "Ryzen 5 5600", "Ryzen 7 5700", "5800X3D", "7800X3D", "Ryzen 9",
    "Core i5", "Core i7", "Core i9",
    
    # PERIFÉRICOS / OUTROS
    "Monitor 144hz", "Monitor 165hz", "Monitor 240hz", "OLED", "QLED",
    "NVMe 1TB", "NVMe 2TB", "SSD 1TB", "SSD 2TB",
    "PS5", "Playstation 5", "Xbox Series",
    "Logitech", "Razer" # Marcas específicas costumam filtrar lixo
]
# ---------------------------------------------------------

def parse_feed_sync(url: str):
    return feedparser.parse(url)

def extrair_imagem(entry):
    """
    Tenta encontrar uma imagem no feed de 3 formas diferentes:
    1. Tags de media (padrão RSS moderno)
    2. Tags de enclosure (padrão Podcast)
    3. Raspagem do HTML da descrição (padrão Gatry/Pelando)
    """
    # Tentativa 1: Media Content (comum em sites de notícias)
    if hasattr(entry, 'media_content'):
        return entry.media_content[0]['url']
    
    # Tentativa 2: Links de imagem (Enclosures)
    if hasattr(entry, 'links'):
        for link in entry.links:
            if link.type.startswith('image/'):
                return link.href
                
    # Tentativa 3: Buscar dentro do HTML (Gatry/Pelando usam isso)
    if hasattr(entry, 'summary'):
        soup = BeautifulSoup(entry.summary, 'lxml')
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            return img_tag['src']
            
    # Se não achar nada, retorna None (sem imagem)
    return None

async def send_discord_alert(title: str, link: str, image_url: str = None):
    if not DISCORD_WEBHOOK_URL.startswith("http"):
        return

    # Monta o Embed (Cartão Visual)
    embed = {
        "title": "🔥 Alerta!",
        "description": f"**{title}**",
        "url": link,
        "color": 5763719, # Cor Verde Matrix
        "footer": {"text": "Sniper Bot • Monitorando Preços"},
    }

    # Se achamos imagem, adiciona ao embed
    if image_url:
        embed["image"] = {"url": image_url}

    payload = {
        "username": "Bot promos e noticias",
        "embeds": [embed]
    }

    async with httpx.AsyncClient() as client:
        try:
            await client.post(DISCORD_WEBHOOK_URL, json=payload)
            print(f"🔔 Alerta visual enviado: {title[:30]}...")
        except Exception as e:
            print(f"❌ Erro Discord: {e}")

async def update_feeds(db: AsyncSession):
    print("🔄 Buscando promoções...")
    
    result = await db.execute(select(Feed))
    feeds = result.scalars().all()

    for feed in feeds:
        loop = asyncio.get_event_loop()
        feed_data = await loop.run_in_executor(None, parse_feed_sync, feed.url)

        added_count = 0
        for entry in feed_data.entries:
            exists = await db.execute(select(NewsItem).where(NewsItem.link == entry.link))
            if not exists.scalars().first():
                # Salva no banco
                new_news = NewsItem(
                    title=entry.title[:250],
                    link=entry.link,
                    feed_id=feed.id
                )
                db.add(new_news)
                added_count += 1
                
                # --- LÓGICA DO SNIPER ---
                title_lower = entry.title.lower()
                
                # Só passa se tiver a palavra exata (ex: "4060", "Ryzen")
                if any(k.lower() in title_lower for k in KEYWORDS):
                    # Extrai a imagem antes de mandar
                    img_url = extrair_imagem(entry)
                    await send_discord_alert(entry.title, entry.link, img_url)
        
        if added_count > 0:
            print(f"✅ {feed.name}: {added_count} novos itens verificados.")

    await db.commit()