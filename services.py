import feedparser
import asyncio
import httpx
from bs4 import BeautifulSoup 
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import Feed, NewsItem

# ---------------------------------------------------------
# ⚠️ COLOQUE SEU WEBHOOK AQUI ANTES DE SALVAR
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1442718193662693438/pu30bsXfYWn8AdAVDq0VsmfA6nonyxUZYAIAxet1boBAJ79EqGkWaNooCeUwan4XpXMr" 
# ---------------------------------------------------------

KEYWORDS = [
    "RTX", "4060", "4070", "4080", "4090", "RX 6600", "RX 7600", 
    "Ryzen 5", "Ryzen 7", "5700X", "5800X3D", "7800X3D",
    "Core i5", "Core i7", "SSD", "NVMe", "Monitor", "144hz", 
    "Promoção", "Bug", "Cupom"
]

def parse_feed_sync(url: str):
    return feedparser.parse(url)

def extrair_imagem(entry):
    if hasattr(entry, 'media_content'):
        return entry.media_content[0]['url']
    if hasattr(entry, 'links'):
        for link in entry.links:
            if link.type.startswith('image/'):
                return link.href
    if hasattr(entry, 'summary'):
        soup = BeautifulSoup(entry.summary, 'lxml')
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            return img_tag['src']
    return None

async def send_discord_alert(title: str, link: str, image_url: str = None):
    if not DISCORD_WEBHOOK_URL.startswith("http"):
        return

    embed = {
        "title": "🔥 Alerta Sniper!",
        "description": f"**{title}**",
        "url": link,
        "color": 5763719,
        "footer": {"text": "Monitorando Preços 24/7"},
    }
    if image_url:
        embed["image"] = {"url": image_url}

    payload = {"username": "Hardware Sniper", "embeds": [embed]}

    async with httpx.AsyncClient() as client:
        try:
            await client.post(DISCORD_WEBHOOK_URL, json=payload)
            print(f"🔔 Alerta enviado: {title[:20]}...")
        except Exception as e:
            print(f"❌ Erro Discord: {e}")

async def update_feeds(db: AsyncSession):
    print("🔄 Verificando Feeds...")
    result = await db.execute(select(Feed))
    feeds = result.scalars().all()

    for feed in feeds:
        loop = asyncio.get_event_loop()
        try:
            feed_data = await loop.run_in_executor(None, parse_feed_sync, feed.url)
            for entry in feed_data.entries:
                exists = await db.execute(select(NewsItem).where(NewsItem.link == entry.link))
                if not exists.scalars().first():
                    new_news = NewsItem(title=entry.title[:250], link=entry.link, feed_id=feed.id)
                    db.add(new_news)
                    
                    # Sniper Check
                    if any(k.lower() in entry.title.lower() for k in KEYWORDS):
                        img = extrair_imagem(entry)
                        await send_discord_alert(entry.title, entry.link, img)
        except Exception as e:
            print(f"Erro no feed {feed.url}: {e}")

    await db.commit()