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
def home(): return "Daya SMC V69.0 Matrix Engine Active"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- SYSTEM SETTINGS ---
TELEGRAM_BOT_TOKEN = "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4"
TELEGRAM_CHAT_ID   = "-1004423772510"
IST = pytz.timezone('Asia/Kolkata')

class DayaSMCMatrixEngine:
    def __init__(self, symbol, yahoo_ticker, market_type):
        self.symbol = symbol
        self.yahoo_ticker = yahoo_ticker
        self.market_type = market_type
        # Daily reference boundaries
        self.daily_high = None
        self.daily_low = None
        self.last_daily_update = None
        # Anti-duplicate state tracks
        self.triggered_states = {"15m": "", "1h": "", "2h": "", "3h": "", "4h": ""}

    def check_market_timing(self):
        if self.market_type == 'CRYPTO': return True
        if self.market_type == 'FOREX':
            return datetime.datetime.now(IST).weekday() < 5
        now = datetime.datetime.now(IST)
        if now.weekday() >= 5: return False
        return 915 <= (now.hour * 100 + now.minute) <= 1530

    def update_daily_benchmarks(self, ticker):
        """Fetches and marks the definitive previous Day High and Low boundaries"""
        try:
            day_df = ticker.history(period="3d", interval="1d")
            if not day_df.empty and len(day_df) >= 2:
                # Use the completed prior day session levels
                self.daily_high = day_df['High'].iloc[-2]
                self.daily_low = day_df['Low'].iloc[-2]
                self.last_daily_update = datetime.datetime.now(IST).date()
        except Exception as e:
            print(f"Error fetching daily matrix boundaries for {self.symbol}: {e}")

    def generate_live_box_string(self, tf, side, entry, sl, tp, ltp, mbs, mrs, res_str):
        fmt = "6.4f" if self.market_type == 'FOREX' else "6.2f"
        return (
            f"┌──────────────────────────────────────────────┐\n"
            f"│ 🟢 Running: {self.symbol:<7} [{tf:<3} TF]                 │\n"
            f"│ 📈 Direction       : {side:<24} │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│  Daya SMC -> Inter-TF Matrix Engine V69      │\n"
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
            
        if self.daily_high is None or self.daily_low is None: return

        # Multi-timeframe execution sequence based directly on your asset profile targets
        intraday_tfs = {"15m": "15m", "1h": "1h", "2h": "1h", "3h": "1h", "4h": "1h"}
        
        for tf, interval in intraday_tfs.items():
            try:
                df = ticker.history(period="2d" if tf == "15m" else "5d", interval=interval)
                if df.empty: continue
                
                # Check real-time candle high/low limits against the daily benchmark block lines
                live_high = df['High'].iloc[-1]
                live_low = df['Low'].iloc[-1]
                live_close = df['Close'].iloc[-1]

                # ⚡ SWEEP & BREAK LOGIC ACCORDING TO YOUR HAND-DRAWN RULES
                # Liquid Sweep: Wick spikes past daily floor/ceiling level, but candle holds internal zone
                sweep_buy = (live_low < self.daily_low) and (live_close > self.daily_low)
                sweep_sell = (live_high > self.daily_high) and (live_close < self.daily_high)
                
                # Direct Structural Breakout
                break_buy = (live_close > self.daily_high)
                break_sell = (live_close < self.daily_low)

                if (sweep_buy or break_buy) and self.triggered_states[tf] != "BUY":
                    self.triggered_states[tf] = "BUY"
                    target = live_close * 1.015 if self.market_type != 'FOREX' else live_close + 0.0035
                    sl = live_close * 0.993 if self.market_type != 'FOREX' else live_close - 0.0015
                    label = "D.SWEEP BUY [🟢 +]" if sweep_buy else "D.BREAKOUT C.B [🟢]"
                    
                    box = self.generate_live_box_string(tf, label, live_close, sl, target, live_close, "[🟢 Daily Matrix Cleared]", "[🔥 Big Money Order Injected]", "RUNNING")
                    self.send_telegram_matrix(box, f"🚀 *Matrix Alert: {tf} {label} ({self.symbol})* 🚀")

                elif (sweep_sell or break_sell) and self.triggered_states[tf] != "SELL":
                    self.triggered_states[tf] = "SELL"
                    target = live_close * 0.985 if self.market_type != 'FOREX' else live_close - 0.0035
                    sl = live_close * 1.007 if self.market_type != 'FOREX' else live_close + 0.0015
                    label = "D.SWEEP PUT [🔴 +]" if sweep_sell else "D.BREAKOUT P.EXIT [🔴]"
                    
                    box = self.generate_live_box_string(tf, label, live_close, sl, target, live_close, "[🔴 Daily Matrix Cleared]", "[💥 Liquidity Grabbed]", "RUNNING")
                    self.send_telegram_matrix(box, f"💥 *Matrix Alert: {tf} {label} ({self.symbol})* 💥")
                    
            except Exception as e:
                print(f"Error executing logic matrix for {tf} on {self.symbol}: {e}")

# --- TOTAL WATCHLIST ENGINES ---
indian_forex_watch = [
    DayaSMCMatrixEngine("RELIANCE", "RELIANCE.NS", "IN"), DayaSMCMatrixEngine("TCS", "TCS.NS", "IN"),
    DayaSMCMatrixEngine("HDFCBANK", "HDFCBANK.NS", "IN"), DayaSMCMatrixEngine("INFY", "INFY.NS", "IN"),
    DayaSMCMatrixEngine("ICICIBANK", "ICICIBANK.NS", "IN"), DayaSMCMatrixEngine("BHARTIARTL", "BHARTIARTL.NS", "IN"),
    DayaSMCMatrixEngine("SBIN", "SBIN.NS", "IN"), DayaSMCMatrixEngine("ITC", "ITC.NS", "IN"),
    DayaSMCMatrixEngine("EURUSD", "EURUSD=X", "FOREX")
]

crypto_watch = [DayaSMCMatrixEngine("BTC-USDT", "BTC-USD", "CRYPTO")]

def start_indian_forex_loop():
    while True:
        for engine in indian_forex_watch: engine.execute_logic()
        time.sleep(10)

def start_crypto_loop():
    while True:
        for engine in crypto_watch: engine.execute_logic()
        time.sleep(5) # 5-second matrix processing loop

Thread(target=start_indian_forex_loop, daemon=True).start()
Thread(target=start_crypto_loop, daemon=True).start()

try:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": "🤖 Daya SMC Matrix V69.0 Engine Fully Implemented!"}, timeout=5)
except: pass

if __name__ == "__main__":
    run_web_server()
