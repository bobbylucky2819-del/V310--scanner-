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
def home(): return "Daya SMC V71.0 Ultimate Matrix Active"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- SYSTEM SETTINGS ---
TELEGRAM_BOT_TOKEN = "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4"
TELEGRAM_CHAT_ID   = "-1004423772510"
IST = pytz.timezone('Asia/Kolkata')

class DayaSMCV71Engine:
    def __init__(self, symbol, yahoo_ticker, market_type):
        self.symbol = symbol
        self.yahoo_ticker = yahoo_ticker
        self.market_type = market_type
        # Backend tracking variables for Daily High/Low
        self.daily_high = None
        self.daily_low = None
        self.last_daily_update = None
        # Track triggers to catch every fresh hourly setup
        self.triggered_states = {"15m": "", "1h": "", "2h": "", "3h": "", "4h": ""}

    def check_market_timing(self):
        if self.market_type == 'CRYPTO': return True
        if self.market_type == 'FOREX':
            return datetime.datetime.now(IST).weekday() < 5
        now = datetime.datetime.now(IST)
        if now.weekday() >= 5: return False
        return 915 <= (now.hour * 100 + now.minute) <= 1530

    def update_daily_benchmarks(self, ticker):
        """Runs purely in the background to cache historical daily filter metrics"""
        try:
            day_df = ticker.history(period="3d", interval="1d")
            if not day_df.empty and len(day_df) >= 2:
                self.daily_high = day_df['High'].iloc[-2]
                self.daily_low = day_df['Low'].iloc[-2]
                self.last_daily_update = datetime.datetime.now(IST).date()
        except: pass

    def generate_live_box_string(self, tf, side, entry, sl, tp, ltp, mbs, mrs, res_str):
        fmt = "6.4f" if self.market_type == 'FOREX' else "6.2f"
        return (
            f"┌──────────────────────────────────────────────┐\n"
            f"│ 🟢 Running: {self.symbol:<7} [{tf:<3} TF]                 │\n"
            f"│ 📈 Direction       : {side:<24} │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│  Daya SMC -> Ultimate Unlocked V71           │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🪙 Start  — {entry:<{fmt}}  →  🛑 Stop loss — {sl:<{fmt}} │\n"
            f"│ 🎯 Target — {tp:<{fmt}}                           │\n"
            f"│ 📈 Live   — {ltp:<{fmt}}                             │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🟢 M.B.S. — {mbs:<32} │\n"
            f"│ ⚠️ M.R.S. — {mrs:<32} │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🏁 Final  → {res_str:<32} │\n"
            f"└──────────────────────────────────────────────┘"
        )

    def send_telegram_matrix(self, box_str, text_msg):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
        escaped_box = box_str.replace('.', '\\.').replace('-', '\\-').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('|', '\\|')
        formatted_text = f"{text_msg}\n\n```text\n{escaped_box}\n```"
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        try: requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": formatted_text, "parse_mode": "MarkdownV2"}, timeout=5)
        except: pass

    def execute_logic(self):
        if not self.check_market_timing(): return
        ticker = yf.Ticker(self.yahoo_ticker)
        
        today = datetime.datetime.now(IST).date()
        if self.daily_high is None or self.last_daily_update != today:
            self.update_daily_benchmarks(ticker)

        # Precise independent tracking for hourly intervals to secure consistent target profits
        intraday_tfs = {"15m": ("15m", 15), "1h": ("1h", 24), "2h": ("1h", 48), "3h": ("1h", 72), "4h": ("1h", 96)}
        
        for tf, (interval, lookback) in intraday_tfs.items():
            try:
                df = ticker.history(period="2d" if tf == "15m" else "5d", interval=interval)
                if df.empty or len(df) < (lookback + 2): continue
                
                live_high = df['High'].iloc[-1]
                live_low = df['Low'].iloc[-1]
                live_close = df['Close'].iloc[-1]
                
                # Independent Timeframe Swing Structure (Pure Price Action Chart Rules)
                tf_high = df['High'].iloc[-lookback:-1].max()
                tf_low = df['Low'].iloc[-lookback:-1].min()

                # Core Signals: High/Low cross via Real-time Candle Wicks
                sweep_buy = (live_low < tf_low) and (live_close > tf_low)
                break_buy = (live_close > tf_high)
                
                sweep_sell = (live_high > tf_high) and (live_close < tf_high)
                break_sell = (live_close < tf_low)

                # --- BACKEND DAILY RUN OPTIONAL FILTER ---
                extra_tag = ""
                if self.daily_high and self.daily_low:
                    if live_low < self.daily_low or live_high > self.daily_high:
                        extra_tag = " [🔥 MATRIX EXTRA]"

                if (sweep_buy or break_buy) and self.triggered_states[tf] != "BUY":
                    self.triggered_states[tf] = "BUY"
                    target = live_close * 1.012 if self.market_type != 'FOREX' else live_close + 0.0030
                    sl = live_close * 0.995 if self.market_type != 'FOREX' else live_close - 0.0012
                    label = f"GRAB BUY [🟢 +]{extra_tag}" if sweep_buy else f"MOMENTUM C.BUY [🟢]{extra_tag}"
                    
                    box = self.generate_live_box_string(tf, label, live_close, sl, target, live_close, "[🟢 Setup Active]", "[🔥 Momentum Shift]", "RUNNING")
                    self.send_telegram_matrix(box, f"🚀 *Daya SMC: {tf} {label} ({self.symbol})* 🚀")

                elif (sweep_sell or break_sell) and self.triggered_states[tf] != "SELL":
                    self.triggered_states[tf] = "SELL"
                    target = live_close * 0.988 if self.market_type != 'FOREX' else live_close - 0.0030
                    sl = live_close * 1.005 if self.market_type != 'FOREX' else live_close + 0.0012
                    label = f"GRAB PUT [🔴 +]{extra_tag}" if sweep_sell else f"MOMENTUM P.BUY [🔴]{extra_tag}"
                    
                    box = self.generate_live_box_string(tf, label, live_close, sl, target, live_close, "[🔴 Setup Active]", "[💥 Orderflow Dump]", "RUNNING")
                    self.send_telegram_matrix(box, f"💥 *Daya SMC: {tf} {label} ({self.symbol})* 💥")
                    
            except Exception as e:
                print(f"Loop error for {tf} on {self.symbol}: {e}")

# --- UNIVERSAL WATCHLIST ENGINES ---
indian_forex_watch = [
    DayaSMCV71Engine("RELIANCE", "RELIANCE.NS", "IN"), DayaSMCV71Engine("TCS", "TCS.NS", "IN"),
    DayaSMCV71Engine("HDFCBANK", "HDFCBANK.NS", "IN"), DayaSMCV71Engine("INFY", "INFY.NS", "IN"),
    DayaSMCV71Engine("ICICIBANK", "ICICIBANK.NS", "IN"), DayaSMCV71Engine("BHARTIARTL", "BHARTIARTL.NS", "IN"),
    DayaSMCV71Engine("SBIN", "SBIN.NS", "IN"), DayaSMCV71Engine("LICI", "LICI.NS", "IN"),
    DayaSMCV71Engine("ITC", "ITC.NS", "IN"), DayaSMCV71Engine("LT", "LT.NS", "IN"),
    DayaSMCV71Engine("HINDUNILVR", "HINDUNILVR.NS", "IN"), DayaSMCV71Engine("HCLTECH", "HCLTECH.NS", "IN"),
    DayaSMCV71Engine("BAJFINANCE", "BAJFINANCE.NS", "IN"), DayaSMCV71Engine("SUNPHARMA", "SUNPHARMA.NS", "IN"),
    DayaSMCV71Engine("MARUTI", "MARUTI.NS", "IN"), DayaSMCV71Engine("TATASTEEL", "TATASTEEL.NS", "IN"),
    DayaSMCV71Engine("KOTAKBANK", "KOTAKBANK.NS", "IN"), DayaSMCV71Engine("AXISBANK", "AXISBANK.NS", "IN"),
    DayaSMCV71Engine("TITAN", "TITAN.NS", "IN"), DayaSMCV71Engine("NTPC", "NTPC.NS", "IN"),
    DayaSMCV71Engine("ONGC", "ONGC.NS", "IN"), DayaSMCV71Engine("ADANIENT", "ADANIENT.NS", "IN"),
    DayaSMCV71Engine("ASIANPAINT", "ASIANPAINT.NS", "IN"), DayaSMCV71Engine("M&M", "M.NS", "IN"),
    DayaSMCV71Engine("POWERGRID", "POWERGRID.NS", "IN"), DayaSMCV71Engine("EURUSD", "EURUSD=X", "FOREX")
]

crypto_watch = [DayaSMCV71Engine("BTC-USDT", "BTC-USD", "CRYPTO")]

def start_indian_forex_loop():
    while True:
        for engine in indian_forex_watch: engine.execute_logic()
        time.sleep(3)

def start_crypto_loop():
    while True:
        for engine in crypto_watch: engine.execute_logic()
        time.sleep(3) # Super fast 3-second cycle response

Thread(target=start_indian_forex_loop, daemon=True).start()
Thread(target=start_crypto_loop, daemon=True).start()

try:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": "🤖 Daya SMC V71.0 Ultimate Unlocked Engine Active!"}, timeout=5)
except: pass

if __name__ == "__main__":
    run_web_server()
    
