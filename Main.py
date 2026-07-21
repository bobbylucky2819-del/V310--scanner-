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
    return "Daya Master V87.0 SmartAPI & Binance WebSocket Engine Live!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ==========================================
# CONFIGURATIONS (ENVIRONMENT VARIABLES)
# ==========================================
API_KEY     = os.environ.get("API_KEY", "5L3fPSxW")
CLIENT_ID   = os.environ.get("CLIENT_ID", "")
PWD         = os.environ.get("PIN", "")
TOTP_SECRET = os.environ.get("TOTP_SECRET", "CV42EVYE6UNCQKEIZWEQHSIUZM")

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4")
TELEGRAM_CHAT_ID   = os.environ.get("CHAT_ID", "-1004423772510")

IST = pytz.timezone('Asia/Kolkata')

def send_telegram(box_str, text_msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    escaped_box = (box_str.replace('.', '\\.').replace('-', '\\-')
                   .replace('[', '\\[').replace(']', '\\]')
                   .replace('(', '\\(').replace(')', '\\)').replace('|', '\\|'))
    formatted_text = f"{text_msg}\n\n```text\n{escaped_box}\n```"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": formatted_text, "parse_mode": "MarkdownV2"}, timeout=5)
    except:
        pass

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
# 1. ANGEL ONE SMARTAPI WEBSOCKET ENGINE (NSE)
# ==========================================
class AngelSmartEngine:
    def __init__(self):
        self.smart_api = SmartConnect(api_key=API_KEY)
        self.feed_token = None
        self.jwt_token = None
        self.sws = None
        self.levels = {}

    def login(self):
        totp = pyotp.TOTP(TOTP_SECRET).now()
        data = self.smart_api.generateSession(CLIENT_ID, PWD, totp)
        if data and data.get('status'):
            self.jwt_token = data['data']['jwtToken']
            self.feed_token = self.smart_api.getfeedToken()
            return True
        return False

    def on_data(self, wsapp, message):
        try:
            token = message.get('token')
            ltp = float(message.get('last_traded_price', 0)) / 100.0
            if token in self.levels:
                p_high = self.levels[token]['p_high']
                p_low  = self.levels[token]['p_low']
                name   = self.levels[token]['name']

                if ltp > p_high and not self.levels[token]['buy_triggered']:
                    self.levels[token]['buy_triggered'] = True
                    sl, tp = ltp * 0.995, ltp * 1.010
                    box = generate_box("NSE LIVE", "SmartAPI V87.0", name, "15m", "C.BUY (CALL) [🟢]", ltp, sl, tp, ltp, "[🟢 High Breakout]", "[🔥 Tick-by-Tick Feed]", "RUNNING")
                    send_telegram(box, f"🚀 *NSE SmartAPI Buy Signal: {name}* 🚀")

                elif ltp < p_low and not self.levels[token]['sell_triggered']:
                    self.levels[token]['sell_triggered'] = True
                    sl, tp = ltp * 1.005, ltp * 0.990
                    box = generate_box("NSE LIVE", "SmartAPI V87.0", name, "15m", "P.BUY (PUT) [🔴]", ltp, sl, tp, ltp, "[🔴 Low Breakdown]", "[💥 Tick-by-Tick Feed]", "RUNNING")
                    send_telegram(box, f"💥 *NSE SmartAPI Sell Signal: {name}* 💥")
        except Exception:
            pass

    def start(self):
        if not self.login():
            return

        self.levels = {
            "2885": {"name": "RELIANCE", "p_high": 3000.0, "p_low": 2950.0, "buy_triggered": False, "sell_triggered": False},
            "3045": {"name": "SBIN",     "p_high": 850.0,  "p_low": 830.0,  "buy_triggered": False, "sell_triggered": False}
        }

        self.sws = SmartWebSocketV2(self.jwt_token, API_KEY, CLIENT_ID, self.feed_token)
        self.sws.on_data = self.on_data
        self.sws.connect()

# ==========================================
# 2. BINANCE WEBSOCKET ENGINE (CRYPTO)
# ==========================================
class BinanceWebSocketEngine:
    def __init__(self, symbols):
        self.symbols = symbols
        self.levels = {s: {"p_high": 0, "p_low": 0, "buy_triggered": False, "sell_triggered": False} for s in symbols}

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            symbol = data['s']
            ltp = float(data['c'])

            if symbol in self.levels:
                p_high = self.levels[symbol]['p_high']
                p_low  = self.levels[symbol]['p_low']

                if p_high > 0 and ltp > p_high and not self.levels[symbol]['buy_triggered']:
                    self.levels[symbol]['buy_triggered'] = True
                    sl, tp = ltp * 0.994, ltp * 1.012
                    box = generate_box("BINANCE", "Crypto Socket V87.0", symbol, "15m", "C.BUY (CALL) [🟢]", ltp, sl, tp, ltp, "[🟢 Instant High Break]", "[⚡ Direct WebSocket]", "RUNNING")
                    send_telegram(box, f"🚀 *Binance Socket Signal: {symbol}* 🚀")

                elif p_low > 0 and ltp < p_low and not self.levels[symbol]['sell_triggered']:
                    self.levels[symbol]['sell_triggered'] = True
                    sl, tp = ltp * 1.006, ltp * 0.988
                    box = generate_box("BINANCE", "Crypto Socket V87.0", symbol, "15m", "P.BUY (PUT) [🔴]", ltp, sl, tp, ltp, "[🔴 Instant Low Break]", "[⚡ Direct WebSocket]", "RUNNING")
                    send_telegram(box, f"💥 *Binance Socket Signal: {symbol}* 💥")
        except Exception:
            pass

    def start(self):
        streams = "/".join([f"{s.lower()}@ticker" for s in self.symbols])
        url = f"wss://stream.binance.com:9443/ws/{streams}"
        ws = websocket.WebSocketApp(url, on_message=self.on_message)
        ws.run_forever()

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
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": "⚡ Daya Master V87.0 SmartAPI & Binance WebSocket Live!"}, timeout=5)
except Exception:
    pass

if __name__ == "__main__":
    while True:
        time.sleep(1)
    
