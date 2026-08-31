import os
import time
import json
import datetime as dt
from zoneinfo import ZoneInfo
import requests
import pandas as pd

# ================= Telegram Config =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise SystemExit("ERROR: Set BOT_TOKEN and CHAT_ID environment variables before running.")

session = requests.Session()
IST = ZoneInfo("Asia/Kolkata")

def send_telegram_msg(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        session.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

# ================= Direct Yahoo Finance Fetch =================
def fetch_yahoo_direct(symbol, interval, range_):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": interval, "range": range_}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = session.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        result = data["chart"]["result"][0]
        ts = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        df = pd.DataFrame({
            "Open": quote["open"],
            "High": quote["high"],
            "Low": quote["low"],
            "Close": quote["close"],
            "Volume": quote["volume"],
        }, index=pd.to_datetime(ts, unit="s", utc=True).tz_convert(IST))
        return df.dropna()
    except Exception as e:
        print(f"Fetch Error [{symbol} {interval}]: {e}")
        return pd.DataFrame()

# ================= Order Flow (Angel One Depth) =================
DEPTH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "depth_data.json")

def get_order_flow_bias(symbol):
    nse_name = symbol.replace(".NS", "")
    if not os.path.exists(DEPTH_FILE):
        return None
    try:
        with open(DEPTH_FILE) as f:
            depth = json.load(f)
        entry = depth.get(nse_name)
        if not entry or time.time() - entry.get("updated", 0) > 120:
            return None
        imbalance = entry.get("imbalance", 0)
        if imbalance > 0.1:
            return "bullish"
        elif imbalance < -0.1:
            return "bearish"
        return "neutral"
    except Exception:
        return None

# ================= Market Hours Helper =================
def is_nse_market_open():
    """Mon-Fri, 9:15 AM to 3:30 PM IST"""
    now = dt.datetime.now(IST)
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close

def is_crypto_symbol(symbol):
    return symbol.endswith("-USD")

# ================= Symbols & Timeframes =================
SYMBOLS = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD",
    "^NSEI", "^NSEBANK", "RELIANCE.NS", "TCS.NS", "INFY.NS"
]
TIMEFRAMES = ["5m", "1h", "2h", "4h"]

# ================= Persistent State =================
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_state.json")

def save_state():
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(demo_accounts, f, indent=2)
    except Exception as e:
        print(f"Save State Error: {e}")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception as e:
            print(f"Load State Error: {e}")
    return None

demo_accounts = load_state()
if demo_accounts is None:
    demo_accounts = {}
    for i in range(1, 31):
        tf = "5m" if i <= 8 else ("1h" if i <= 16 else ("2h" if i <= 23 else "4h"))
        demo_accounts[f"DEMO_{i:02d}"] = {"tf": tf, "balance": 100000.0, "active_trade": None}
    save_state()

# ================= Technical & SMC Indicators =================
def compute_indicators(df):
    if df.empty or len(df) < 15:
        return df
    high_low = df['High'] - df['Low']
    high_cp = (df['High'] - df['Close'].shift(1)).abs()
    low_cp = (df['Low'] - df['Close'].shift(1)).abs()
    df['TR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()

    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    tp_vol = df['Volume'] * typical_price
    day_key = df.index.date
    df['VWAP'] = tp_vol.groupby(day_key).cumsum() / df['Volume'].groupby(day_key).cumsum().replace(0, 1)

    signed_vol = df['Volume'].where(df['Close'] >= df['Open'], -df['Volume'])
    df['CVD'] = signed_vol.groupby(day_key).cumsum()
    return df

def compute_delta_approx(df, lookback=10):
    if len(df) < lookback:
        return 0, "neutral"
    recent = df.iloc[-lookback:]
    buy_vol = recent.loc[recent['Close'] >= recent['Open'], 'Volume'].sum()
    sell_vol = recent.loc[recent['Close'] < recent['Open'], 'Volume'].sum()
    delta = buy_vol - sell_vol
    return delta, ("bullish" if delta > 0 else "bearish" if delta < 0 else "neutral")

def detect_fvg(df):
    """Fair Value Gap in last 3 candles"""
    if len(df) < 3:
        return None
    c1, c3 = df.iloc[-3], df.iloc[-1]
    if c1['High'] < c3['Low']:
        return "bullish"
    elif c1['Low'] > c3['High']:
        return "bearish"
    return None

def detect_order_block(df, lookback=10):
    """Order Block: Last opposite candle before strong impulse move"""
    if len(df) < lookback + 2:
        return None
    recent = df.iloc[-lookback:]
    last_candle = recent.iloc[-1]
    
    # Bullish OB: Strong green candle breaking recent high after red candle
    if last_candle['Close'] > last_candle['Open'] and (last_candle['Close'] - last_candle['Open']) > (last_candle['High'] - last_candle['Low']) * 0.6:
        red_candles = recent[recent['Close'] < recent['Open']]
        if not red_candles.empty:
            return "bullish"
            
    # Bearish OB: Strong red candle breaking recent low after green candle
    elif last_candle['Close'] < last_candle['Open'] and (last_candle['Open'] - last_candle['Close']) > (last_candle['High'] - last_candle['Low']) * 0.6:
        green_candles = recent[recent['Close'] > recent['Open']]
        if not green_candles.empty:
            return "bearish"
            
    return None

def detect_breaker_block(df, lookback=10):
    """Breaker block: Market Structure Break of swing high/low"""
    if len(df) < lookback + 2:
        return None
    recent = df.iloc[-lookback:]
    swing_high = recent['High'].iloc[:-2].max()
    swing_low = recent['Low'].iloc[:-2].min()
    last_close, prev_close = df['Close'].iloc[-1], df['Close'].iloc[-2]

    if prev_close <= swing_high and last_close > swing_high:
        return "bullish"
    elif prev_close >= swing_low and last_close < swing_low:
        return "bearish"
    return None

# ================= Alert Formatters =================
def send_main_trade_box(acc_id, symbol, side, entry, sl, tp1, tp2, rr, tf, smc_confluence):
    border = "🟩" if "BUY" in side or "LONG" in side else "🟥"
    msg = f"""
{border}━━━━━━━━━━━━━━━━━━━━━━{border}
*LUCKY TRADING - SMC CONFLUENCE*
{border}━━━━━━━━━━━━━━━━━━━━━━{border}
📌 *Account:* `{acc_id}` | *TF:* `{tf}`
🏷 *Symbol:* `{symbol}`
⚡ *Action:* *{side}*
🎯 *Entry:* `{entry:.2f}`
🛑 *SL:* `{sl:.2f}`
🎯 *TP1:* `{tp1:.2f}` | *TP2:* `{tp2:.2f}`
⚖ *R:R:* `1:{rr:.2f}`
🧬 *SMC Signals:* `{smc_confluence}`
📊 *System:* Daya SMC Engine
{border}━━━━━━━━━━━━━━━━━━━━━━{border}
"""
    send_telegram_msg(msg)

def send_pnl_box(acc_id, symbol, result_type, exit_price, pnl, new_bal):
    icon = "💰" if pnl >= 0 else "🛑"
    status_bar = "🟢 PROFIT HIT 🟢" if pnl >= 0 else "🔴 STOP LOSS HIT 🔴"
    msg = f"""
┌──────────────────────┐
│ {status_bar} │
└──────────────────────┘
📦 *Account:* `{acc_id}`
🏷 *Symbol:* `{symbol}`
{icon} *Status:* *{result_type}*
🏁 *Exit Price:* `{exit_price:.2f}`
💵 *Realized P&L:* `${pnl:+.2f}`
💼 *Updated Balance:* `${new_bal:,.2f}`
────────────────────────
"""
    send_telegram_msg(msg)

# ================= Core Engine Loop =================
def run_scanner():
    print("🦁 Daya SMC Complete Engine Started...")
    while True:
        try:
            for symbol in SYMBOLS:
                if not is_crypto_symbol(symbol) and not is_nse_market_open():
                    continue

                for tf in TIMEFRAMES:
                    fetch_tf = "1h" if tf in ("2h", "4h") else tf
                    period_val = "5d" if tf == "5m" else "30d"

                    df = fetch_yahoo_direct(symbol, fetch_tf, period_val)
                    if df.empty or len(df) < 15:
                        continue

                    if tf in ("2h", "4h"):
                        df = df.resample(tf).agg({
                            'Open': 'first', 'High': 'max',
                            'Low': 'min', 'Close': 'last', 'Volume': 'sum'
                        }).dropna()

                    df = compute_indicators(df)
                    if df.empty or len(df) < 3:
                        continue

                    c_close = float(df['Close'].iloc[-1])
                    p_close = float(df['Close'].iloc[-2])
                    c_vwap = float(df['VWAP'].iloc[-1])
                    p_vwap = float(df['VWAP'].iloc[-2])
                    atr_val = float(df['ATR'].iloc[-1]) if not pd.isna(df['ATR'].iloc[-1]) else (c_close * 0.01)
                    min_move = 0.3 * atr_val

                    delta_val, delta_dir = compute_delta_approx(df)
                    cvd_rising = float(df['CVD'].iloc[-1]) > float(df['CVD'].iloc[-2])

                    # SMC Detections
                    fvg_bias = detect_fvg(df)
                    ob_bias = detect_order_block(df)
                    breaker_bias = detect_breaker_block(df)
                    of_bias = get_order_flow_bias(symbol)

                    # SMC Scores
                    smc_bull_signals = [s for s in [fvg_bias, ob_bias, breaker_bias] if s == "bullish"]
                    smc_bear_signals = [s for s in [fvg_bias, ob_bias, breaker_bias] if s == "bearish"]

                    vwap_bullish = (p_close <= p_vwap) and (c_close > c_vwap) and ((c_close - c_vwap) >= min_move)
                    vwap_bearish = (p_close >= p_vwap) and (c_close < c_vwap) and ((c_vwap - c_close) >= min_move)

                    # Entry Rules (Buy / Sell Confluence)
                    g_buy = vwap_bullish and (delta_dir == "bullish") and cvd_rising and (len(smc_bull_signals) >= 1)
                    r_buy = vwap_bearish and (delta_dir == "bearish") and (not cvd_rising) and (len(smc_bear_signals) >= 1)

                    if of_bias is not None:
                        g_buy = g_buy and (of_bias != "bearish")
                        r_buy = r_buy and (of_bias != "bullish")

                    g_exit = (p_close >= p_vwap) and (c_close < c_vwap)
                    r_exit = (p_close <= p_vwap) and (c_close > c_vwap)

                    for acc_id, acc in demo_accounts.items():
                        if acc["tf"] != tf:
                            continue
                        trade = acc["active_trade"]

                        if trade and trade["symbol"] == symbol:
                            if trade["side"] == "LONG":
                                if c_close >= trade["tp2"]:
                                    pnl = (trade["tp2"] - trade["entry"]) * trade["qty"]
                                    acc["balance"] += pnl
                                    send_pnl_box(acc_id, symbol, "TP2 HIT", trade["tp2"], pnl, acc["balance"])
                                    acc["active_trade"] = None
                                    save_state()
                                elif c_close >= trade["tp1"] and not trade["tp1_hit"]:
                                    trade["tp1_hit"] = True
                                    send_telegram_msg(f"🔹 *[{acc_id}]* `{symbol}` TP1 Reached! Holding for TP2.")
                                elif c_close <= trade["sl"] or g_exit:
                                    pnl = (c_close - trade["entry"]) * trade["qty"]
                                    acc["balance"] += pnl
                                    reason = "G.EXIT (Cross Down)" if g_exit else "SL HIT"
                                    send_pnl_box(acc_id, symbol, reason, c_close, pnl, acc["balance"])
                                    acc["active_trade"] = None
                                    save_state()

                            elif trade["side"] == "SHORT":
                                if c_close <= trade["tp2"]:
                                    pnl = (trade["entry"] - trade["tp2"]) * trade["qty"]
                                    acc["balance"] += pnl
                                    send_pnl_box(acc_id, symbol, "TP2 HIT", trade["tp2"], pnl, acc["balance"])
                                    acc["active_trade"] = None
                                    save_state()
                                elif c_close <= trade["tp1"] and not trade["tp1_hit"]:
                                    trade["tp1_hit"] = True
                                    send_telegram_msg(f"🔹 *[{acc_id}]* `{symbol}` TP1 Reached! Holding for TP2.")
                                elif c_close >= trade["sl"] or r_exit:
                                    pnl = (trade["entry"] - c_close) * trade["qty"]
                                    acc["balance"] += pnl
                                    reason = "R.EXIT (Cross Up)" if r_exit else "SL HIT"
                                    send_pnl_box(acc_id, symbol, reason, c_close, pnl, acc["balance"])
                                    acc["active_trade"] = None
                                    save_state()

                        elif not trade:
                            confluence_tag = f"FVG:{fvg_bias} | OB:{ob_bias} | BRK:{breaker_bias}"
                            if g_buy:
                                entry = c_close
                                sl = entry - (1.5 * atr_val)
                                tp1 = entry + (2.0 * atr_val)
                                tp2 = entry + (3.5 * atr_val)
                                risk = max(entry - sl, 0.01)
                                qty = round((acc["balance"] * 0.01) / risk, 4)
                                acc["active_trade"] = {
                                    "symbol": symbol, "side": "LONG", "entry": entry,
                                    "sl": sl, "tp1": tp1, "tp2": tp2, "qty": qty, "tp1_hit": False
                                }
                                send_main_trade_box(acc_id, symbol, "BUY", entry, sl, tp1, tp2, 2.0, tf, confluence_tag)
                                save_state()

                            elif r_buy:
                                entry = c_close
                                sl = entry + (1.5 * atr_val)
                                tp1 = entry - (2.0 * atr_val)
                                tp2 = entry - (3.5 * atr_val)
                                risk = max(sl - entry, 0.01)
                                qty = round((acc["balance"] * 0.01) / risk, 4)
                                acc["active_trade"] = {
                                    "symbol": symbol, "side": "SHORT", "entry": entry,
                                    "sl": sl, "tp1": tp1, "tp2": tp2, "qty": qty, "tp1_hit": False
                                }
                                send_main_trade_box(acc_id, symbol, "SELL", entry, sl, tp1, tp2, 2.0, tf, confluence_tag)
                                save_state()

            time.sleep(300)
        except Exception as err:
            print(f"Cycle Error: {err}")
            time.sleep(10)

if __name__ == "__main__":
    send_telegram_msg("🚀 *Daya SMC Complete Bot Initialized!*\nOB + FVG + Breaker Block + VWAP Integrated.")
    run_scanner()
