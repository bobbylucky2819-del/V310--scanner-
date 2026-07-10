import os
import time
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!", 200

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

# ---- కాన్ఫిగరేషన్ ----
BOT_TOKEN = os.environ.get("NEW_BOT_TOKEN")
CHAT_ID = os.environ.get("NEW_CHAT_ID")

SYMBOLS = [
    "BTC-USD", "ETH-USD", "XRP-USD", 
    "SBIN.NS", "TATAMOTORS.NS", "RELIANCE.NS", "INFY.NS"
]

def send_telegram_alert(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_cp = np.abs(df['High'] - df['Close'].shift(1))
    low_cp = np.abs(df['Low'] - df['Close'].shift(1))
    df_tr = pd.DataFrame({'tr1': high_low, 'tr2': high_cp, 'tr3': low_cp})
    tr = df_tr.max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

def fetch_live_data(symbol, interval):
    try:
        yf_interval = interval
        if interval in ["2h", "3h"]:
            yf_interval = "1h"
            
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="7d", interval=yf_interval)
        
        if df.empty or len(df) < 15:
            return None
            
        if interval == "2h":
            df = df.resample('2h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
        elif interval == "3h":
            df = df.resample('3h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
            
        return df[['High', 'Low', 'Close']]
    except:
        return None

def scan_v310_market():
    print("🚀 V310 Crypto & Indian Markets Scanner is live...")
    TIMEFRAMES = ["15m", "1h", "2h", "3h", "4h"]
    
    global last_signals
    last_signals = {}
    
    while True:
        for symbol in SYMBOLS:
            for tf in TIMEFRAMES:
                key = f"{symbol}_{tf}"
                if key not in last_signals:
                    last_signals[key] = {"state": None, "target": 0.0, "stop": 0.0}
                    
                df = fetch_live_data(symbol, tf)
                if df is None or len(df) < 10:
                    continue
                    
                try:
                    close = df['Close'].iloc[-1]
                    prev_close = df['Close'].iloc[-2]
                    
                    sub_df = df.iloc[-8:-1]
                    highest_high = sub_df['High'].max()
                    lowest_low = sub_df['Low'].min()
                    
                    atr_series = calculate_atr(df)
                    atr_val = atr_series.iloc[-1]
                    
                    state = last_signals[key]["state"]
                    target = last_signals[key]["target"]
                    stop = last_signals[key]["stop"]
                    
                    # ---- CHECK EXITS FIRST ----
                    if state == "CALL" and (close >= target or close <= stop):
                        send_telegram_alert(f"🔶 C.EXIT | {symbol.replace('.NS','')} ({tf}) | Price: {close:.2f}")
                        last_signals[key]["state"] = None
                    elif state == "PUT" and (close <= target or close >= stop):
                        send_telegram_alert(f"🔶 P.EXIT | {symbol.replace('.NS','')} ({tf}) | Price: {close:.2f}")
                        last_signals[key]["state"] = None
                        
                    # ---- CHECK NEW ENTRIES ----
                    elif prev_close <= highest_high and close > highest_high and state != "CALL":
                        last_signals[key]["target"] = close + (atr_val * 2)
                        last_signals[key]["stop"] = close - (atr_val * 1.5)
                        last_signals[key]["state"] = "CALL"
                        send_telegram_alert(f"🟢 C.BUY | {symbol.replace('.NS','')} ({tf}) | Entry: {close:.2f} | TG: {last_signals[key]['target']:.2f} | SL: {last_signals[key]['stop']:.2f}")
                        
                    elif prev_close >= lowest_low and close < lowest_low and state != "PUT":
                        last_signals[key]["target"] = close - (atr_val * 2)
                        last_signals[key]["stop"] = close + (atr_val * 1.5)
                        last_signals[key]["state"] = "PUT"
                        send_telegram_alert(f"🔴 P.BUY | {symbol.replace('.NS','')} ({tf}) | Entry: {close:.2f} | TG: {last_signals[key]['target']:.2f} | SL: {last_signals[key]['stop']:.2f}")
                except:
                    continue
                    
        time.sleep(300)

if __name__ == "__main__":
    # ఎర్రర్ ఉన్నా లేకపోయినా సర్వర్ ఆన్ అవ్వగానే ఈ మెసేజ్ ముందే వెళ్ళిపోతుంది!
    send_telegram_alert("🚀 Daya Master V310 Live! Crypto & Indian Markets Loaded (15m, 1h, 2h, 3h, 4h)")
    scan_v310_market()
            
