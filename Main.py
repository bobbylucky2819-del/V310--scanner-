import os
import time
import datetime
import requests
from threading import Thread
from flask import Flask

try:
    import yfinance as yf
    import pytz
except ImportError:
    os.system('pip install yfinance pytz')
    import yfinance as yf
    import pytz

app = Flask(__name__)
@app.route('/')
def home(): return "Daya Master V86.1 Dual Fix Engine Active"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- TELEGRAM CONFIG ---
TELEGRAM_BOT_TOKEN = "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4"
TELEGRAM_CHAT_ID   = "-1004423772510"
IST = pytz.timezone('Asia/Kolkata')

def send_telegram(box_str, text_msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    escaped_box = box_str.replace('.', '\\.').replace('-', '\\-').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('|', '\\|')
    formatted_text = f"{text_msg}\n\n```text\n{escaped_box}\n```"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": formatted_text, "parse_mode": "MarkdownV2"}, timeout=5)
    except: pass

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
# 1. INDIAN MARKET (NSE) FIXED ENGINE
# ==========================================
class IndianNseEngine:
    def __init__(self, ticker_name):
        self.ticker = ticker_name
        self.clean_name = ticker_name.replace(".NS", "")
        self.active_trade = {"15m": None, "1h": None, "2h": None, "3h": None, "4h": None}
        self.last_signal_direction = {"15m": None, "1h": None, "2h": None, "3h": None, "4h": None}
        self.last_signal_candle_time = {"15m": None, "1h": None, "2h": None, "3h": None, "4h": None}

    def scan(self):
        now = datetime.datetime.now(IST)
        if now.weekday() >= 5: return
        if not (915 <= (now.hour * 100 + now.minute) <= 1530): return

        intraday_tfs = {"15m": "15m", "1h": "1h", "2h": "60m", "3h": "60m", "4h": "60m"}

        for tf, interval_str in intraday_tfs.items():
            try:
                stock = yf.Ticker(self.ticker)
                df = stock.history(period="5d", interval=interval_str)
                if df.empty or len(df) < 3: continue

                ltp = df['Close'].iloc[-1]
                live_open = df['Open'].iloc[-1]
                current_candle_time = df.index[-1]

                # --- LIVE TARGET & MRS PROTECTION ---
                if self.active_trade[tf]:
                    trade = self.active_trade[tf]
                    if trade["side"] == "BUY" and ltp >= trade["tp"]:
                        box = generate_box("NSE LIVE", "NSE Fix V86.1", self.clean_name, tf, "C.BUY [🟢]", trade["entry"], trade["sl"], trade["tp"], ltp, "[🟢 Target Cleared]", "PROFIT LOCKED ✅", "SUCCESS")
                        send_telegram(box, f"💰 *NSE Profit Secured: {self.clean_name} ({tf})* 💰")
                        self.active_trade[tf] = None
                        continue
                    elif trade["side"] == "SELL" and ltp <= trade["tp"]:
                        box = generate_box("NSE LIVE", "NSE Fix V86.1", self.clean_name, tf, "P.BUY [🔴]", trade["entry"], trade["sl"], trade["tp"], ltp, "[🔴 Target Cleared]", "PROFIT LOCKED ✅", "SUCCESS")
                        send_telegram(box, f"💰 *NSE Profit Secured: {self.clean_name} ({tf})* 💰")
                        self.active_trade[tf] = None
                        continue

                    if (trade["side"] == "BUY" and ltp < live_open) or (trade["side"] == "SELL" and ltp > live_open):
                        box = generate_box("NSE LIVE", "NSE Fix V86.1", self.clean_name, tf, trade["side"]+" EXIT", trade["entry"], trade["sl"], trade["tp"], ltp, "[⚠️ Reversal Detected]", "[🚨 MRS RESCUE EXIT]", "MARKET EXITED")
                        send_telegram(box, f"⚠️ *NSE MRS Rescue: Exited {self.clean_name} ({tf})* ⚠️")
                        self.active_trade[tf] = None
                        continue

                # --- EXACT HIGH/LOW BREAKOUT SCANS (FIXED) ---
                p_high, p_low = df['High'].iloc[-2], df['Low'].iloc[-2]

                if ltp > p_high:
                    if (self.last_signal_candle_time[tf] != current_candle_time) or (self.last_signal_direction[tf] != "BUY"):
                        self.last_signal_candle_time[tf] = current_candle_time
                        self.last_signal_direction[tf] = "BUY"
                        target, sl = ltp * 1.010, ltp * 0.995
                        self.active_trade[tf] = {"entry_time": current_candle_time, "entry": ltp, "sl": sl, "tp": target, "side": "BUY"}
                        box = generate_box("NSE LIVE", "NSE Fix V86.1", self.clean_name, tf, "C.BUY (CALL) [🟢]", ltp, sl, target, ltp, "[🟢 High Breakout]", "[🔥 Riding Momentum]", "RUNNING")
                        send_telegram(box, f"🚀 *NSE Buy Trigger: {self.clean_name} ({tf})* 🚀")

                elif ltp < p_low:
                    if (self.last_signal_candle_time[tf] != current_candle_time) or (self.last_signal_direction[tf] != "SELL"):
                        self.last_signal_candle_time[tf] = current_candle_time
                        self.last_signal_direction[tf] = "SELL"
                        target, sl = ltp * 0.990, ltp * 1.005
                        self.active_trade[tf] = {"entry_time": current_candle_time, "entry": ltp, "sl": sl, "tp": target, "side": "SELL"}
                        box = generate_box("NSE LIVE", "NSE Fix V86.1", self.clean_name, tf, "P.BUY (PUT) [🔴]", ltp, sl, target, ltp, "[🔴 Low Breakdown]", "[💥 Riding Crash Wave]", "RUNNING")
                        send_telegram(box, f"💥 *NSE Sell Trigger: {self.clean_name} ({tf})* 💥")
            except: pass

# ==========================================
# 2. BINANCE DIRECT CRYPTO FIXED ENGINE
# ==========================================
class BinanceCryptoEngine:
    def __init__(self, symbol):
        self.symbol = symbol
        self.active_trade = {"15m": None, "1h": None, "4h": None}
        self.last_signal_direction = {"15m": None, "1h": None, "4h": None}
        self.last_signal_candle_time = {"15m": None, "1h": None, "4h": None}

    def fetch_binance_klines(self, interval, limit=10):
        url = f"https://api.binance.com/api/v3/klines?symbol={self.symbol}&interval={interval}&limit={limit}"
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                parsed = []
                for item in data:
                    parsed.append({
                        'open_time': item[0],
                        'open': float(item[1]),
                        'high': float(item[2]),
                        'low': float(item[3]),
                        'close': float(item[4])
                    })
                return parsed
        except: pass
        return []

    def scan(self):
        tf_map = {"15m": "15m", "1h": "1h", "4h": "4h"}
        for tf, b_interval in tf_map.items():
            try:
                klines = self.fetch_binance_klines(b_interval, limit=10)
                if len(klines) < 3: continue

                curr, prev = klines[-1], klines[-2]
                ltp, live_open, candle_time = curr['close'], curr['open'], curr['open_time']

                # --- TARGET / MRS CONTROL ---
                if self.active_trade[tf]:
                    trade = self.active_trade[tf]
                    if (trade["side"] == "BUY" and ltp >= trade["tp"]) or (trade["side"] == "SELL" and ltp <= trade["tp"]):
                        box = generate_box("BINANCE", "Crypto Fix V86.1", self.symbol, tf, trade["side"]+" LOCKED", trade["entry"], trade["sl"], trade["tp"], ltp, "[🟢 Target Cleared]", "[🔥 PROFIT SECURED]", "PROFIT LOCKED ✅")
                        send_telegram(box, f"💰 *Crypto Target Cleared: {self.symbol} ({tf})* 💰")
                        self.active_trade[tf] = None
                        continue

                    if (trade["side"] == "BUY" and ltp < live_open) or (trade["side"] == "SELL" and ltp > live_open):
                        box = generate_box("BINANCE", "Crypto Fix V86.1", self.symbol, tf, "MRS EXIT", trade["entry"], trade["sl"], trade["tp"], ltp, "[⚠️ Reversal Detected]", "[🚨 MRS RESCUE EXIT]", "EXITED")
                        send_telegram(box, f"⚠️ *Crypto MRS Rescue: {self.symbol} ({tf})* ⚠️")
                        self.active_trade[tf] = None
                        continue

                # --- EXACT HIGH/LOW BREAKOUT SCANS (FIXED) ---
                p_high, p_low = prev['high'], prev['low']

                if ltp > p_high:
                    if (self.last_signal_candle_time[tf] != candle_time) or (self.last_signal_direction[tf] != "BUY"):
                        self.last_signal_candle_time[tf] = candle_time
                        self.last_signal_direction[tf] = "BUY"
                        target, sl = ltp * 1.012, ltp * 0.994
                        self.active_trade[tf] = {"entry_time": candle_time, "entry": ltp, "sl": sl, "tp": target, "side": "BUY"}
                        box = generate_box("BINANCE", "Crypto Fix V86.1", self.symbol, tf, "C.BUY (CALL) [🟢]", ltp, sl, target, ltp, "[🟢 High Breakout]", "[🔥 Momentum Grab]", "RUNNING")
                        send_telegram(box, f"🚀 *Binance Buy Signal: {self.symbol} ({tf})* 🚀")

                elif ltp < p_low:
                    if (self.last_signal_candle_time[tf] != candle_time) or (self.last_signal_direction[tf] != "SELL"):
                        self.last_signal_candle_time[tf] = candle_time
                        self.last_signal_direction[tf] = "SELL"
                        target, sl = ltp * 0.988, ltp * 1.006
                        self.active_trade[tf] = {"entry_time": candle_time, "entry": ltp, "sl": sl, "tp": target, "side": "SELL"}
                        box = generate_box("BINANCE", "Crypto Fix V86.1", self.symbol, tf, "P.BUY (PUT) [🔴]", ltp, sl, target, ltp, "[🔴 Low Breakdown]", "[💥 Crash Grab]", "RUNNING")
                        send_telegram(box, f"💥 *Binance Sell Signal: {self.symbol} ({tf})* 💥")
            except: pass

# ==========================================
# THREAD RUNNERS
# ==========================================
nse_watch = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS"]
crypto_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]

def run_nse_bot(ticker):
    bot = IndianNseEngine(ticker)
    while True:
        bot.scan()
        time.sleep(3)

def run_crypto_bot(symbol):
    bot = BinanceCryptoEngine(symbol)
    while True:
        bot.scan()
        time.sleep(3)

for ticker in nse_watch:
    Thread(target=run_nse_bot, args=(ticker,), daemon=True).start()

for sym in crypto_symbols:
    Thread(target=run_crypto_bot, args=(sym,), daemon=True).start()

try:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": "⚡ Daya Master V86.1 NSE & Binance High/Low Fix Engine Live!"}, timeout=5)
except: pass

if __name__ == "__main__":
    run_web_server()
