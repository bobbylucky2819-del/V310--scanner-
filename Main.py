import os
import time
import requests
import pandas as pd
import numpy as np

# --- న్యూ సెపరేట్ టెలిగ్రామ్ కాన్ఫిగరేషన్ ---
BOT_TOKEN = os.environ.get("NEW_BOT_TOKEN")
CHAT_ID = os.environ.get("NEW_CHAT_ID")

# స్కాన్ చేయాల్సిన సింబల్స్ లిస్ట్
SYMBOLS = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "EURUSD", "GBPUSD"]

# సిగ్నల్ హిస్టరీ ట్రాక్ చేయడానికి
last_signals = {symbol: {"state": None, "target": None, "stop": None} for symbol in SYMBOLS}

def send_telegram_alert(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Telegram Error: {e}")

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_cp = np.abs(df['high'] - df['close'].shift())
    low_cp = np.abs(df['low'] - df['close'].shift())
    df_tr = pd.DataFrame({'tr1': high_low, 'tr2': high_cp, 'tr3': low_cp})
    tr = df_tr.max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

def fetch_live_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=30"
    try:
        res = requests.get(url).json()
        df = pd.DataFrame(res, columns=['time', 'open', 'high', 'low', 'close', 'v', 'ct', 'qa', 'nt', 'tb', 'tg', 'i'])
        return df[['high', 'low', 'close']].astype(float)
    except:
        return None

def scan_v310_market():
    print("🚀 V310 Separate Scanner is running 24/7 on Render...")
    while True:
        for symbol in SYMBOLS:
            df = fetch_live_data(symbol)
            if df is None or len(df) < 20: continue
            
            close = df['close'].iloc[-1]
            prev_close = df['close'].iloc[-2]
            
            # V310 SMC Filter: Past 7 bars highest/lowest
            highest_high = df['high'].shift(1).iloc[-8:-1].max()
            lowest_low = df['low'].shift(1).iloc[-8:-1].min()
            
            atr_val = calculate_atr(df).iloc[-1]
            state = last_signals[symbol]["state"]
            
            # ---- CHECK EXITS FIRST ----
            if state == "CALL" and (close >= last_signals[symbol]["target"] or close <= last_signals[symbol]["stop"]):
                send_telegram_alert(f"🚨 *V310 CALL EXIT (C.EXIT)* 🚨\n\n📊 *Symbol:* {symbol}\n💰 *Exit Price:* {close}")
                last_signals[symbol] = {"state": None, "target": None, "stop": None}
                
            elif state == "PUT" and (close <= last_signals[symbol]["target"] or close >= last_signals[symbol]["stop"]):
                send_telegram_alert(f"🚨 *V310 PUT EXIT (P.EXIT)* 🚨\n\n📊 *Symbol:* {symbol}\n💰 *Exit Price:* {close}")
                last_signals[symbol] = {"state": None, "target": None, "stop": None}
            
            # ---- CHECK NEW ENTRIES ----
            elif prev_close <= highest_high and close > highest_high and state != "CALL":
                target = close + (atr_val * 2)
                stop = close - (atr_val * 1.5)
                last_signals[symbol] = {"state": "CALL", "target": target, "stop": stop}
                send_telegram_alert(f"🟢 *V310 CALL BUY (C.BUY)* 🟢\n\n📊 *Symbol:* {symbol}\n🎯 *Entry:* {close}\n🛑 *SL:* {stop:.4f}\n💰 *Target:* {target:.4f}")
                
            elif prev_close >= lowest_low and close < lowest_low and state != "PUT":
                target = close - (atr_val * 2)
                stop = close + (atr_val * 1.5)
                last_signals[symbol] = {"state": "PUT", "target": target, "stop": stop}
                send_telegram_alert(f"🔴 *V310 PUT BUY (P.BUY)* 🔴\n\n📊 *Symbol:* {symbol}\n🎯 *Entry:* {close}\n🛑 *SL:* {stop:.4f}\n💰 *Target:* {target:.4f}")
                
        time.sleep(60)

if __name__ == "__main__":
    scan_v310_market()
          
