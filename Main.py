import os
import requests
from flask import Flask, jsonify
from SmartApi import SmartConnect
import pyotp

app = Flask(__name__)

# ==========================================
# ANGEL ONE CREDENTIALS
# ==========================================
API_KEY      = os.getenv("API_KEY", "5L3fPSxW")
CLIENT_CODE  = os.getenv("CLIENT_CODE", "AAAE383027")
PASSWORD     = os.getenv("PASSWORD", "2222")
TOTP_SECRET  = os.getenv("TOTP_SECRET", "CV42EVYE6UNCQKEIZWEQHSIUZM")

BOT_TOKEN    = os.getenv("BOT_TOKEN", "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4")
CHAT_ID      = os.getenv("CHAT_ID", "-1004423772510")

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
        print(f"Telegram alert error: {e}")

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Angel One Live SMC Scanner Active!", "client": CLIENT_CODE}), 200

@app.route("/scan", methods=["GET", "POST"])
def scan_market():
    try:
        smart_api = SmartConnect(api_key=API_KEY)
        totp_code = pyotp.TOTP(TOTP_SECRET).now()
        login_res = smart_api.generateSession(CLIENT_CODE, PASSWORD, totp_code)
        
        if not login_res.get('status'):
            return jsonify({"status": "error", "message": "Angel One Login Failed"}), 400

        symbols = [
            {"name": "NIFTY", "token": "99926000"},
            {"name": "BANKNIFTY", "token": "99926009"}
        ]

        signals_found = []

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
                prev_c, curr_c = candles[-2], candles[-1]
                
                prev_high, prev_low = prev_c[2], prev_c[3]
                curr_high, curr_low, curr_close = curr_c[2], curr_c[3], curr_c[4]

                if curr_low < prev_low and curr_close > prev_low:
                    send_telegram_alert("CALL BUY (Bullish Sweep)", item["name"], curr_close, "1H")
                    signals_found.append(f"{item['name']} CALL BUY")
                elif curr_high > prev_high and curr_close < prev_high:
                    send_telegram_alert("PUT BUY (Bearish Sweep)", item["name"], curr_close, "1H")
                    signals_found.append(f"{item['name']} PUT BUY")

        return jsonify({"status": "success", "signals": signals_found}), 200

    except Exception as e:
        return jsonify({"status": "error", "details": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
