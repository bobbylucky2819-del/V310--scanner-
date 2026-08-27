import os
import time
import datetime
import pyotp
import requests
import pandas as pd
import numpy as np
from SmartApi import SmartConnect

# ==========================================
# 1. CREDENTIALS & CONFIGURATION
# ==========================================
CLIENT_ID = os.getenv("ANGEL_CLIENT_ID", "AAAE383027")
MPIN = os.getenv("ANGEL_MPIN", "2222")
API_KEY = os.getenv("ANGEL_API_KEY", "5L3fPSxW")
TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET", "CV42EVYE6UNCQKEIZWEQHSIUZM")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ==========================================
# 2. AUTHENTICATION & TELEGRAM UTILITIES
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
        print(f"[TELEGRAM ALERT LOG]:\n{message}\n")
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
# 3. INDICATOR CALCULATIONS
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
    # Intraday Order Flow Delta & Buy/Sell Volume Approximation
    df['Buy_Vol'] = ((df['Close'] - df['Low']) / spread) * df['Volume']
    df['Sell_Vol'] = df['Volume'] - df['Buy_Vol']
    df['Delta'] = df['Buy_Vol'] - df['Sell_Vol']
    df['CVD'] = df['Delta'].cumsum()
    df['Vol_SMA'] = df['Volume'].rolling(window=20).mean().bfill()
    return df

# ==========================================
# 4. CORE SMC / ICT / VWAP ANALYSIS ENGINE
# ==========================================
def analyze_market(obj, token="99926000", symbol="NIFTY 50", exchange="NSE"):
    now = datetime.datetime.now()
    from_date = (now - datetime.timedelta(days=7)).strftime("%Y-%m-%d 09:15")
    to_date = now.strftime("%Y-%m-%d %H:%M")

    # A. 5-Minute Intraday Data Fetch
    res_5m = obj.getCandleData({
        "exchange": exchange,
        "symboltoken": token,
        "interval": "FIVE_MINUTE",
        "fromdate": from_date,
        "todate": to_date
    })

    # B. Daily Data Fetch (PDH, PDL)
    res_1d = obj.getCandleData({
        "exchange": exchange,
        "symboltoken": token,
        "interval": "ONE_DAY",
        "fromdate": (now - datetime.timedelta(days=30)).strftime("%Y-%m-%d 09:15"),
        "todate": to_date
    })

    # C. Weekly Data Fetch (PWH, PWL)
    res_1w = obj.getCandleData({
        "exchange": exchange,
        "symboltoken": token,
        "interval": "ONE_DAY",
        "fromdate": (now - datetime.timedelta(days=90)).strftime("%Y-%m-%d 09:15"),
        "todate": to_date
    })

    if not res_5m or not res_5m.get('data') or not res_1d or not res_1d.get('data'):
        print(f"Data feed empty for {symbol}")
        return

    cols = ["Timestamp", "Open", "High", "Low", "Close", "Volume"]
    df = pd.DataFrame(res_5m['data'], columns=cols)
    df[['Open', 'High', 'Low', 'Close', 'Volume']] = df[['Open', 'High', 'Low', 'Close', 'Volume']].apply(pd.to_numeric)

    daily_df = pd.DataFrame(res_1d['data'], columns=cols)
    daily_df[['Open', 'High', 'Low', 'Close', 'Volume']] = daily_df[['Open', 'High', 'Low', 'Close', 'Volume']].apply(pd.to_numeric)

    weekly_df = pd.DataFrame(res_1w['data'], columns=cols)
    weekly_df[['Open', 'High', 'Low', 'Close', 'Volume']] = weekly_df[['Open', 'High', 'Low', 'Close', 'Volume']].apply(pd.to_numeric)

    # Key Levels Calculation
    pdh = float(daily_df['High'].iloc[-2])
    pdl = float(daily_df['Low'].iloc[-2])
    pwh = float(weekly_df['High'].iloc[-6]) if len(weekly_df) >= 6 else pdh
    pwl = float(weekly_df['Low'].iloc[-6]) if len(weekly_df) >= 6 else pdl

    # Technical Layers
    df = calculate_vwap(df)
    df = calculate_order_flow_delta(df)

    if len(df) < 5:
        return

    # Candle References
    curr = df.iloc[-1]    # Present Candle (n)
    prev = df.iloc[-2]    # Previous Candle (n-1)
    prev2 = df.iloc[-3]   # Candle (n-2)
    prev3 = df.iloc[-4]   # Candle (n-3)

    # Metrics
    curr_delta_pos = curr['Delta'] > 0
    curr_delta_neg = curr['Delta'] < 0
    cvd_expanding_up = curr['CVD'] > prev['CVD']
    cvd_expanding_down = curr['CVD'] < prev['CVD']
    above_vol_sma = curr['Volume'] >= curr['Vol_SMA']
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
    # STRATEGY 1: LIQUIDITY SWEEP + RETEST + VWAP + DELTA (+) / (-)
    # ==========================================================
    # Bullish Liquidity Sweep (PDL / PWL / Swing Low Sweep & Reject)
    bull_sweep = (prev['Low'] < pdl and prev['Close'] > pdl) or (prev['Low'] < prev2['Low'] and prev['Close'] > prev2['Low'])
    bull_fvg_retest = (curr['Low'] <= prev2['High']) and (curr['Close'] >= prev2['High'])
    bull_ob_retest = (prev2['Close'] < prev2['Open']) and (curr['Low'] <= prev2['High']) and (curr['Close'] >= prev2['Low'])

    if bull_sweep and (bull_fvg_retest or bull_ob_retest) and above_vwap and curr_delta_pos and cvd_expanding_up:
        entry_type = "BUY"
        setup_name = "Liquidity Sweep + FVG/OB Retest (Bullish)"
        sl = float(min(curr['Low'], prev['Low']) - 5.0)
        reasons = [
            "PDL / Swing Low Liquidity Hunt Complete",
            "FVG / OB Zone Successfully Retested",
            "Holding Above Institutional VWAP",
            f"Present Delta Positive (+{curr['Delta']:.0f}) & CVD Expanding Up",
            "Above Average Volume Activity" if above_vol_sma else "Standard Institutional Flow"
        ]

    # Bearish Liquidity Sweep (PDH / PWH / Swing High Sweep & Reject)
    bear_sweep = (prev['High'] > pdh and prev['Close'] < pdh) or (prev['High'] > prev2['High'] and prev['Close'] < prev2['High'])
    bear_fvg_retest = (curr['High'] >= prev2['Low']) and (curr['Close'] <= prev2['Low'])
    bear_ob_retest = (prev2['Close'] > prev2['Open']) and (curr['High'] >= prev2['Low']) and (curr['Close'] <= prev2['High'])

    if bear_sweep and (bear_fvg_retest or bear_ob_retest) and below_vwap and curr_delta_neg and cvd_expanding_down:
        entry_type = "SELL"
        setup_name = "Liquidity Sweep + FVG/OB Retest (Bearish)"
        sl = float(max(curr['High'], prev['High']) + 5.0)
        reasons = [
            "PDH / Swing High Liquidity Hunt Complete",
            "FVG / OB Zone Successfully Retested",
            "Holding Below Institutional VWAP",
            f"Present Delta Negative ({curr['Delta']:.0f}) & CVD Falling Down",
            "Above Average Volume Activity" if above_vol_sma else "Standard Institutional Flow"
        ]

    # ==========================================================
    # STRATEGY 2: ORDER BLOCK BREAKER (UP & DOWN RETEST)
    # ==========================================================
    if not entry_type:
        # Bullish Breaker: Failed Bearish OB Broken Upward -> Retested as Support
        failed_bear_ob = prev3['Close'] < prev3['Open']
        breaker_up_level = float(prev3['High'])
        broken_up = prev['Close'] > breaker_up_level
        retested_up_support = (curr['Low'] <= breaker_up_level) and (curr['Close'] >= breaker_up_level)

        if failed_bear_ob and broken_up and retested_up_support and above_vwap and curr_delta_pos and cvd_expanding_up:
            entry_type = "BUY"
            setup_name = "Bullish Breaker Block Retest"
            sl = float(min(curr['Low'], breaker_up_level) - 5.0)
            reasons = [
                f"Failed Bearish OB at {breaker_up_level:.2f} Converted to Support",
                "Clean Retest on Present Candle",
                "Confluence Above VWAP Baseline",
                f"Order Flow Delta Positive (+{curr['Delta']:.0f})"
            ]

        # Bearish Breaker: Failed Bullish OB Broken Downward -> Retested as Resistance
        failed_bull_ob = prev3['Close'] > prev3['Open']
        breaker_down_level = float(prev3['Low'])
        broken_down = prev['Close'] < breaker_down_level
        retested_down_resistance = (curr['High'] >= breaker_down_level) and (curr['Close'] <= breaker_down_level)

        if failed_bull_ob and broken_down and retested_down_resistance and below_vwap and curr_delta_neg and cvd_expanding_down:
            entry_type = "SELL"
            setup_name = "Bearish Breaker Block Retest"
            sl = float(max(curr['High'], breaker_down_level) + 5.0)
            reasons = [
                f"Failed Bullish OB at {breaker_down_level:.2f} Converted to Resistance",
                "Clean Retest on Present Candle",
                "Confluence Below VWAP Baseline",
                f"Order Flow Delta Negative ({curr['Delta']:.0f})"
            ]

    # ==========================================================
    # STRATEGY 3: FVG/OB RETEST + STRONG VWAP MOMENTUM SURGE
    # ==========================================================
    if not entry_type:
        vwap_touch_bounce = (curr['Low'] <= curr['VWAP'] * 1.0008) and (curr['Close'] > curr['VWAP'])
        strong_green_body = (curr['Close'] > curr['Open']) and ((curr['Close'] - curr['Open']) >= (curr['High'] - curr['Low']) * 0.55)
        
        if (bull_fvg_retest or bull_ob_retest) and vwap_touch_bounce and strong_green_body and curr_delta_pos and cvd_expanding_up:
            entry_type = "BUY"
            setup_name = "FVG/OB Retest + VWAP Strong Momentum Bounce"
            sl = float(curr['Low'] - 5.0)
            reasons = [
                "Institutional FVG/OB Retest Validated",
                "VWAP Dynamic Support Reaction",
                "Strong Green Body Momentum Bar",
                f"Positive Delta (+{curr['Delta']:.0f}) with High Relative Volume"
            ]

        vwap_touch_rejection = (curr['High'] >= curr['VWAP'] * 0.9992) and (curr['Close'] < curr['VWAP'])
        strong_red_body = (curr['Close'] < curr['Open']) and ((curr['Open'] - curr['Close']) >= (curr['High'] - curr['Low']) * 0.55)

        if (bear_fvg_retest or bear_ob_retest) and vwap_touch_rejection and strong_red_body and curr_delta_neg and cvd_expanding_down:
            entry_type = "SELL"
            setup_name = "FVG/OB Retest + VWAP Strong Momentum Rejection"
            sl = float(curr['High'] + 5.0)
            reasons = [
                "Institutional FVG/OB Retest Validated",
                "VWAP Dynamic Resistance Reaction",
                "Strong Red Body Momentum Bar",
                f"Negative Delta ({curr['Delta']:.0f}) with High Relative Volume"
            ]

    # ==========================================================
    # 5. RISK MANAGEMENT (TP1, TP2, SL) & DISPATCH
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
            delta_status = f"+{curr['Delta']:.0f}" if curr['Delta'] > 0 else f"{curr['Delta']:.0f}"
            cvd_trend_label = "🟢 Bullish Accumulation (Expanding)" if cvd_expanding_up else "🔴 Bearish Distribution (Falling)"

            msg = (
                f"⚡ *ICT & SMC INSTITUTIONAL ALERT: {symbol}* ⚡\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 *SETUP:* `{setup_name}`\n"
                f"📌 *ACTION:* `{entry_type}` {icon}\n"
                f"💰 *Entry Price:* `{entry_price:.2f}`\n"
                f"🛑 *Stop Loss (SL):* `{sl:.2f}` _(Risk: {abs(risk):.2f} pts)_\n"
                f"🎯 *Target 1 (1:2 R:R):* `{tp1:.2f}`\n"
                f"🚀 *Target 2 (1:3 R:R / Liquidity):* `{tp2:.2f}`\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📊 *VWAP Level:* `{curr['VWAP']:.2f}`\n"
                f"⚡ *Present Candle Delta:* `{delta_status}`\n"
                f"🌊 *CVD Momentum:* `{cvd_trend_label}`\n"
                f"📍 *PDH:* `{pdh:.2f}` | *PDL:* `{pdl:.2f}`\n"
                f"📍 *PWH:* `{pwh:.2f}` | *PWL:* `{pwl:.2f}`\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🔍 *Confluence Check:*\n• " + "\n• ".join(reasons) + "\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
            send_telegram(msg)
            print(f"Triggered: {setup_name} | {entry_type} @ {entry_price:.2f}")

# ==========================================
# 6. MAIN EXECUTION LOOP
# ==========================================
if __name__ == "__main__":
    session = get_angel_session()
    print("ICT/SMC Sweep + Breaker + VWAP + Delta Engine Running on 5M Cycle...")

    while True:
        try:
            if session:
                # NIFTY 50 Token: 99926000 (NSE)
                analyze_market(session, token="99926000", symbol="NIFTY 50", exchange="NSE")
            else:
                session = get_angel_session()
            time.sleep(300)  # 5-Minute Candle Scan Loop
        except Exception as err:
            print(f"Loop Exception: {err}")
            time.sleep(60)
