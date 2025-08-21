# config.py

# Binance API bilgilerin
API_KEY = "API KEY"
API_SECRET = "SECRET KEY"

# Grid stratejisi ayarları
# Botu başlatmak için kullanacağın sembol ve temel işlem miktarı
SYMBOL = "BTCUSDT"
BASE_ORDER_SIZE = 0.001  # İlk satış için BTC miktarı

# Grid yüzdeleri – satarken yüzde kaç yukarıdan, alırken yüzde kaç aşağıdan emir girileceği
SELL_PERCENT = 0.01  # Mevcut fiyattan %1 yukarıdan satış
BUY_PERCENT = 0.01   # Satış fiyatından %1 aşağıdan alış

# İndikatörler için kullanılacak mum aralığı
INTERVAL = "1h"

# Testnet kullanmak istersen:
USE_TESTNET = True
