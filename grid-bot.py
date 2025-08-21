# grid_bot.py
import time
from decimal import Decimal

import pandas as pd
import numpy as np
from binance.client import Client

from config import (
    API_KEY,
    API_SECRET,
    SYMBOL,
    BASE_ORDER_SIZE,
    SELL_PERCENT,
    BUY_PERCENT,
    USE_TESTNET,
    INTERVAL,
)

client = Client(API_KEY, API_SECRET)
if USE_TESTNET:
    client.API_URL = "https://testnet.binance.vision/api"

# Sembol bilgilerini çekerek fiyat ve miktar adımlarını belirle
symbol_info = client.get_symbol_info(SYMBOL)
base_asset = symbol_info["baseAsset"]
quote_asset = symbol_info["quoteAsset"]
tick_size = next(f["tickSize"] for f in symbol_info["filters"] if f["filterType"] == "PRICE_FILTER")
step_size = next(f["stepSize"] for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE")


def round_step_size(quantity: float, step: str) -> float:
    step_dec = Decimal(step)
    return float((Decimal(str(quantity)) // step_dec) * step_dec)


def round_tick_size(price: float, tick: str) -> float:
    tick_dec = Decimal(tick)
    return float((Decimal(str(price)) // tick_dec) * tick_dec)


def fetch_klines() -> pd.DataFrame:
    klines = client.get_klines(symbol=SYMBOL, interval=INTERVAL, limit=100)
    df = pd.DataFrame(
        klines,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "qav",
            "trades",
            "tbbav",
            "tbqav",
            "ignore",
        ],
    )
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)

    # EMA20 ve EMA50
    df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()

    # ATR
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr = np.maximum.reduce([
        high - low,
        abs(high - close.shift()),
        abs(low - close.shift()),
    ])
    df["ATR"] = tr.rolling(window=14).mean()

    # Stochastic RSI
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.rolling(14).mean()
    roll_down = down.rolling(14).mean()
    rs = roll_up / roll_down
    rsi = 100 - (100 / (1 + rs))
    stochrsi = (rsi - rsi.rolling(14).min()) / (rsi.rolling(14).max() - rsi.rolling(14).min())
    df["StochRSI"] = stochrsi

    return df.dropna()


def wait_for_fill(order_id: int):
    while True:
        order = client.get_order(symbol=SYMBOL, orderId=order_id)
        if order["status"] == Client.ORDER_STATUS_FILLED:
            return order
        time.sleep(2)


def get_fills(order_id: int):
    trades = client.get_my_trades(symbol=SYMBOL, orderId=order_id)
    qty = sum(float(t["qty"]) for t in trades)
    quote_qty = sum(float(t["price"]) * float(t["qty"]) for t in trades)
    fee_in_quote = 0.0
    for t in trades:
        commission = float(t["commission"])
        if t["commissionAsset"] == quote_asset:
            fee_in_quote += commission
        else:
            fee_in_quote += commission * float(t["price"])
    return qty, quote_qty / qty, fee_in_quote


def compounding_cycle(quantity_to_sell: float) -> float:
    df = fetch_klines()
    last = df.iloc[-1]
    last_price = last["close"]
    print(
        f"Close: {last_price:.2f} | EMA20: {last['EMA20']:.2f} | EMA50: {last['EMA50']:.2f} "
        f"| ATR: {last['ATR']:.2f} | StochRSI: {last['StochRSI']:.2f}"
    )

    sell_price = round_tick_size(last_price * (1 + SELL_PERCENT), tick_size)
    sell_qty = round_step_size(quantity_to_sell, step_size)
    sell_order = client.order_limit_sell(symbol=SYMBOL, quantity=sell_qty, price=str(sell_price))
    print(f"SELL {sell_qty} {base_asset} @ {sell_price}")
    wait_for_fill(sell_order["orderId"])

    filled_qty, exec_price, fee_in_quote = get_fills(sell_order["orderId"])
    q_received = filled_qty * exec_price - fee_in_quote

    buy_price = round_tick_size(exec_price * (1 - BUY_PERCENT), tick_size)
    amount_to_buy = q_received / buy_price
    amount_to_buy = round_step_size(amount_to_buy, step_size)

    buy_order = client.order_limit_buy(symbol=SYMBOL, quantity=amount_to_buy, price=str(buy_price))
    print(f"BUY {amount_to_buy} {base_asset} @ {buy_price}")
    wait_for_fill(buy_order["orderId"])

    return amount_to_buy


def run_bot():
    quantity = BASE_ORDER_SIZE
    while True:
        quantity = compounding_cycle(quantity)
        time.sleep(5)


if __name__ == "__main__":
    run_bot()
