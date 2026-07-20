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
def home(): return "Daya Master V84.0 Complete Engine Active"

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
    fmt = "6.4f" if "FOREX" in market_title else "6.2f"
    return (
        f"┌──────────────────────────────────────────────┐\n"
        f"│ 🏛️ {market_title:<10}: {name:<10} [{tf:<3} TF]         │\n"
        f"│ 📈 Action          : {side:<24} │\n"
        f"├──────────────────────────────────────────────┤\n"
        f"│  Daya SMC -> {version:<28} │\n"
        f"├──────────────────────────────────────────────┤\n"
        f"│ 🪙 Entry  — {entry:<{fmt}}  →  🛑 StopLoss — {sl:<{fmt}} │\n"
        f"│ 🎯 Target — {tp:<{fmt}}                           │\n"
        f"│ 📈 Price  — {ltp:<{fmt}}                           │\n"
        f"├──────────────────────────────────────────────┤\n"
        f"│ 🟢 M.B.S. — {mbs:<32} │\n"
        f"│ ⚠️ M.R.S. — {mrs:<32} │\n"
        f"├──────────────────────────────────────────────┤\n"
        f"│ 🏁 Status → {final_str:<32} │\n"
        f"└──────────────────────────────────────────────┘"
    )

# ==========================================
# CORE 1: MULTI-TIMEFRAME INDIAN MARKET ENGINE
# ==========================================
class IndianMultiTimeframeEngine:
    def __init__(self, ticker_name):
        self.ticker = ticker_name
        self.clean_name = ticker_name.replace(".NS", "")
        self.active_trade = {"15m": None, "1h": None, "2h": None, "3h": None, "4h": None}
        self.last_trigger_time = {"15m": None, "1h": None, "2h": None, "3h": None, "4h": None}
        self.prev_day_high = None
        self.prev_day_low = None

    def fetch_extremes(self):
        try:
            stock = yf.Ticker(self.ticker)
            df_day = stock.history(period="2d", interval="1d")
            if len(df_day) >= 2:
                self.prev_day_high = df_day['High'].iloc[-2]
                self.prev_day_low = df_day['Low'].iloc[-2]
        except: pass

    def scan(self):
        now = datetime.datetime.now(IST)
        if now.weekday() >= 5: return
        if not (915 <= (now.hour * 100 + now.minute) <= 1530): return

        if self.prev_day_high is None: self.fetch_extremes()
        intraday_tfs = {"15m": 15, "1h": 60, "2h": 120, "3h": 180, "4h": 240}

        for tf, minutes in intraday_tfs.items():
            try:
                # 30-Second Orderflow Lock Window Calculation
                current_minute_offset = now.minute % minutes if minutes < 60 else (now.hour * 60 + now.minute) % minutes
                is_30s_window = (current_minute_offset == (minutes - 1)) and (now.second >= 30)

                interval_str = "15m" if tf == "15m" else "1h"
                stock = yf.Ticker(self.ticker)
                df = stock.history(period="5d", interval=interval_str)
                if df.empty or len(df) < 5: continue

                ltp = df['Close'].iloc[-1]
                live_open = df['Open'].iloc[-1]
                current_candle_time = df.index[-1]

                is_top_gainer = (self.prev_day_high and ltp > self.prev_day_high)
                is_top_loser = (self.prev_day_low and ltp < self.prev_day_low)

                # --- LIVE MRS / TARGET CONTROL ---
                if self.active_trade[tf]:
                    trade = self.active_trade[tf]
                    if trade["side"] == "BUY" and ltp >= trade["tp"]:
                        box = generate_box("NSE LIVE", "NSE Breaker V84.0", self.clean_name, tf, "C.BUY [🟢]", trade["entry"], trade["sl"], trade["tp"], ltp, "[🟢 Target Cleared]", "PROFIT LOCKED ✅", "SUCCESS")
                        send_telegram(box, f"💰 *NSE Profit Secured: {self.clean_name} ({tf})* 💰")
                        self.active_trade[tf] = None
                        continue
                    elif trade["side"] == "SELL" and ltp <= trade["tp"]:
                        box = generate_box("NSE LIVE", "NSE Breaker V84.0", self.clean_name, tf, "P.BUY [🔴]", trade["entry"], trade["sl"], trade["tp"], ltp, "[🔴 Target Cleared]", "PROFIT LOCKED ✅", "SUCCESS")
                        send_telegram(box, f"💰 *NSE Profit Secured: {self.clean_name} ({tf})* 💰")
                        self.active_trade[tf] = None
                        continue

                    if len(df[df.index >= trade["entry_time"]]) >= 2:
                        last_c, last_o = df['Close'].iloc[-2], df['Open'].iloc[-2]
                        if (trade["side"] == "BUY" and last_c < last_o) or (trade["side"] == "SELL" and last_c > last_o):
                            box = generate_box("NSE LIVE", "NSE Breaker V84.0", self.clean_name, tf, trade["side"]+" EXIT", trade["entry"], trade["sl"], trade["tp"], ltp, "[⚠️ Reversal Detected]", "[🚨 MRS RESCUE EXIT]", "MARKET EXITED")
                            send_telegram(box, f"⚠️ *NSE MRS Rescue: Exited {self.clean_name} ({tf})* ⚠️")
                            self.active_trade[tf] = None
                            continue

                # --- 1-BAR BREAKOUT & ORDERFLOW LOCK ---
                p_high, p_low = df['High'].iloc[-2], df['Low'].iloc[-2]

                if (ltp > p_high) and (ltp > live_open) and (self.last_trigger_time[tf] != current_candle_time):
                    self.last_trigger_time[tf] = current_candle_time
                    target, sl = ltp * 1.010, ltp * 0.995
                    mbs_status = "[🟢 30s Orderflow Lock]" if is_30s_window else "[🟢 Fast Breakout]"
                    mrs_status = "[🔥 Top Gainer Ride]" if is_top_gainer else "[🔥 Riding Momentum]"
                    
                    self.active_trade[tf] = {"entry_time": current_candle_time, "entry": ltp, "sl": sl, "tp": target, "side": "BUY"}
                    box = generate_box("NSE LIVE", "NSE Breaker V84.0", self.clean_name, tf, "C.BUY (CALL) [🟢]", ltp, sl, target, ltp, mbs_status, mrs_status, "RUNNING")
                    send_telegram(box, f"🚀 *NSE Buy Trigger: {self.clean_name} ({tf})* 🚀")

                elif (ltp < p_low) and (ltp < live_open) and (self.last_trigger_time[tf] != current_candle_time):
                    self.last_trigger_time[tf] = current_candle_time
                    target, sl = ltp * 0.990, ltp * 1.005
                    mbs_status = "[🔴 30s Orderflow Lock]" if is_30s_window else "[🔴 Fast Breakdown]"
                    mrs_status = "[💥 Top Loser Ride]" if is_top_loser else "[💥 Riding Crash Wave]"
                    
                    self.active_trade[tf] = {"entry_time": current_candle_time, "entry": ltp, "sl": sl, "tp": target, "side": "SELL"}
                    box = generate_box("NSE LIVE", "NSE Breaker V84.0", self.clean_name, tf, "P.BUY (PUT) [🔴]", ltp, sl, target, ltp, mbs_status, mrs_status, "RUNNING")
                    send_telegram(box, f"💥 *NSE Sell Trigger: {self.clean_name} ({tf})* 💥")
            except: pass

# ==========================================
# CORE 2: MULTI-TIMEFRAME CRYPTO BOTTOM ENGINE
# ==========================================
class CryptoMultiTimeframeEngine:
    def __init__(self, symbol, yahoo_ticker):
        self.symbol = symbol
        self.yahoo_ticker = yahoo_ticker
        self.active_trade = {"15m": None, "1h": None, "2h": None, "3h": None, "4h": None}
        self.last_trigger_time = {"15m": None, "1h": None, "2h": None, "3h": None, "4h": None}

    def scan(self):
        now = datetime.datetime.now(IST)
        intraday_tfs = {"15m": 15, "1h": 60, "2h": 120, "3h": 180, "4h": 240}
        ticker = yf.Ticker(self.yahoo_ticker)

        for tf, minutes in intraday_tfs.items():
            try:
                current_minute_offset = now.minute % minutes if minutes < 60 else (now.hour * 60 + now.minute) % minutes
                is_30s_window = (current_minute_offset == (minutes - 1)) and (now.second >= 30)

                interval_str = "15m" if tf == "15m" else "1h"
                df = ticker.history(period="5d", interval=interval_str)
                if len(df) < 5: continue

                ltp, live_open = df['Close'].iloc[-1], df['Open'].iloc[-1]
                current_candle_time = df.index[-1]

                # --- LIVE TARGET & MRS PROTECTION ---
                if self.active_trade[tf]:
                    trade = self.active_trade[tf]
                    if (trade["side"] == "BUY" and ltp >= trade["tp"]) or (trade["side"] == "SELL" and ltp <= trade["tp"]):
                        box = generate_box("CRYPTO", "Bottom Rider V84.0", self.symbol, tf, trade["side"]+" LOCKED", trade["entry"], trade["sl"], trade["tp"], ltp, "[🟢 Target Cleared]", "[🔥 PROFIT SECURED CLEAN]", "PROFIT LOCKED ✅")
                        send_telegram(box, f"💰 *Crypto Target Reached: {self.symbol} ({tf})* 💰")
                        self.active_trade[tf] = None
                        continue

                    if len(df[df.index >= trade["entry_time"]]) >= 2:
                        last_c, last_o = df['Close'].iloc[-2], df['Open'].iloc[-2]
                        if (trade["side"] == "BUY" and last_c < last_o) or (trade["side"] == "SELL" and last_c > last_o):
                            box = generate_box("CRYPTO", "Bottom Rider V84.0", self.symbol, tf, "MRS EXIT", trade["entry"], trade["sl"], trade["tp"], ltp, "[⚠️ Pullback/Noise]", "[🚨 MRS RESCUE EXIT]", "EXITED")
                            send_telegram(box, f"⚠️ *Crypto MRS Rescue: {self.symbol} ({tf})* ⚠️")
                            self.active_trade[tf] = None
                            continue

                # --- BOTTOM REVERSAL MOMENTUM SCANS ---
                lowest_low, highest_high = df['Low'].tail(15).min(), df['High'].tail(15).max()
                is_at_bottom = (ltp <= (lowest_low + (highest_high - lowest_low) * 0.35))
                is_at_top = (ltp >= (highest_high - (highest_high - lowest_low) * 0.35))
                prev_c, prev_o = df['Close'].iloc[-2], df['Open'].iloc[-2]

                mbs_status = "[🟢 30s Orderflow Lock]" if is_30s_window else "[🟢 Bottom Zone Grab]"

                if is_at_bottom and (prev_c < prev_o) and (ltp > live_open) and self.last_trigger_time[tf] != current_candle_time:
                    self.last_trigger_time[tf] = current_candle_time
                    target, sl = ltp * 1.012, ltp * 0.994
                    self.active_trade[tf] = {"entry_time": current_candle_time, "entry": ltp, "sl": sl, "tp": target, "side": "BUY"}
                    box = generate_box("CRYPTO", "Bottom Rider V84.0", self.symbol, tf, "C.BUY (CALL) [🟢]", ltp, sl, target, ltp, mbs_status, "[🔥 Leaving Upper Noise]", "RUNNING")
                    send_telegram(box, f"🚀 *Crypto Bottom Buy: {self.symbol} ({tf})* 🚀")

                elif is_at_top and (prev_c > prev_o) and (ltp < live_open) and self.last_trigger_time[tf] != current_candle_time:
                    self.last_trigger_time[tf] = current_candle_time
                    target, sl = ltp * 0.988, ltp * 1.006
                    mbs_status = "[🔴 30s Orderflow Lock]" if is_30s_window else "[🔴 Top Zone Grab]"
                    self.active_trade[tf] = {"entry_time": current_candle_time, "entry": ltp, "sl": sl, "tp": target, "side": "SELL"}
                    box = generate_box("CRYPTO", "Bottom Rider V84.0", self.symbol, tf, "P.BUY (PUT) [🔴]", ltp, sl, target, ltp, mbs_status, "[💥 Leaving Lower Noise]", "RUNNING")
                    send_telegram(box, f"💥 *Crypto Top Sell: {self.symbol} ({tf})* 💥")
            except: pass

# ==========================================
# THREAD RUNNERS & BOT INIT
# ==========================================
nse_watch = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS"]
crypto_watch = [("BTC-USDT", "BTC-USD"), ("ETH-USDT", "ETH-USD"), ("SOL-USDT", "SOL-USD")]

def run_nse_thread(engine_obj):
    while True:
        engine_obj.scan()
        time.sleep(3)

def run_crypto_thread(engine_obj):
    while True:
        engine_obj.scan()
        time.sleep(10)

for ticker in nse_watch:
    obj = IndianMultiTimeframeEngine(ticker)
    Thread(target=run_nse_thread, args=(obj,), daemon=True).start()

for sym, yticker in crypto_watch:
    obj = CryptoMultiTimeframeEngine(sym, yticker)
    Thread(target=run_crypto_thread, args=(obj,), daemon=True).start()

try:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": "🤖 Daya Master V84.0 5-Timeframe Complete Engine Live!"}, timeout=5)
except: pass

if __name__ == "__main__":
    run_web_server()
                 
