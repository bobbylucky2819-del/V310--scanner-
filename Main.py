import os
import time
import requests
from flask import Flask, jsonify
from SmartApi import SmartConnect
import pyotp

app = Flask(__name__)

# ==========================================
# CONFIGURATION & CREDENTIALS
# ==========================================
API_KEY      = os.getenv("API_KEY", "5L3fPSxW")
CLIENT_CODE  = os.getenv("CLIENT_CODE", "YOUR_ANGEL_CLIENT_ID") # Mee Angel One Client ID ikkada ivvandi
PASSWORD     = os.getenv("PASSWORD", "YOUR_ANGEL_PIN")           # Mee Angel One Trading PIN
TOTP_SECRET  = os.getenv("TOTP_SECRET", "YOUR_TOTP_SECRET")      # Angel One App lo TOTP Key

BOT_TOKEN    = os.getenv("BOT_TOKEN", "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4")
CHAT_ID      = os.getenv("CHAT_ID", "-1004423772510")

# ==========================================
# TELEGRAM NOTIFICATION FUNCTION
# ==========================================
def send_telegram_alert(signal_type, symbol, price, tf):
    msg = f"🚨 *ANGEL ONE SMC SIGNAL: {signal_type}*\n\n" \
          f"📈 *Symbol:* `{symbol}`\n" \
          f"⏱️ *Timeframe:* `{tf}`\n" \
          f"💰 *Price:* `{price}`\n" \
          f"🤖 *Bot:* `@luckyTradingV310Bot`"
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram error: {e}")

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Angel One Live Scanner Running!"}), 200

# ==========================================
# ANGEL ONE LIVE SCANNER ENGINE
# ==========================================
def run_angel_scanner():
    try:
        smart_api = SmartConnect(api_key=API_KEY)
        totp = pyotp.TOTP(TOTP_SECRET).now()
        smart_api.generateSession(CLIENT_CODE, PASSWORD, totp)
        print("✅ Angel One API Connected Successfully!")

        symbols = [
            {"name": "NIFTY", "token": "99926000"},
            {"name": "BANKNIFTY", "token": "99926009"}
        ]

        for item in symbols:
            params = {
                "exchange": "NSE",
                "symboltoken": item["token"],
                "interval": "ONE_HOUR",
                "fromdate": "2026-07-20 09:15",
                "todate": "2026-07-26 15:30"
            }
            res = smart_api.getCandleData(params)
            if res and 'data' in res and len(res['data']) >= 2:
                candles = res['data']
                prev_c = candles[-2]
                curr_c = candles[-1]

                prev_high, prev_low = prev_c[2], prev_c[3]
                curr_high, curr_low, curr_close = curr_c[2], curr_c[3], curr_c[4]

                # SMC 1H Liquidity Sweep Conditions
                if curr_low < prev_low and curr_close > prev_low:
                    send_telegram_alert("CALL BUY (Bullish Sweep)", item["name"], curr_close, "1H")
                elif curr_high > prev_high and curr_close < prev_high:
                    send_telegram_alert("PUT BUY (Bearish Sweep)", item["name"], curr_close, "1H")

    except Exception as e:
        print(f"Scanner Exception: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
        
