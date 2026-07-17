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
def home(): return "Daya SMC Engine V65 Scalper Active"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

TELEGRAM_BOT_TOKEN = "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4"
TELEGRAM_CHAT_ID   = "-1004423772510"
IST = pytz.timezone('Asia/Kolkata')

class DayaSMCEngineV65:
    def __init__(self, symbol, yahoo_ticker):
        self.symbol = symbol
        self.yahoo_ticker = yahoo_ticker
        self.state = 0  
        self.entry_price = 0.0
        self.target_price = 0.0
        self.stop_loss = 0.0
        self.entry_timestamp = 0
        self.side = ""
        self.mbs_status = "[ ]"
        self.mrs_status = "[ ]"
        self.live_msg_id = None
        self.is_forex = yahoo_ticker.endswith("=X")
        self.is_crypto = "-USD" in yahoo_ticker

    def check_market_timing(self):
        if self.is_forex or self.is_crypto: return True
        now = datetime.datetime.now(IST)
        if now.weekday() >= 5: return False
        current_time_int = now.hour * 100 + now.minute
        return 915 <= current_time_int <= 1530

    def generate_live_box_string(self, ltp, time_run_mins, final_pnl_str):
        fmt = "6.4f" if (self.is_forex or self.is_crypto) else "6.2f"
        return (
            f"┌──────────────────────────────────────────────┐\n"
            f"│ 🟢 Running: {self.symbol:<7}                         │\n"
            f"│ 📈 Direction       : {self.side:<24} │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│  Daya SMC -> Live Trading                    │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🪙 Start  — {self.entry_price:<{fmt}}  →  🛑 Stop loss — {self.stop_loss:<{fmt}} │\n"
            f"│ 🎯 Target — {self.target_price:<{fmt}}                           │\n"
            f"│ 📈 Live   — {ltp:<{fmt}}                             │\n"
            f"│ ⏰ Time   — [{time_run_mins:<2}m] -- 60m Scale               │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🟢 M.B.S. — {self.mbs_status:<32} │\n"
            f"│ ⚠️ M.R.S. — {self.mrs_status:<32} │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🏁 Final  → {final_pnl_str:<32} │\n"
            f"└──────────────────────────────────────────────┘"
        )

    def send_telegram_matrix(self, box_str, text_msg, update_existing=False):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
        # HTML Parse Mode కోసం సేఫ్ ఫార్మాటింగ్
        formatted_text = f"{text_msg}\n\n<pre>{box_str}</pre>"
        
        if update_existing and self.live_msg_id:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
            try:
                res = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "message_id": self.live_msg_id, "text": formatted_text, "parse_mode": "HTML"}, timeout=5).json()
                if not res.get("ok"): print(f"❌ Edit Error: {res}")
                return
            except Exception as e:
                print(f"❌ Edit Exception: {e}")
                return
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            res = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": formatted_text, "parse_mode": "HTML"}, timeout=5).json()
            if res.get("ok"): 
                self.live_msg_id = res["result"]["message_id"]
            else:
                print(f"❌ Send Error: {res}")
        except Exception as e:
            print(f"❌ Send Exception: {e}")

    def execute_logic(self):
        if not self.check_market_timing(): return
        
        try:
            ticker = yf.Ticker(self.yahoo_ticker)
            df = ticker.history(period="1d", interval="1m")
            if df.empty or len(df) < 10: return
            
            ltp = df['Close'].iloc[-1]
            current_vol = df['Volume'].iloc[-1]
            
            prev_day_df = ticker.history(period="2d", interval="1d")
            if len(prev_day_df) < 2: return
            pdh = prev_day_df['High'].iloc[-2]
            pdl = prev_day_df['Low'].iloc[-2]
            
            avg_volume = df['Volume'].mean()
            anchored_vwap = (df['Close'] * df['Volume']).sum() / df['Volume'].sum() if df['Volume'].sum() > 0 else df['Close'].mean()
            
            if self.is_forex:
                delta_volume_breakout = True
            else:
                delta_volume = current_vol / (avg_volume if avg_volume > 0 else 1)
                delta_volume_breakout = delta_volume > 1.3 

            is_accumulation = df['High'].tail(3).max() - df['Low'].tail(3).min() < (ltp * 0.0015)
            
            liquidity_grab_buy = (df['Low'].iloc[-2] < pdl or ltp < pdl) and ltp > anchored_vwap
            liquidity_grab_sell = (df['High'].iloc[-2] > pdh or ltp > pdh) and ltp < anchored_vwap
            
            buy_trigger = (liquidity_grab_buy and delta_volume_breakout and not is_accumulation and self.state == 0)
            sell_trigger = (liquidity_grab_sell and delta_volume_breakout and not is_accumulation and self.state == 0)
            
            if buy_trigger:
                self.state = 1
                self.side = "BUY / CALL SIDE"
                self.entry_price = ltp
                self.target_price = ltp + (0.0025 if (self.is_forex or self.is_crypto) else 30.0)
                self.stop_loss = ltp - (0.0012 if (self.is_forex or self.is_crypto) else 12.0)
                self.entry_timestamp = time.time()
                self.mbs_status = "[🟢 Structure Break Active]"
                self.mrs_status = "[🔥 OrderFlow Injection]"
                self.send_telegram_matrix(self.generate_live_box_string(ltp, 0, "RUNNING"), f"🚀 <b>SMC LIQUIDITY GRAB BUY DETECTED ({self.symbol})</b> 🚀", False)
                return

            elif sell_trigger:
                self.state = -1
                self.side = "PUT SIDE / C.SEL"
                self.entry_price = ltp
                self.target_price = ltp - (0.0025 if (self.is_forex or self.is_crypto) else 30.0)
                self.stop_loss = ltp + (0.0012 if (self.is_forex or self.is_crypto) else 12.0)
                self.entry_timestamp = time.time()
                self.mbs_status = "[🔴 Structure Break Active]"
                self.mrs_status = "[💥 Manipulation Hunt]"
                self.send_telegram_matrix(self.generate_live_box_string(ltp, 0, "RUNNING"), f"💥 <b>SMC LIQUIDITY GRAB PUT DETECTED ({self.symbol})</b> 💥", False)
                return

            if self.state != 0:
                time_run_mins = int((time.time() - self.entry_timestamp) // 60)
                current_diff = (ltp - self.entry_price) if self.state == 1 else (self.entry_price - ltp)
                
                target_hit = (ltp >= self.target_price) if self.state == 1 else (ltp <= self.target_price)
                stop_hit = (ltp <= self.stop_loss) if self.state == 1 else (ltp >= self.stop_loss)
                
                if target_hit or stop_hit:
                    if target_hit:
                        self.mbs_status = "[✅ Distribution Complete]"
                        res_str = f"PROFIT: +{current_diff:.4f}"
                        msg = f"💰 <b>SMC TARGET DISTRIBUTED ({self.symbol})</b> 💰"
                    else:
                        self.mbs_status = "[❌ Breakout Failed]"
                        res_str = f"LOSS: {current_diff:.4f}"
                        msg = f"🚨 <b>SMC STOPLOSS HIT IN HUNT ({self.symbol})</b> 🚨"
                    
                    self.send_telegram_matrix(self.generate_live_box_string(ltp, time_run_mins, res_str), msg, True)
                    self.state, self.live_msg_id = 0, None
                else:
                    pnl_live = f"PROFIT: +{current_diff:.4f}" if current_diff >= 0 else f"LOSS: {current_diff:.4f}"
                    self.send_telegram_matrix(self.generate_live_box_string(ltp, time_run_mins, pnl_live), f"⏳ <b>TRADING REALTIME MONITORING ({self.symbol})</b> ⏳", True)
                    
        except Exception as e:
            print(f"Core Execution Exception for {self.symbol}: {e}")

if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True).start()
    
    matrix_watch = [
        DayaSMCEngineV65("RELIANCE", "RELIANCE.NS"),
        DayaSMCEngineV65("SBIN", "SBIN.NS"),
        DayaSMCEngineV65("TCS", "TCS.NS"),
        DayaSMCEngineV65("INFY", "INFY.NS"),
        DayaSMCEngineV65("EURUSD", "EURUSD=X"),
        DayaSMCEngineV65("BTC-USD", "BTC-USD")
    ]
    
    print("Daya Master V65 Engine Online.")
    while True:
        for engine in matrix_watch:
            engine.execute_logic()
        time.sleep(60) # Yahoo block అవ్వకుండా 60 సెకన్ల గ్యాప్
    
