import os
import time
import datetime
import requests
from threading import Thread
from flask import Flask

app = Flask(__name__)
@app.route('/')
def home(): return "Daya Master V85.0 Binance Direct Engine Active"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- TELEGRAM CONFIG ---
TELEGRAM_BOT_TOKEN = "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4"
TELEGRAM_CHAT_ID   = "-1004423772510"

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
# BINANCE DIRECT API CRYPTO ENGINE (DIRECT RESULT)
# ==========================================
class BinanceCryptoEngine:
    def __init__(self, symbol):
        self.symbol = symbol # e.g. BTCUSDT
        self.active_trade = {"15m": None, "1h": None, "4h": None}
        self.last_trigger_time = {"15m": None, "1h": None, "4h": None}

    def fetch_binance_klines(self, interval, limit=20):
        # Direct official Binance Public Klines Endpoint
        url = f"https://api.binance.com/api/v3/klines?symbol={self.symbol}&interval={interval}&limit={limit}"
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                # Parse OHLCV
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
        except Exception as e:
            print(f"Binance API fetch error on {self.symbol}: {e}")
        return []

    def scan(self):
        tf_map = {"15m": "15m", "1h": "1h", "4h": "4h"}
        
        for tf, b_interval in tf_map.items():
            try:
                klines = self.fetch_binance_klines(b_interval, limit=20)
                if len(klines) < 5: continue

                curr = klines[-1]   # Running Candle
                prev = klines[-2]   # Immediate Closed Candle

                ltp = curr['close']
                live_open = curr['open']
                candle_time = curr['open_time']

                # --- 1. LIVE TARGET / MRS REVERSAL PROTECTION ---
                if self.active_trade[tf]:
                    trade = self.active_trade[tf]
                    # Target Hit
                    if (trade["side"] == "BUY" and ltp >= trade["tp"]) or (trade["side"] == "SELL" and ltp <= trade["tp"]):
                        box = generate_box("BINANCE", "Binance Direct V85", self.symbol, tf, trade["side"]+" LOCKED", trade["entry"], trade["sl"], trade["tp"], ltp, "[🟢 Target Cleared]", "[🔥 PROFIT SECURED CLEAN]", "PROFIT LOCKED ✅")
                        send_telegram(box, f"💰 *Crypto Target Cleared: {self.symbol} ({tf})* 💰")
                        self.active_trade[tf] = None
                        continue

                    # MRS Reversal (Opposite Candle Close Exit)
                    if (trade["side"] == "BUY" and ltp < live_open) or (trade["side"] == "SELL" and ltp > live_open):
                        box = generate_box("BINANCE", "Binance Direct V85", self.symbol, tf, "MRS EXIT", trade["entry"], trade["sl"], trade["tp"], ltp, "[⚠️ Reversal Detected]", "[🚨 MRS RESCUE EXIT]", "EXITED")
                        send_telegram(box, f"⚠️ *Crypto MRS Rescue: {self.symbol} ({tf})* ⚠️")
                        self.active_trade[tf] = None
                        continue

                # --- 2. FAST 1-BAR BREAKOUT & REVERSAL SCANS ---
                p_high, p_low = prev['high'], prev['low']
                p_open, p_close = prev['open'], prev['close']

                # Green Momentum Breakout (C.BUY)
                if (ltp > p_high or (p_close < p_open and ltp > live_open)) and self.last_trigger_time[tf] != candle_time:
                    self.last_trigger_time[tf] = candle_time
                    target, sl = ltp * 1.012, ltp * 0.994
                    self.active_trade[tf] = {"entry_time": candle_time, "entry": ltp, "sl": sl, "tp": target, "side": "BUY"}
                    box = generate_box("BINANCE", "Binance Direct V85", self.symbol, tf, "C.BUY (CALL) [🟢]", ltp, sl, target, ltp, "[🟢 Live Binance Stream]", "[🔥 Momentum Grab]", "RUNNING")
                    send_telegram(box, f"🚀 *Binance Buy Signal: {self.symbol} ({tf})* 🚀")

                # Red Momentum Breakdown (P.BUY)
                elif (ltp < p_low or (p_close > p_open and ltp < live_open)) and self.last_trigger_time[tf] != candle_time:
                    self.last_trigger_time[tf] = candle_time
                    target, sl = ltp * 0.988, ltp * 1.006
                    self.active_trade[tf] = {"entry_time": candle_time, "entry": ltp, "sl": sl, "tp": target, "side": "SELL"}
                    box = generate_box("BINANCE", "Binance Direct V85", self.symbol, tf, "P.BUY (PUT) [🔴]", ltp, sl, target, ltp, "[🔴 Live Binance Stream]", "[💥 Crash Grab]", "RUNNING")
                    send_telegram(box, f"💥 *Binance Sell Signal: {self.symbol} ({tf})* 💥")

            except Exception as e:
                print(f"Error processing {self.symbol} {tf}: {e}")

# ==========================================
# THREAD RUNNER
# ==========================================
crypto_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]

def run_crypto_bot(symbol):
    bot = BinanceCryptoEngine(symbol)
    while True:
        bot.scan()
        time.sleep(3) # 3-Second High-Speed Direct Binance Fetching

# Launch Threads
for sym in crypto_symbols:
    Thread(target=run_crypto_bot, args=(sym,), daemon=True).start()

try:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": "⚡ Daya Master V85.0 Binance Direct Engine Live & Ready!"}, timeout=5)
except: pass

if __name__ == "__main__":
    run_web_server()
