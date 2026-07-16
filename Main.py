import os
import time
import datetime
import requests
from threading import Thread
from flask import Flask

try:
    import yfinance as yf
except ImportError:
    os.system('pip install yfinance')
    import yfinance as yf

# --- FLASK PORT BINDER FOR RENDER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Daya SMC Engine V62 Active"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- SYSTEM SETTINGS ---
TELEGRAM_BOT_TOKEN = "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4"
TELEGRAM_CHAT_ID   = "-1004423772510"

class DayaSMCUltimateEngine:
    def __init__(self, symbol, yahoo_ticker):
        self.symbol = symbol
        self.yahoo_ticker = yahoo_ticker
        self.state = 0  # 0 = FLAT, 1 = BUY, -1 = SELL
        self.entry_price = 0.0
        self.target_price = 0.0
        self.stop_loss = 0.0
        self.entry_timestamp = 0
        self.side = ""
        self.mbs_status = "[ ]"
        self.mrs_status = "[ ]"
        self.live_msg_id = None
        self.is_forex = yahoo_ticker.endswith("=X") or "-" in symbol

    def check_market_timing(self):
        """
        💸 IND vs FOREX Timing Block Filter
        """
        now = datetime.datetime.now()
        if self.is_forex:
            return True # Forex/Crypto running 24/7
        # Indian Market Timing Strict Check (Mon-Fri, 9:15 AM to 3:30 PM)
        if now.weekday() >= 5: return False
        current_time_int = now.hour * 100 + now.minute
        return 915 <= current_time_int <= 1530

    def generate_live_box_string(self, ltp, time_run_mins, final_pnl_str):
        return (
            f"┌──────────────────────────────────────────────┐\n"
            f"│ 🟢 greendot running: {self.symbol:<7}                     │\n"
            f"│ 📈 Direction       : {self.side:<24} │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│  my box -> Live trading (indian/forex)       │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🪙 Start  — {self.entry_price:<6.2f}  →  🛑 Stop loss — {self.stop_loss:<5.2f} │\n"
            f"│ 🎯 Target — {self.target_price:<6.2f}                           │\n"
            f"│ 📈 Live   — {ltp:<6.2f}                             │\n"
            f"│ ⏰ Time   — [{time_run_mins:<2}m] -- 60m Scale               │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🟢 M.B.S. — {self.mbs_status:<32} │\n"
            f"│ ⚠️ M.R.S. — {self.mrs_status:<32} │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🏁 final  → {final_pnl_str:<32} │\n"
            f"└──────────────────────────────────────────────┘"
        )

    def send_telegram_matrix(self, box_str, text_msg, update_existing=False):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
        escaped_box = box_str.replace('.', '\\.').replace('-', '\\-').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('|', '\\|')
        formatted_text = f"{text_msg}\n\n```text\n{escaped_box}\n```"
        
        if update_existing and self.live_msg_id:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
            try:
                requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "message_id": self.live_msg_id, "text": formatted_text, "parse_mode": "MarkdownV2"}, timeout=5)
                return
            except: pass
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            res = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": formatted_text, "parse_mode": "MarkdownV2"}, timeout=5).json()
            if res.get("ok"): self.live_msg_id = res["result"]["message_id"]
        except: pass

    def execute_logic(self):
        if not self.check_market_timing(): return
        
        try:
            ticker = yf.Ticker(self.yahoo_ticker)
            df = ticker.history(period="3d", interval="15m")
            if df.empty or len(df) < 5: return
            
            # 1. Price Action Variables
            ltp = df['Close'].iloc[-1]
            current_vol = df['Volume'].iloc[-1]
            
            # 2. Before Day High / Day Low Markings
            prev_day_df = ticker.history(period="2d", interval="1d")
            if len(prev_day_df) < 2: return
            pdh = prev_day_df['High'].iloc[-2]
            pdl = prev_day_df['Low'].iloc[-2]
            
            # 3. Anchor VWAP & Volume Profile POC (Math Estimations)
            avg_volume = df['Volume'].mean()
            poc_price = df['Close'].rolling(window=4).mean().iloc[-1]
            anchored_vwap = (df['Close'] * df['Volume']).sum() / df['Volume'].sum()
            
            # 4. Delta Volume Trigger
            delta_volume = current_vol / (avg_volume if avg_volume > 0 else 1)
            delta_volume_breakout = delta_volume > 1.8
            
            # 5. Accumulation & Manipulation Engine
            is_accumulation = df['High'].tail(4).max() - df['Low'].tail(4).min() < (ltp * 0.003)
            liquidity_grab_buy = (df['Low'].iloc[-2] < pdl or ltp < pdl) and ltp > anchored_vwap
            liquidity_grab_sell = (df['High'].iloc[-2] > pdh or ltp > pdh) and ltp < anchored_vwap
            
            # --- SMC TRIGGER MAPPING ---
            buy_trigger = (liquidity_grab_buy and delta_volume_breakout and not is_accumulation and self.state == 0)
            sell_trigger = (liquidity_grab_sell and delta_volume_breakout and not is_accumulation and self.state == 0)
            
            if buy_trigger:
                self.state = 1
                self.side = "BUY / CALL SIDE"
                self.entry_price = ltp
                self.target_price = ltp + (0.0050 if self.is_forex else 50.0)
                self.stop_loss = ltp - (0.0020 if self.is_forex else 20.0)
                self.entry_timestamp = time.time()
                self.mbs_status = "[🟢 Green Dot Active]"
                self.mrs_status = "[🔥 OrderFlow Injection]"
                self.send_telegram_matrix(self.generate_live_box_string(ltp, 0, "RUNNING"), f"🚀 *SMC LIQUIDITY GRAB BUY TRIGGERED ({self.symbol})* 🚀", False)
                return

            elif sell_trigger:
                self.state = -1
                self.side = "PUT SIDE / C.SEL"
                self.entry_price = ltp
                self.target_price = ltp - (0.0050 if self.is_forex else 50.0)
                self.stop_loss = ltp + (0.0020 if self.is_forex else 20.0)
                self.entry_timestamp = time.time()
                self.mbs_status = "[🔴 Red Dot Active]"
                self.mrs_status = "[💥 Manipulation Hunt]"
                self.send_telegram_matrix(self.generate_live_box_string(ltp, 0, "RUNNING"), f"💥 *SMC LIQUIDITY GRAB PUT TRIGGERED ({self.symbol})* 💥", False)
                return

            # --- MONITORING LOOP LOOP ---
            if self.state != 0:
                time_run_mins = int((time.time() - self.entry_timestamp) // 60)
                current_diff = (ltp - self.entry_price) if self.state == 1 else (self.entry_price - ltp)
                
                target_hit = (ltp >= self.target_price) if self.state == 1 else (ltp <= self.target_price)
                stop_hit = (ltp <= self.stop_loss) if self.state == 1 else (ltp >= self.stop_loss)
                
                if target_hit or stop_hit:
                    if target_hit:
                        self.mbs_status = "[✅ Distribution Complete]"
                        res_str = f"PROFIT: +{current_diff:.2f}"
                        msg = f"💰 *SMC TARGET DISTRIBUTED ({self.symbol})* 💰"
                    else:
                        self.mbs_status = "[❌ Breakout Faileded]"
                        res_str = f"LOSS: {current_diff:.2f}"
                        msg = f"🚨 *SMC STOPLOSS HIT IN HUNT ({self.symbol})* 🚨"
                    
                    self.send_telegram_matrix(self.generate_live_box_string(ltp, time_run_mins, res_str), msg, True)
                    self.state, self.live_msg_id = 0, None
                else:
                    pnl_live = f"PROFIT: +{current_diff:.2f}" if current_diff >= 0 else f"LOSS: {current_diff:.2f}"
                    self.send_telegram_matrix(self.generate_live_box_string(ltp, time_run_mins, pnl_live), f"⏳ *TRADING REALTIME MONITORING ({self.symbol})* ⏳", True)
                    
        except Exception as e:
            print(f"SMC Execution Scan Error: {e}")

if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True).start()
    
    # Target Major Vectors Scanners Setup (.NS is Indian market NSE)
    matrix_watch = [
        DayaSMCUltimateEngine("RELIANCE", "RELIANCE.NS"),
        DayaSMCUltimateEngine("SBIN", "SBIN.NS"),
        DayaSMCUltimateEngine("TCS", "TCS.NS"),
        DayaSMCUltimateEngine("INFY", "INFY.NS"),
        DayaSMCUltimateEngine("EURUSD", "EURUSD=X"),
        DayaSMCUltimateEngine("BTC-USD", "BTC-USD")
    ]
    
    print("Daya Master V62 Architecture Systems Online.")
    while True:
        for engine in matrix_watch:
            engine.execute_logic()
        time.sleep(30) # Scans every 30 seconds smoothly
