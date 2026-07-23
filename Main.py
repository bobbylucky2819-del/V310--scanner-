import os
import time
import datetime
import requests
import pyotp
import pytz
import json
import websocket
from threading import Thread
from flask import Flask
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

app = Flask(__name__)

@app.route('/')
def home():
    return "Daya Master Active Engine Live!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ==========================================
# CONFIGURATIONS
# ==========================================
API_KEY     = os.environ.get("API_KEY", "5L3fPSxW")
CLIENT_ID   = os.environ.get("CLIENT_ID", "")
PWD         = os.environ.get("PIN", "")
TOTP_SECRET = os.environ.get("TOTP_SECRET", "CV42EVYE6UNCQKEIZWEQHSIUZM")

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4")
TELEGRAM_CHAT_ID   = os.environ.get("CHAT_ID", "-1004423772510")

IST = pytz.timezone('Asia/Kolkata')

def send_telegram(box_str, text_msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: 
        return
    escaped_box = (box_str.replace('.', '\\.').replace('-', '\\-')
                   .replace('[', '\\[').replace(']', '\\]')
                   .replace('(', '\\(').replace(')', '\\)').replace('|', '\\|'))
    formatted_text = f"{text_msg}\n\n```text\n{escaped_box}\n```"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": formatted_text,
                "parse_mode": "MarkdownV2"
            },
            timeout=5
        )
        print(response.status_code, response.text)
    except Exception as e:
        print("Telegram Send Error:", e)

def generate_box(market_title, version, name, tf, side, entry, sl, tp, ltp, mbs, mrs, final_str):
    return (
        f"┌──────────────────────────────────────────────┐\n"
        f"│ 🏛️ {market_title:<10}: {name:<10} [{tf:<3} TF]         │\n"
        f"│ 📈 Action          : {side:<24} │\n"
        f"├──────────────────────────────────────────────┤\n"
        f"│  Daya SMC -> {version:<28} │\n"
        f"├──────────────────────────────────────────────┤\n"
        f"│ 🪙 Entry  — {entry:<8.2f} →  🛑 StopLoss — {sl:<8.2f}│\n"
        f"│ 🎯 Target — {tp:<8.2f}                           │\n"
        f"│ 📈 Price  — {ltp:<8.2f}                           │\n"
        f"├──────────────────────────────────────────────┤\n"
        f"│ 🟢 M.B.S. — {mbs:<32} │\n"
        f"│ ⚠️ M.R.S. — {mrs:<32} │\n"
        f"├──────────────────────────────────────────────┤\n"
        f"│ 🏁 Status → {final_str:<32} │\n"
        f"└──────────────────────────────────────────────┘"
    )

# ==========================================
# 1. ANGEL ONE ENGINE (NSE ALERTS)
# ==========================================
class AngelSmartEngine:
    def __init__(self):
        self.smart_api = SmartConnect(api_key=API_KEY)
        self.feed_token = None
        self.jwt_token = None
        self.sws = None
        self.levels = {
            "2885": {"name": "RELIANCE", "last_price": 0, "last_time": 0},
            "3045": {"name": "SBIN",     "last_price": 0, "last_time": 0}
        }

    def login(self):
        totp = pyotp.TOTP(TOTP_SECRET).now()
        data = self.smart_api.generateSession(CLIENT_ID, PWD, totp)
        print("Login Response:", data)
        if data and data.get('status'):
            self.jwt_token = data['data']['jwtToken']
            self.feed_token = self.smart_api.getfeedToken()
            return True
        return False

    def on_data(self, wsapp, message):
        print(message)
        try:
            token = message.get('token')
            ltp = float(message.get('last_traded_price', 0)) / 100.0
            
            if token in self.levels and ltp > 0:
                now = time.time()
                last_p = self.levels[token]['last_price']
                last_t = self.levels[token]['last_time']
                name = self.levels[token]['name']

                if last_p == 0:
                    self.levels[token]['last_price'] = ltp
                    self.levels[token]['last_time'] = now
                    return

                change_pct = abs((ltp - last_p) / last_p) * 100

                if change_pct >= 0.05 or (now - last_t >= 20):
                    self.levels[token]['last_price'] = ltp
                    self.levels[token]['last_time'] = now

                    if ltp >= last_p:
                        sl, tp = ltp * 0.995, ltp * 1.010
                        box = generate_box("NSE LIVE", "Daya Master V87", name, "1m", "C.BUY (CALL) [🟢]", ltp, sl, tp, ltp, "[🟢 Live Price Movement]", "[⚡ Exchange Feed]", "RUNNING")
                        send_telegram(box, f"🚀 *NSE Live Signal: {name}* 🚀")
                    else:
                        sl, tp = ltp * 1.005, ltp * 0.990
                        box = generate_box("NSE LIVE", "Daya Master V87", name, "1m", "P.BUY (PUT) [🔴]", ltp, sl, tp, ltp, "[🔴 Live Price Drop]", "[⚡ Exchange Feed]", "RUNNING")
                        send_telegram(box, f"💥 *NSE Live Signal: {name}* 💥")
        except Exception as e:
            print("NSE Error:", e)

    def on_open(self, wsapp):
        print("Angel WebSocket Connected")
        token_list = [{"exchangeType": 1, "tokens": ["2885", "3045"]}]
        self.sws.subscribe("correl_id_1", 1, token_list)

    def start(self):
        if not self.login():
            return
        self.sws = SmartWebSocketV2(self.jwt_token, API_KEY, CLIENT_ID, self.feed_token)
        self.sws.on_data = self.on_data
        self.sws.on_open = self.on_open
        self.sws.connect()

# ==========================================
# 2. BINANCE ENGINE (CRYPTO ALERTS)
# ==========================================
class BinanceWebSocketEngine:
    def __init__(self, symbols):
        self.symbols = symbols
        self.levels = {s: {"last_price": 0, "last_time": 0} for s in symbols}

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if "data" in data:
                data = data["data"]

            symbol = data['s']
            ltp = float(data['c'])

            if symbol in self.levels and ltp > 0:
                now = time.time()
                last_p = self.levels[symbol]['last_price']
                last_t = self.levels[symbol]['last_time']

                if last_p == 0:
                    self.levels[symbol]['last_price'] = ltp
                    self.levels[symbol]['last_time'] = now
                    return

                change_pct = abs((ltp - last_p) / last_p) * 100

                if change_pct >= 0.05 or (now - last_t >= 20):
                    self.levels[symbol]['last_price'] = ltp
                    self.levels[symbol]['last_time'] = now

                    if ltp >= last_p:
                        sl, tp = ltp * 0.994, ltp * 1.012
                        box = generate_box("BINANCE", "Crypto Live V87", symbol, "1m", "C.BUY (CALL) [🟢]", ltp, sl, tp, ltp, "[🟢 Live Price Move]", "[⚡ Direct WebSocket]", "RUNNING")
                        send_telegram(box, f"🚀 *Binance Signal: {symbol}* 🚀")
                    else:
                        sl, tp = ltp * 1.006, ltp * 0.988
                        box = generate_box("BINANCE", "Crypto Live V87", symbol, "1m", "P.BUY (PUT) [🔴]", ltp, sl, tp, ltp, "[🔴 Live Price Drop]", "[⚡ Direct WebSocket]", "RUNNING")
                        send_telegram(box, f"💥 *Binance Signal: {symbol}* 💥")
        except Exception as e:
            print("Binance Error:", e)

    def start(self):
        streams = "/".join([f"{s.lower()}@ticker" for s in self.symbols])
        url = f"wss://stream.binance.com:9443/stream?streams={streams}"
        ws = websocket.WebSocketApp(url, on_message=self.on_message)
        while True:
            try:
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                print(e)
                time.sleep(5)

# ==========================================
# THREAD INITIALIZATION
# ==========================================
def start_angel():
    engine = AngelSmartEngine()
    engine.start()

def start_crypto():
    crypto_engine = BinanceWebSocketEngine(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    crypto_engine.start()

Thread(target=run_web_server, daemon=True).start()
Thread(target=start_crypto, daemon=True).start()
Thread(target=start_angel, daemon=True).start()

try:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": "⚡ Daya Master Fast Signal Engine V87.0 Live!"}, timeout=5)
except Exception:
    pass

if __name__ == "__main__":
    while True:
        time.sleep(1)
    
