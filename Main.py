import os
import time
import datetime
import threading
import pyotp
import requests
import pandas as pd
import numpy as np
from flask import Flask
from SmartApi import SmartConnect

# ==========================================
# 1. FLASK WEB SERVER (FOR RENDER & UPTIMEROBOT)
# ==========================================
app = Flask(__name__)

@app.route('/')
def health_check():
    return "ICT/SMC Multi-Timeframe Order Flow Algo Bot is Active 24/7 on Render!"

# ==========================================
# 2. CREDENTIALS & CONFIGURATION
# ==========================================
CLIENT_ID = os.getenv("ANGEL_CLIENT_ID", "AAAE383027")
MPIN = os.getenv("ANGEL_MPIN", "2222")
API_KEY = os.getenv("ANGEL_API_KEY", "5L3fPSxW")
TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET", "CV42EVYE6UNCQKEIZWEQHSIUZM")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ==========================================
# 3. AUTHENTICATION & TELEGRAM UTILITIES
# ==========================================
def get_angel_session():
    try:
        smart_api = SmartConnect(api_key=API_KEY)
        totp = pyotp.TOTP(TOTP_SECRET).now()
        data = smart_api.generateSession(CLIENT_ID, MPIN, totp)
        if data and data.get('status'):
            print("Angel One Session Connected Successfully.")
            return smart_api
        else:
            print(f"Login Failed: {data.get('message')}")
            return None
    except Exception as e:
        print(f"Auth Exception: {e}")
        return None

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[TELEGRAM LOG]:\n{message}\n")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as err:
        print(f"Telegram Dispatch Error: {err}")

# ==========================================
# 4. INDICATOR & ORDER FLOW CALCULATIONS
# ==========================================
def calculate_vwap(df):
    v = df['Volume'].values
    tp = (df['High'] + df['Low'] + df['Close']) / 3.0
    cum_vol = v.cumsum()
    cum_vol = np.where(cum_vol == 0, 1e-5, cum_vol)
    df['VWAP'] = (tp * v).cumsum() / cum_vol
    return df

def calculate_order_flow_delta(df):
    spread = (df['High'] - df['Low']).replace(0, 0.05)
    df['Buy_Vol'] = ((df['Close'] - df['Low']) / spread) * df['Volume']
    df['Sell_Vol'] = df['Volume'] - df['Buy_Vol']
    df['Delta'] = df['Buy_Vol'] - df['Sell_Vol']
    df['CVD'] = df['Delta'].cumsum()
    df['Vol_SMA'] = df['Volume'].rolling(window=20).mean().bfill()
    return df

def resample_to_4hr(df_1h):
    df = df_1h.copy()
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df.set_index('Timestamp', inplace=True)
    df_4h = df.resample('4h').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna().reset_index()
    return df_4h

# ==========================================
# 5. CORE MULTI-TIMEFRAME SMC / ICT ENGINE
# ==========================================
def analyze_market(obj, token="99926000", symbol="NIFTY 50", exchange="NSE"):
    now = datetime.datetime.now()
    from_date_5m = (now - datetime.timedelta(days=5)).strftime("%Y-%m-%d 09:15")
    from_date_1h = (now - datetime.timedelta(days=30)).strftime("%Y-%m-%d 09:15")
    from_date_1d = (now - datetime.timedelta(days=60)).strftime("%Y-%m-%d 09:15")
    to_date = now.strftime("%Y-%m-%d %H:%M")

    cols = ["Timestamp", "Open", "High", "Low", "Close", "Volume"]

    # 1. 5-Minute Execution Data
    res_5m = obj.getCandleData({
        "exchange": exchange,
        "symboltoken": token,
        "interval": "FIVE_MINUTE",
        "fromdate": from_date_5m,
        "todate": to_date
    })

    # 2. 1-Hour HTF Data
    res_1h = obj.getCandleData({
        "exchange": exchange,
        "symboltoken": token,
        "interval": "ONE_HOUR",
        "fromdate": from_date_1h,
        "todate": to_date
    })

    # 3. Daily Data (PDH, PDL, PWH, PWL)
    res_1d = obj.getCandleData({
        "exchange": exchange,
        "symboltoken": token,
        "interval": "ONE_DAY",
        "fromdate": from_date_1d,
        "todate": to_date
    })

    if not res_5m or not res_5m.get('data') or not res_1h or not res_1h.get('data') or not res_1d or not res_1d.get('data'):
        return

    df_5m = pd.DataFrame(res_5m['data'], columns=cols)
    df_5m[['Open', 'High', 'Low', 'Close', 'Volume']] = df_5m[['Open', 'High', 'Low', 'Close', 'Volume']].apply(pd.to_numeric)

    df_1h = pd.DataFrame(res_1h['data'], columns=cols)
    df_1h[['Open', 'High', 'Low', 'Close', 'Volume']] = df_1h[['Open', 'High', 'Low', 'Close', 'Volume']].apply(pd.to_numeric)

    df_daily = pd.DataFrame(res_1d['data'], columns=cols)
    df_daily[['Open', 'High', 'Low', 'Close', 'Volume']] = df_daily[['Open', 'High', 'Low', 'Close', 'Volume']].apply(pd.to_numeric)

    # 4-Hour Resampling
    df_4h = resample_to_4hr(df_1h)

    # HTF Bias Determination (1H & 4H EMA Trend)
    df_1h['EMA_20'] = df_1h['Close'].ewm(span=20, adjust=False).mean()
    df_4h['EMA_20'] = df_4h['Close'].ewm(span=20, adjust=False).mean()

    htf_1h_bullish = df_1h['Close'].iloc[-1] > df_1h['EMA_20'].iloc[-1]
    htf_4h_bullish = df_4h['Close'].iloc[-1] > df_4h['EMA_20'].iloc[-1]

    # Key Levels
    pdh = float(df_daily['High'].iloc[-2])
    pdl = float(df_daily['Low'].iloc[-2])
    pwh = float(df_daily['High'].iloc[-6]) if len(df_daily) >= 6 else pdh
    pwl = float(df_daily['Low'].iloc[-6]) if len(df_daily) >= 6 else pdl

    # 5M Indicators
    df_5m = calculate_vwap(df_5m)
    df_5m = calculate_order_flow_delta(df_5m)

    if len(df_5m) < 5:
        return

    curr = df_5m.iloc[-1]
    prev = df_5m.iloc[-2]
    prev2 = df_5m.iloc[-3]
    prev3 = df_5m.iloc[-4]

    curr_delta_pos = curr['Delta'] > 0
    curr_delta_neg = curr['Delta'] < 0
    cvd_expanding_up = curr['CVD'] > prev['CVD']
    cvd_expanding_down = curr['CVD'] < prev['CVD']
    above_vwap = curr['Close'] > curr['VWAP']
    below_vwap = curr['Close'] < curr['VWAP']

    entry_type = None
    entry_price = float(curr['Close'])
    sl = 0.0
    tp1 = 0.0
    tp2 = 0.0
    setup_name = ""
    reasons = []

    # ==========================================================
    # STRATEGY 1: LIQUIDITY SWEEP + FVG/OB RETEST (5M + HTF CONFLUENCE)
    # ==========================================================
    bull_sweep = (prev['Low'] < pdl and prev['Close'] > pdl) or (prev['Low'] < prev2['Low'] and prev['Close'] > prev2['Low'])
    bull_fvg_retest = (curr['Low'] <= prev2['High']) and (curr['Close'] >= prev2['High'])
    bull_ob_retest = (prev2['Close'] < prev2['Open']) and (curr['Low'] <= prev2['High']) and (curr['Close'] >= prev2['Low'])

    if bull_sweep and (bull_fvg_retest or bull_ob_retest) and above_vwap and curr_delta_pos and cvd_expanding_up and htf_1h_bullish:
        entry_type = "BUY"
        setup_name = "HTF Aligned Sweep + FVG/OB Retest"
        sl = float(min(curr['Low'], prev['Low']) - 5.0)
        reasons = ["1H/4H Bullish Trend Bias", "PDL/Low Liquidity Hunt", "FVG/OB Retested", "Above VWAP", f"Delta Positive (+{curr['Delta']:.0f}) & CVD Up"]

    bear_sweep = (prev['High'] > pdh and prev['Close'] < pdh) or (prev['High'] > prev2['High'] and prev['Close'] < prev2['High'])
    bear_fvg_retest = (curr['High'] >= prev2['Low']) and (curr['Close'] <= prev2['Low'])
    bear_ob_retest = (prev2['Close'] > prev2['Open']) and (curr['High'] >= prev2['Low']) and (curr['Close'] <= prev2['High'])

    if bear_sweep and (bear_fvg_retest or bear_ob_retest) and below_vwap and curr_delta_neg and cvd_expanding_down and not htf_1h_bullish:
        entry_type = "SELL"
        setup_name = "HTF Aligned Sweep + FVG/OB Retest"
        sl = float(max(curr['High'], prev['High']) + 5.0)
        reasons = ["1H/4H Bearish Trend Bias", "PDH/High Liquidity Hunt", "FVG/OB Retested", "Below VWAP", f"Delta Negative ({curr['Delta']:.0f}) & CVD Down"]

    # ==========================================================
    # STRATEGY 2: BREAKER BLOCK RETEST (UP & DOWN)
    # ==========================================================
    if not entry_type:
        failed_bear_ob = prev3['Close'] < prev3['Open']
        breaker_up_level = float(prev3['High'])
        if failed_bear_ob and prev['Close'] > breaker_up_level and (curr['Low'] <= breaker_up_level and curr['Close'] >= breaker_up_level) and above_vwap and curr_delta_pos and cvd_expanding_up:
            entry_type = "BUY"
            setup_name = "Bullish Breaker Block Retest"
            sl = float(min(curr['Low'], breaker_up_level) - 5.0)
            reasons = [f"Failed Bearish OB @ {breaker_up_level:.2f} Converted to Support", "5M Retest Validated", "Above VWAP", "Delta (+) & CVD Rising"]

        failed_bull_ob = prev3['Close'] > prev3['Open']
        breaker_down_level = float(prev3['Low'])
        if failed_bull_ob and prev['Close'] < breaker_down_level and (curr['High'] >= breaker_down_level and curr['Close'] <= breaker_down_level) and below_vwap and curr_delta_neg and cvd_expanding_down:
            entry_type = "SELL"
            setup_name = "Bearish Breaker Block Retest"
            sl = float(max(curr['High'], breaker_down_level) + 5.0)
            reasons = [f"Failed Bullish OB @ {breaker_down_level:.2f} Converted to Resistance", "5M Retest Validated", "Below VWAP", "Delta (-) & CVD Falling"]

    # ==========================================================
    # STRATEGY 3: FVG/OB + VWAP STRONG MOMENTUM SURGE
    # ==========================================================
    if not entry_type:
        vwap_bounce = (curr['Low'] <= curr['VWAP'] * 1.0008) and (curr['Close'] > curr['VWAP'])
        green_candle = (curr['Close'] > curr['Open']) and ((curr['Close'] - curr['Open']) >= (curr['High'] - curr['Low']) * 0.55)
        if (bull_fvg_retest or bull_ob_retest) and vwap_bounce and green_candle and curr_delta_pos and cvd_expanding_up:
            entry_type = "BUY"
            setup_name = "FVG/OB Retest + VWAP Strong Momentum Bounce"
            sl = float(curr['Low'] - 5.0)
            reasons = ["FVG/OB Retest", "VWAP Dynamic Support Reaction", "Strong Green Body", "Surging Institutional CVD"]

        vwap_reject = (curr['High'] >= curr['VWAP'] * 0.9992) and (curr['Close'] < curr['VWAP'])
        red_candle = (curr['Close'] < curr['Open']) and ((curr['Open'] - curr['Close']) >= (curr['High'] - curr['Low']) * 0.55)
        if (bear_fvg_retest or bear_ob_retest) and vwap_reject and red_candle and curr_delta_neg and cvd_expanding_down:
            entry_type = "SELL"
            setup_name = "FVG/OB Retest + VWAP Strong Momentum Rejection"
            sl = float(curr['High'] + 5.0)
            reasons = ["FVG/OB Retest", "VWAP Dynamic Resistance Reaction", "Strong Red Body", "Plunging Institutional CVD"]

    # ==========================================================
    # 6. RISK MANAGEMENT (TP1, TP2, SL) & DISPATCH
    # ==========================================================
    if entry_type:
        if entry_type == "BUY":
            risk = entry_price - sl
            if risk > 0:
                tp1 = entry_price + (2.0 * risk)
                tp2 = max(entry_price + (3.0 * risk), pdh, pwh)
        else:
            risk = sl - entry_price
            if risk > 0:
                tp1 = entry_price - (2.0 * risk)
                tp2 = min(entry_price - (3.0 * risk), pdl, pwl)

        if risk > 0:
            icon = "🟢" if entry_type == "BUY" else "🔴"
            delta_str = f"+{curr['Delta']:.0f}" if curr['Delta'] > 0 else f"{curr['Delta']:.0f}"
            cvd_str = "🟢 Bullish Accumulation" if cvd_expanding_up else "🔴 Bearish Distribution"
            htf_label = "🟢 1H/4H Bullish" if htf_1h_bullish else "🔴 1H/4H Bearish"

            msg = (
                f"⚡ *ICT/SMC MULTI-TF ALGO ALERT: {symbol}* ⚡\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 *SETUP:* `{setup_name}`\n"
                f"📌 *ACTION:* `{entry_type}` {icon}\n"
                f"💰 *Entry Price:* `{entry_price:.2f}`\n"
                f"🛑 *Stop Loss (SL):* `{sl:.2f}` _(Risk: {abs(risk):.2f} pts)_\n"
                f"🎯 *Target 1 (1:2 R:R):* `{tp1:.2f}`\n"
                f"🚀 *Target 2 (1:3 R:R / Liquidity):* `{tp2:.2f}`\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"⏳ *Higher Timeframe Bias (1H/4H):* `{htf_label}`\n"
                f"📊 *VWAP Level:* `{curr['VWAP']:.2f}`\n"
                f"⚡ *Present Candle Delta:* `{delta_str}`\n"
                f"🌊 *CVD Momentum:* `{cvd_str}`\n"
                f"📍 *PDH:* `{pdh:.2f}` | *PDL:* `{pdl:.2f}`\n"
                f"📍 *PWH:* `{pwh:.2f}` | *PWL:* `{pwl:.2f}`\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🔍 *Confluence Check:*\n• " + "\n• ".join(reasons) + "\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
            send_telegram(msg)
            print(f"Triggered: {setup_name} | {entry_type} @ {entry_price:.2f}")

# ==========================================
# 7. WORKER THREAD & APP ENTRY
# ==========================================
def run_trading_engine():
    session = get_angel_session()
    print("Multi-TF (5M + 1H/4H) SMC & Order Flow Engine Running...")
    while True:
        try:
            if session:
                analyze_market(session, token="99926000", symbol="NIFTY 50", exchange="NSE")
            else:
                session = get_angel_session()
            time.sleep(300)
        except Exception as err:
            print(f"Engine Loop Error: {err}")
            time.sleep(60)

# Automatically launch the trading engine thread in background
bot_thread = threading.Thread(target=run_trading_engine)
bot_thread.daemon = True
bot_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
