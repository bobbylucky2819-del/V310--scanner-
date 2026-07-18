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
def home(): return "Daya SMC V67.5 Master Engine Active"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- SYSTEM SETTINGS ---
TELEGRAM_BOT_TOKEN = "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4"
TELEGRAM_CHAT_ID   = "-1004423772510"
IST = pytz.timezone('Asia/Kolkata')

class DayaSMCEngineV67:
    def __init__(self, symbol, yahoo_ticker):
        self.symbol = symbol
        self.yahoo_ticker = yahoo_ticker
        # All required Timeframes including 15m and 1d
        self.tf_states = {"15m": 0, "1h": 0, "2h": 0, "3h": 0, "4h": 0, "1d": 0}
        self.tf_msg_ids = {"15m": None, "1h": None, "2h": None, "3h": None, "4h": None, "1d": None}
        self.is_forex = yahoo_ticker.endswith("=X") or "-" in symbol

    def check_market_timing(self):
        if self.is_forex: return True
        now = datetime.datetime.now(IST)
        if now.weekday() >= 5: return False
        current_time_int = now.hour * 100 + now.minute
        return 915 <= current_time_int <= 1530

    def generate_live_box_string(self, tf, side, entry, sl, tp, ltp, mbs, mrs, res_str):
        fmt = "6.4f" if self.is_forex else "6.2f"
        return (
            f"┌──────────────────────────────────────────────┐\n"
            f"│ 🟢 Running: {self.symbol:<7} [{tf:<3} TF]                 │\n"
            f"│ 📈 Direction       : {side:<24} │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│  Daya SMC -> Ultimate Multi-TF Engine        │\n"
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

    def send_telegram_matrix(self, tf, box_str, text_msg, update_existing=False):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
        escaped_box = box_str.replace('.', '\\.').replace('-', '\\-').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('|', '\\|')
        formatted_text = f"{text_msg}\n\n```text\n{escaped_box}\n```"
        
        if update_existing and self.tf_msg_ids[tf]:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
            try:
                requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "message_id": self.tf_msg_ids[tf], "text": formatted_text, "parse_mode": "MarkdownV2"}, timeout=5)
                return
            except: return
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            res = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": formatted_text, "parse_mode": "MarkdownV2"}, timeout=5).json()
            if res.get("ok"): self.tf_msg_ids[tf] = res["result"]["message_id"]
        except: pass

    def execute_logic(self):
        if not self.check_market_timing(): return
        ticker = yf.Ticker(self.yahoo_ticker)

        # ⚡ [ENGINE 1]: 1D FRAME - DETECTS DATINNA / DATTAKA POINA (Sweep OR Momentum Breakout)
        try:
            time.sleep(1)
            day_df = ticker.history(period="10d", interval="1d")
            if not day_df.empty and len(day_df) >= 3:
                d_ltp = day_df['Close'].iloc[-1]
                pdh = day_df['High'].iloc[-2]
                pdl = day_df['Low'].iloc[-2]
                
                # Dynamic Daily Swing Limits
                d_swing_high = day_df['High'].iloc[-5:-2].max()
                d_swing_low = day_df['Low'].iloc[-5:-2].min()
                
                # Condition A: Pure Daily Sweep Case
                day_sweep_buy = (day_df['Low'].iloc[-1] < d_swing_low or day_df['Low'].iloc[-2] < d_swing_low) and d_ltp > d_swing_low
                day_sweep_sell = (day_df['High'].iloc[-1] > d_swing_high or day_df['High'].iloc[-2] > d_swing_high) and d_ltp < d_swing_high
                
                # Condition B: Pure Daily High/Low Breakout (Datinna Case)
                day_break_buy = (d_ltp > pdh)
                day_break_sell = (d_ltp < pdl)
                
                day_final_buy = day_sweep_buy or day_break_buy
                day_final_sell = day_sweep_sell or day_break_sell
                
                if self.tf_states["1d"] == 0:
                    if day_final_buy:
                        self.tf_states["1d"] = 1
                        tgt = d_ltp + (0.0050 if self.is_forex else 80.0)
                        sl = d_ltp - (0.0025 if self.is_forex else 35.0)
                        # Up green marker injected into text
                        lbl = "1D SWING BUY [🟢 +]" if day_sweep_buy else "1D BREAKOUT C.B [🟢]"
                        box = self.generate_live_box_string("1d", lbl, d_ltp, sl, tgt, d_ltp, "[🟢 Structure Break Active]", "[🔥 OrderFlow Injection]", "RUNNING")
                        self.send_telegram_matrix("1d", box, f"🚀 *SMC {lbl} ({self.symbol})* 🚀", False)
                    elif day_final_sell:
                        self.tf_states["1d"] = -1
                        tgt = d_ltp - (0.0050 if self.is_forex else 80.0)
                        sl = d_ltp + (0.0025 if self.is_forex else 35.0)
                        # Low red marker injected into text
                        lbl = "1D SWING PUT [🔴 +]" if day_sweep_sell else "1D BREAKOUT P.EXIT [🔴]"
                        box = self.generate_live_box_string("1d", lbl, d_ltp, sl, tgt, d_ltp, "[🔴 Structure Break Active]", "[💥 Manipulation Hunt]", "RUNNING")
                        self.send_telegram_matrix("1d", box, f"💥 *SMC {lbl} ({self.symbol})* 💥", False)
                else:
                    self.tf_states["1d"] = 0
                    self.tf_msg_ids["1d"] = None
        except Exception as e:
            print(f"1D Core Logic Error for {self.symbol}: {e}")

        # ⚡ [ENGINE 2]: INTRADAY TIMEFRAMES WITH 15M INCLUDED (15m, 1h, 2h, 3h, 4h)
        intraday_tfs = {
            "15m": ("15m", 16),
            "1h": ("1h", 24),
            "2h": ("1h", 48),
            "3h": ("1h", 72),
            "4h": ("1h", 96)
        }
        
        for tf, (interval, lookback) in intraday_tfs.items():
            try:
                time.sleep(1)
                # Fetch data matching required historical depth
                df = ticker.history(period="5d" if tf == "15m" else "7d", interval=interval)
                if df.empty or len(df) < (lookback + 5): continue
                
                ltp = df['Close'].iloc[-1]
                current_vol = df['Volume'].iloc[-1]
                
                # TradingView Swing Point Calculation
                swing_high = df['High'].iloc[-(lookback+2):-2].max()
                swing_low = df['Low'].iloc[-(lookback+2):-2].min()
                
                # Pure Anchored VWAP Formula Mapping
                total_pv = (df['Close'].tail(lookback) * df['Volume'].tail(lookback)).sum()
                total_v = df['Volume'].tail(lookback).sum()
                anchored_vwap = total_pv / total_v if total_v > 0 else df['Close'].mean()
                
                # Custom Delta Volume and Squeeze Filters
                avg_volume = df['Volume'].tail(lookback).mean()
                delta_volume = current_vol / (avg_volume if avg_volume > 0 else 1)
                delta_volume_breakout = True if self.is_forex else (delta_volume > 1.2)
                is_accumulation = df['High'].tail(3).max() - df['Low'].tail(3).min() < (ltp * 0.0015)
                
                # Double Chance Logic: Target Lines Multi-Fitted
                sweep_buy = (df['Low'].iloc[-2] < swing_low or df['Low'].iloc[-1] < swing_low) and ltp > swing_low
                sweep_sell = (df['High'].iloc[-2] > swing_high or df['High'].iloc[-1] > swing_high) and ltp < swing_high
                
                nosweep_buy = (ltp > swing_high) 
                nosweep_sell = (ltp < swing_low)
                
                final_buy = (sweep_buy or nosweep_buy) and ltp > anchored_vwap and delta_volume_breakout and not is_accumulation
                final_sell = (sweep_sell or nosweep_sell) and ltp < anchored_vwap and delta_volume_breakout and not is_accumulation
                
                state = self.tf_states[tf]
                
                if state == 0:
                    if final_buy:
                        self.tf_states[tf] = 1
                        target = ltp + (0.0020 if tf == "15m" else 0.0030 if self.is_forex else 25.0 if tf == "15m" else 50.0)
                        sl = ltp - (0.0010 if tf == "15m" else 0.0015 if self.is_forex else 12.0 if tf == "15m" else 20.0)
                        label = "GRAB BUY [🟢 +]" if sweep_buy else "MOMENTUM C.BUY [🟢]"
                        box = self.generate_live_box_string(tf, label, ltp, sl, target, ltp, "[🟢 Structure Break Active]", "[🔥 OrderFlow Injection]", "RUNNING")
                        self.send_telegram_matrix(tf, box, f"🚀 *SMC {tf} {label} ({self.symbol})* 🚀", False)
                    elif final_sell:
                        self.tf_states[tf] = -1
                        target = ltp - (0.0020 if tf == "15m" else 0.0030 if self.is_forex else 25.0 if tf == "15m" else 50.0)
                        sl = ltp + (0.0010 if tf == "15m" else 0.0015 if self.is_forex else 12.0 if tf == "15m" else 20.0)
                        label = "GRAB PUT [🔴 +]" if sweep_sell else "MOMENTUM P.BUY [🔴]"
                        box = self.generate_live_box_string(tf, label, ltp, sl, target, ltp, "[🔴 Structure Break Active]", "[💥 Manipulation Hunt]", "RUNNING")
                        self.send_telegram_matrix(tf, box, f"💥 *SMC {tf} {label} ({self.symbol})* 💥", False)
                else:
                    self.tf_states[tf] = 0
                    self.tf_msg_ids[tf] = None
            except Exception as e:
                print(f"Error processing {tf} for {self.symbol}: {e}")

# --- WATCHLIST CONFIGURATION ---
matrix_watch = [
    DayaSMCEngineV67("RELIANCE", "RELIANCE.NS"),
    DayaSMCEngineV67("SBIN", "SBIN.NS"),
    DayaSMCEngineV67("EURUSD", "EURUSD=X"),
    DayaSMCEngineV67("BTC-USD", "BTC-USD")
]

def start_trading_loop():
    print("🚀 Daya Master V67.5 Engine Active with 15m & 1D Logic...")
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": "🤖 Daya SMC V67.5 Core Engine Active! (15m + 1D Optimized)"}, timeout=5)
    except: pass

    while True:
        for engine in matrix_watch:
            engine.execute_logic()
            time.sleep(2)
        time.sleep(300)

Thread(target=start_trading_loop, daemon=True).start()

if __name__ == "__main__":
    run_web_server()
    
