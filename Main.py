import os
import requests
import pytz
from datetime import datetime, timedelta
from flask import Flask, jsonify
from SmartApi import SmartConnect
import pyotp

app = Flask(__name__)

# Credentials
API_KEY      = os.getenv("API_KEY", "5L3fPSxW")
CLIENT_CODE  = os.getenv("CLIENT_CODE", "AAAE383027")
PASSWORD     = os.getenv("PASSWORD", "2222")
TOTP_SECRET  = os.getenv("TOTP_SECRET", "CV42EVYE6UNCQKEIZWEQHSIUZM")

BOT_TOKEN    = os.getenv("BOT_TOKEN", "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4")
CHAT_ID      = os.getenv("CHAT_ID", "-1004423772510")

# Duplicate messages control cheyadaniki last sent signal memory
last_sent_signals = {}

def is_market_open():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    
    # Check if Monday to Friday (0 to 4)
    if now.weekday() >= 5:
        return False
        
    # Check Market Timing (9:15 AM to 3:30 PM)
    market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    return market_start <= now <= market_end

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
    return jsonify({"status": "Angel One SMC Scanner Active!", "client": CLIENT_CODE}), 200

@app.route("/scan", methods=["GET", "POST"])
def scan_market():
    global last_sent_signals
    
    # Market Open lo lenappudu (Night/Weekends) scans skip chestundi
    if not is_market_open():
        return jsonify({"status": "skipped", "reason": "Market is Closed"}), 200

    try:
        smart_api = SmartConnect(api_key=API_KEY)
        totp_code = pyotp.TOTP(TOTP_SECRET).now()
        login_res = smart_api.generateSession(CLIENT_CODE, PASSWORD, totp_code)
        
        if not login_res.get('status'):
            return jsonify({"status": "error", "message": "Angel One Login Failed"}), 400

        now = datetime.now()
        from_d = (now - timedelta(days=5)).strftime("%Y-%m-%d 09:15")
        to_d = now.strftime("%Y-%m-%d %H:%M")

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
                "fromdate": from_d,
                "todate": to_d
            }
            res = smart_api.getCandleData(params)
            if res and 'data' in res and len(res['data']) >= 2:
                candles = res['data']
                prev_c, curr_c = candles[-2], candles[-1]
                
                candle_time = curr_c[0] # Last candle timestamp
                prev_high, prev_low = prev_c[2], prev_c[3]
                curr_high, curr_low, curr_close = curr_c[2], curr_c[3], curr_c[4]

                sig_type = None
                if curr_low < prev_low and curr_close > prev_low:
                    sig_type = "CALL BUY (Bullish Sweep)"
                elif curr_high > prev_high and curr_close < prev_high:
                    sig_type = "PUT BUY (Bearish Sweep)"

                if sig_type:
                    # Unique Key: Symbol + Signal Type + Candle Time
                    sig_key = f"{item['name']}_{sig_type}_{candle_time}"
                    
                    # Already pampina signal ayithe duplicate filter chestundi
                    if last_sent_signals.get(item['name']) != sig_key:
                        send_telegram_alert(sig_type, item["name"], curr_close, "1H")
                        last_sent_signals[item['name']] = sig_key
                        signals_found.append(f"{item['name']} {sig_type}")

        return jsonify({"status": "success", "signals": signals_found}), 200

    except Exception as e:
        return jsonify({"status": "error", "details": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
