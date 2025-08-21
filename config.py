# config.py

# --- API ---
API_KEY = "API KEY"
API_SECRET = "SECRET KEY"
USE_TESTNET = True

# --- Market / Symbol ---
SYMBOL = "BTCUSDT"
INTERVAL = "15m"  # для більш чутливих сигналів

# --- Base inventory (початковий обсяг базового активу) ---
BASE_ORDER_SIZE = 0.002  # стартова кількість для першого SELL

# --- Static grid deltas (у відсотках як частка) ---
SELL_PERCENT = 0.03   # +3% від поточної ціни (якщо не використовуємо ATR)
BUY_PERCENT  = 0.03   # -3% від ціни виконаного продажу

# --- Fees (оцінка, використовуйте maker-знижки/BNB якщо є) ---
MAKER_FEE = 0.0010   # 0.10%
TAKER_FEE = 0.0010   # 0.10%

# --- Indicators ---
USE_INDICATORS = True
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
STOCH_PERIOD = 14
K_SMOOTH = 3
D_SMOOTH = 3
STOCH_ENTRY_K = 0.80   # >0.8 дозволяємо SELL
STOCH_EXIT_K  = 0.20   # <0.2 можна забороняти SELL (не обов'язково)

ATR_PERIOD = 14
USE_ATR_DYNAMIC_STEP = True
ATR_K = 1.5         # множник для ATR/close
STEP_MIN = 0.01     # 1% мінімально (коли ATR дуже малий)
STEP_MAX = 0.05     # 5% максимально

# --- Compounding ---
REINVEST_THRESHOLD_QUOTE = 5.0  # поріг у котирувальній валюті для перерахунку розміру

# --- Housekeeping ---
POLL_SEC = 5