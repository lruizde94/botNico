import asyncio
import random
import ccxt.async_support as ccxt
import aiohttp
from aiohttp import TCPConnector, DefaultResolver
import requests
from transformers import pipeline
from py_clob_client.client import ClobClient
from datetime import datetime

# --- CONFIGURACIÓN DE TUS CLAVES ---
POLYGON_RPC = "https://polygon-mainnet.g.alchemy.com/v2/yG7wv2t0LidDL84QqqKLP"
CRYPTO_PANIC_KEY = "f4b6509b7797dbc7179d84b45349f81877c46e65"
CRYPTO_PANIC_URL = "https://cryptopanic.com/api/v1/posts/"

class FranceBotPoC:
    def __init__(self):
        print("🚀 Iniciando Proyecto France (Modo PoC: Alchemy + CryptoPanic)...")
        
        # 1. Motor de IA (Sentimiento)
        # Con 8 cores, esto debería cargar rápido tras la primera descarga.
        print("🧠 Cargando Modelo de IA (esto tarda un poco la primera vez)...")
        self.sentiment_pipe = pipeline("text-classification", model="mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis")
        
        # 2. Conexión Binance (Precio Spot)
        self.exchange = ccxt.binance()
        
        # 3. Cliente Polymarket (Lectura)
        self.poly_client = ClobClient(host="https://clob.polymarket.com", key="", chain_id=137)
        
        # Estado interno para no repetir noticias
        self.last_processed_news_id = None

    async def get_btc_price(self):
        """Obtiene precio real de BTC en Binance con tus fallbacks robustos."""
        # Intento 1: CCXT (Async)
        try:
            ticker = await self.exchange.fetch_ticker('BTC/USDT')
            return ticker['last'], False
        except Exception:
            pass 

        # Intento 2: HTTP Directo (Requests síncrono como fallback seguro)
        try:
            def fetch_price_sync():
                response = requests.get('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT', timeout=5)
                return float(response.json()['price'])
            
            price = await asyncio.to_thread(fetch_price_sync)
            return price, False
        except Exception:
            pass

        # Intento 3: Simulación (Último recurso)
        simulated = round(random.uniform(90000.0, 105000.0), 2)
        return simulated, True

    async def fetch_latest_news(self):
        """Consulta CryptoPanic usando TU CLAVE."""
        params = {
            "auth_token": CRYPTO_PANIC_KEY,
            "currencies": "BTC",
            "filter": "important", # Filtramos solo noticias importantes para menos ruido
            "kind": "news"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(CRYPTO_PANIC_URL, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get('results', [])
                        
                        if not results:
                            return None

                        latest_news = results[0]
                        news_id = latest_news['id']
                        title = latest_news['title']

                        # Evitar repetir la misma noticia
                        if self.last_processed_news_id != news_id:
                            self.last_processed_news_id = news_id
                            return title
                        return None
                    else:
                        print(f"[API Error] CryptoPanic: {resp.status}")
                        return None
        except Exception as e:
            print(f"[Error Red] CryptoPanic (async): {e}")
            # Intento síncrono como fallback (requests)
            try:
                def fetch_sync():
                    r = requests.get(CRYPTO_PANIC_URL, params=params, timeout=10)
                    if r.status_code != 200:
                        print(f"[API Error Sync] CryptoPanic: {r.status_code}")
                        return None
                    data = r.json()
                    results = data.get('results', [])
                    if not results:
                        return None
                    latest_news = results[0]
                    return latest_news.get('id'), latest_news.get('title')

                res = await asyncio.to_thread(fetch_sync)
                if not res:
                    return None
                news_id, title = res
                if self.last_processed_news_id != news_id:
                    self.last_processed_news_id = news_id
                    return title
                return None
            except Exception as e2:
                print(f"[Error Red] CryptoPanic (sync): {e2}")
                return None

    async def analyze_sentiment(self, text):
        # Ejecutar IA en hilo separado para no bloquear
        result = await asyncio.to_thread(self.sentiment_pipe, text)
        return result[0]['label'], result[0]['score']

    async def check_opportunity(self, news_text):
        btc_price, simulated = await self.get_btc_price()
        sentiment, confidence = await self.analyze_sentiment(news_text)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] 📰 NUEVA NOTICIA DETECTADA")
        print(f"   Titular: '{news_text}'")
        if simulated:
            print(f"   📉 Precio BTC: ${btc_price} (Simulado - Error de conexión)")
        else:
            print(f"   📉 Precio BTC: ${btc_price} (Binance Real)")
        print(f"   🧠 IA: {sentiment.upper()} (Confianza: {confidence:.2f})")

        # LÓGICA DE TRADING
        if sentiment == 'negative' and confidence > 0.85:
            print("   👉 DECISIÓN: 🔴 Venta Fuerte (Bearish)")
        elif sentiment == 'positive' and confidence > 0.85:
            print("   👉 DECISIÓN: 🟢 Compra Fuerte (Bullish)")
        else:
            print("   👉 DECISIÓN: ⚪ Ignorar (Confianza baja/Neutral)")

    async def close(self):
        await self.exchange.close()
        # Allow underlying transports to close gracefully
        await asyncio.sleep(0.25)

async def main():
    bot = FranceBotPoC()
    print("\n📡 CONECTADO. Escuchando noticias de Bitcoin (Intervalo: 60s)...")
    print("   (Presiona Ctrl+C para salir)")

    try:
        while True:
            # 1. Buscar noticia
            latest_news = await bot.fetch_latest_news()
            
            # 2. Si hay noticia nueva, analizarla
            if latest_news:
                await bot.check_opportunity(latest_news)
            else:
                # Feedback visual pequeño
                print(".", end="", flush=True)

            # 3. Esperar 60 segundos
            await asyncio.sleep(60)

    except KeyboardInterrupt:
        print("\nDeteniendo bot...")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())