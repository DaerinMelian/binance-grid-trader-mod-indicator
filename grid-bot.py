"""Compounding grid trading bot with EMA/StochRSI/ATR gating.

Cycle:
  1) Place SELL limit at last_price * (1 + sell_pct)
     (allowed only if EMA20>EMA50 and StochRSI_K>0.8 when USE_INDICATORS).
  2) After SELL filled, place BUY limit at sell_fill_price * (1 - buy_pct).
  3) Buy with ALL net proceeds (compounding). Repeat.

Optional: dynamic step from ATR (step_pct = clamp(ATR_K * ATR/close, STEP_MIN, STEP_MAX)).
"""

import time
import math
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException
import config as C
from indicators import ema, atr, stoch_rsi

# ---------------- Binance helpers ----------------

client = Client(C.API_KEY, C.API_SECRET)
if C.USE_TESTNET:
    client.API_URL = 'https://testnet.binance.vision/api'

def get_symbol_filters(symbol):
    info = client.get_symbol_info(symbol)
    f = {x['filterType']: x for x in info['filters']}
    tick = float(f['PRICE_FILTER']['tickSize'])
    step = float(f['LOT_SIZE']['stepSize'])
    min_notional = float(f.get('NOTIONAL', {}).get('minNotional', 0.0) or
                         f.get('MIN_NOTIONAL', {}).get('minNotional', 0.0) or 10.0)
    return tick, step, min_notional

TICK_SIZE, STEP_SIZE, MIN_NOTIONAL = get_symbol_filters(C.SYMBOL)

def round_price(p):
    return math.floor(p / TICK_SIZE) * TICK_SIZE

def round_qty(q):
    # округлення вниз до кроку лота
    precision = int(round(-math.log10(STEP_SIZE)))
    return float(math.floor(q / STEP_SIZE) * STEP_SIZE)

def last_price():
    return float(client.get_symbol_ticker(symbol=C.SYMBOL)['price'])

def klines_df(limit=500) -> pd.DataFrame:
    k = client.get_klines(symbol=C.SYMBOL, interval=C.INTERVAL, limit=limit)
    df = pd.DataFrame(k, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","qav","trades","tb_base","tb_quote","ignore"
    ])
    df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df.set_index('open_time', inplace=True)
    return df

# ---------------- Indicators/Signals ----------------

def with_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['EMA20'] = ema(df['close'], C.EMA_FAST)
    df['EMA50'] = ema(df['close'], C.EMA_SLOW)
    df['ATR']   = atr(df, C.ATR_PERIOD)
    k, d = stoch_rsi(df['close'], C.RSI_PERIOD, C.STOCH_PERIOD, C.K_SMOOTH, C.D_SMOOTH)
    df['K'], df['D'] = k, d
    return df.dropna().copy()

def trend_ok(row) -> bool:
    return row['EMA20'] > row['EMA50']

def step_pct_from_atr(row_close, row_atr):
    raw = C.ATR_K * (row_atr / row_close)
    return max(C.STEP_MIN, min(C.STEP_MAX, float(raw)))

def allow_sell(row) -> bool:
    if not C.USE_INDICATORS:
        return True
    if not trend_ok(row):
        return False
    # Перепроданість/перекупленість за StochRSI: продаємо лише коли високо
    k = float(row['K'])
    return k > C.STOCH_ENTRY_K

# ---------------- Orders/Execution ----------------

def place_limit(side, price, qty):
    price = round_price(price)
    qty   = round_qty(qty)
    notional = price * qty
    if notional < MIN_NOTIONAL:
        raise ValueError(f"Notional too small: {notional} < {MIN_NOTIONAL}")
    try:
        return client.create_order(
            symbol=C.SYMBOL,
            side=side,
            type=Client.ORDER_TYPE_LIMIT,
            timeInForce=Client.TIME_IN_FORCE_GTC,
            quantity=str(qty),
            price=str(price)
        )
    except BinanceAPIException as e:
        raise RuntimeError(f"Binance error: {e.message}") from e

def wait_fill(order_id, poll=2):
    while True:
        o = client.get_order(symbol=C.SYMBOL, orderId=order_id)
        if o['status'] == 'FILLED':
            return float(o['price']), float(o['executedQty'])
        time.sleep(poll)

# ---------------- Main cycle ----------------

def compounding_cycle(base_qty):
    """
    base_qty: скільки базового активу ми продаємо на старті циклу.
    Після SELL ? BUY купуємо на всю чисту виручку; нова кількість повертається.
    """
    # 1) Визначаємо крок відсотків
    df = with_indicators(klines_df())
    row = df.iloc[-1]
    if C.USE_ATR_DYNAMIC_STEP:
        sell_pct = buy_pct = step_pct_from_atr(row['close'], row['ATR'])
    else:
        sell_pct, buy_pct = C.SELL_PERCENT, C.BUY_PERCENT

    # 2) Дозвіл на SELL за індикаторами
    if not allow_sell(row):
        # якщо ринок не підходить — чекаємо наступну свічку
        time.sleep(C.POLL_SEC)
        return base_qty

    # 3) SELL
    lp = last_price()
    sell_price = lp * (1.0 + sell_pct)
    sell_order = place_limit(Client.SIDE_SELL, sell_price, base_qty)
    fill_price_sell, filled_qty_sell = wait_fill(sell_order['orderId'])

    # net proceeds після комісії (припускаємо maker)
    net_quote = fill_price_sell * filled_qty_sell * (1.0 - C.MAKER_FEE)

    # 4) BUY на нижчому рівні
    buy_price = fill_price_sell * (1.0 - buy_pct)
    qty_to_buy = (net_quote * (1.0 - C.MAKER_FEE)) / buy_price  # ще раз врахуємо комісію на купівлю
    buy_order = place_limit(Client.SIDE_BUY, buy_price, qty_to_buy)
    fill_price_buy, filled_qty_buy = wait_fill(buy_order['orderId'])

    # 5) Нова базова кількість (компаундинг)
    new_base_qty = filled_qty_buy

    # опційний лог
    print(f"[CYCLE] sold {filled_qty_sell:.8f} @ {fill_price_sell:.2f} ? bought {filled_qty_buy:.8f} @ {fill_price_buy:.2f}  | ?qty={new_base_qty - base_qty:.8f}")
    return new_base_qty

def run_bot():
    qty = C.BASE_ORDER_SIZE
    while True:
        try:
            qty = compounding_cycle(qty)
        except Exception as e:
            print("ERROR:", e)
            time.sleep(3)
        time.sleep(C.POLL_SEC)

if __name__ == "__main__":
    run_bot()
