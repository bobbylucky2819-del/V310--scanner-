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
def home(): return "Daya SMC V77.0 Ultimate All-Crypto Matrix Active"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- SYSTEM SETTINGS ---
TELEGRAM_BOT_TOKEN = "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4"
TELEGRAM_CHAT_ID   = "-1004423772510"
IST = pytz.timezone('Asia/Kolkata')

class DayaSMCV77UltimateEngine:
    def __init__(self, symbol, yahoo_ticker, market_type):
        self.symbol = symbol
        self.yahoo_ticker = yahoo_ticker
        self.market_type = market_type
        self.daily_high = None
        self.daily_low = None
        self.last_daily_update = None
        self.last_trigger_time = {"15m": None, "1h": None, "2h": None, "3h": None, "4h": None}
        self.last_trigger_side = {"15m": "", "1h": "", "2h": "", "3h": "", "4h": ""}

    def check_market_timing(self):
        if self.market_type == 'CRYPTO': return True
        if self.market_type == 'FOREX':
            return datetime.datetime.now(IST).weekday() < 5
        now = datetime.datetime.now(IST)
        if now.weekday() >= 5: return False
        return 915 <= (now.hour * 100 + now.minute) <= 1530

    def update_daily_benchmarks(self, ticker):
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
            f"│  Daya SMC -> Ultimate All-Crypto V77.0      │\n"
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
        now_time = datetime.datetime.now(IST)
        
        intraday_tfs = {"15m": 15, "1h": 60, "2h": 120, "3h": 180, "4h": 240}
        ticker = yf.Ticker(self.yahoo_ticker)
        
        today = datetime.datetime.now(IST).date()
        if (self.daily_high is None or self.last_daily_update != today) and self.market_type == 'CRYPTO':
            self.update_daily_benchmarks(ticker)

        for tf, minutes in intraday_tfs.items():
            try:
                # 30-Seconds Pre-Close Filter Logic
                current_minute_offset = now_time.minute % minutes if minutes < 60 else (now_time.hour * 60 + now_time.minute) % minutes
                current_second = now_time.second
                is_30s_window = (current_minute_offset == (minutes - 1)) and (current_second >= 30)
                
                interval_str = "15m" if tf == "15m" else "1h"
                df = ticker.history(period="3d" if tf == "15m" else "7d", interval=interval_str)
                if df.empty or len(df) < 7: continue

                multiplier = 1 if tf in ["15m", "1h"] else (2 if tf == "2h" else (3 if tf == "3h" else 4))
                
                live_close = df['Close'].iloc[-1]
                live_high = df['High'].iloc[-1]
                live_low = df['Low'].iloc[-1]
                
                # Lookback 5 blocks for structural evaluation
                structure_high = df['High'].iloc[-5 - multiplier:-1].max()
                structure_low = df['Low'].iloc[-5 - multiplier:-1].min()

                # Low-Momentum Choppy Filter
                candle_range = abs(live_high - live_low)
                avg_range = (df['High'] - df['Low']).tail(10).mean()
                if candle_range < (avg_range * 0.38): continue

                # Continuous Structural Break Triggers
                c_buy_momentum = (live_close > structure_high)
                p_buy_momentum = (live_close < structure_low)

                # Daily High/Low Break Tag [MATRIX EXTRA]
                extra_tag = ""
                if self.daily_high and self.daily_low:
                    if live_low < self.daily_low or live_high > self.daily_high:
                        extra_tag = " [🔥 MATRIX EXTRA]"

                current_candle_time = df.index[-1]

                if c_buy_momentum:
                    if self.last_trigger_time[tf] != current_candle_time or self.last_trigger_side[tf] != "BUY":
                        self.last_trigger_time[tf] = current_candle_time
                        self.last_trigger_side[tf] = "BUY"
                        
                        mbs_status = "[🟢 30s Orderflow Lock]" if is_30s_window else "[🟢 Structure Break High]"
                        mrs_status = "[🔥 Advance Volume Grabbed]" if is_30s_window else "[🔥 Continuous Call Ride]"
                        
                        target = live_close * 1.018 if self.market_type == 'CRYPTO' else (live_close * 1.012 if self.market_type == 'IN' else live_close + 0.0035)
                        sl = live_close * 0.992 if self.market_type == 'CRYPTO' else (live_close * 0.994 if self.market_type == 'IN' else live_close - 0.0014)
                        label = f"C.BUY (CALL) [🟢]{extra_tag}"
                        
                        box = self.generate_live_box_string(tf, label, live_close, sl, target, live_close, mbs_status, mrs_status, "RUNNING")
                        self.send_telegram_matrix(box, f"🚀 *Daya Master: {tf} {label} ({self.symbol})* 🚀")

                elif p_buy_momentum:
                    if self.last_trigger_time[tf] != current_candle_time or self.last_trigger_side[tf] != "SELL":
                        self.last_trigger_time[tf] = current_candle_time
                        self.last_trigger_side[tf] = "SELL"
                        
                        mbs_status = "[🔴 30s Orderflow Lock]" if is_30s_window else "[🔴 Structure Break Low]"
                        mrs_status = "[💥 Advance Volume Grabbed]" if is_30s_window else "[💥 Continuous Put Ride]"
                        
                        target = live_close * 0.982 if self.market_type == 'CRYPTO' else (live_close * 0.988 if self.market_type == 'IN' else live_close - 0.0035)
                        sl = live_close * 1.008 if self.market_type == 'CRYPTO' else (live_close * 1.006 if self.market_type == 'IN' else live_close + 0.0014)
                        label = f"P.BUY (PUT) [🔴]{extra_tag}"
                        
                        box = self.generate_live_box_string(tf, label, live_close, sl, target, live_close, mbs_status, mrs_status, "RUNNING")
                        self.send_telegram_matrix(box, f"💥 *Daya Master: {tf} {label} ({self.symbol})* 💥")
                        
            except Exception as e:
                print(f"Matrix loop fault on {tf} {self.symbol}: {e}")

# --- EXPANDED ALL-CRYPTO WATCHLIST ---
crypto_watch = [
    DayaSMCV77UltimateEngine("BTC-USDT", "BTC-USD", "CRYPTO"),
    DayaSMCV77UltimateEngine("ETH-USDT", "ETH-USD", "CRYPTO"),
    DayaSMCV77UltimateEngine("SOL-USDT", "SOL-USD", "CRYPTO"),
    DayaSMCV77UltimateEngine("XRP-USDT", "XRP-USD", "CRYPTO"),
    DayaSMCV77UltimateEngine("BNB-USDT", "BNB-USD", "CRYPTO"),
    DayaSMCV77UltimateEngine("ADA-USDT", "ADA-USD", "CRYPTO"),
    DayaSMCV77UltimateEngine("DOT-USDT", "DOT-USD", "CRYPTO"),
    DayaSMCV77UltimateEngine("DOGE-USDT", "DOGE-USD", "CRYPTO"),
    DayaSMCV77UltimateEngine("MATIC-USDT", "MATIC-USD", "CRYPTO"),
    DayaSMCV77UltimateEngine("LTC-USDT", "LTC-USD", "CRYPTO")
]

indian_forex_watch = [
    DayaSMCV77UltimateEngine("RELIANCE", "RELIANCE.NS", "IN"), DayaSMCV77UltimateEngine("TCS", "TCS.NS", "IN"),
    DayaSMCV77UltimateEngine("HDFCBANK", "HDFCBANK.NS", "IN"), DayaSMCV77UltimateEngine("INFY", "INFY.NS", "IN"),
    DayaSMCV77UltimateEngine("ICICIBANK", "ICICIBANK.NS", "IN"), DayaSMCV77UltimateEngine("EURUSD", "EURUSD=X", "FOREX")
]

def start_indian_forex_loop():
    while True:
        for engine in indian_forex_watch: engine.execute_logic()
        time.sleep(4)

def start_crypto_loop():
    while True:
        for engine in crypto_watch: engine.execute_logic()
        time.sleep(4)

Thread(target=start_indian_forex_loop, daemon=True).start()
Thread(target=start_crypto_loop, daemon=True).start()

try:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": "🤖 Daya SMC Ultimate Engine V77.0 All-Crypto Matrix Locked & Active!"}, timeout=5)
except: pass

if __name__ == "__main__":
    run_web_server()
        
