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
def home(): return "Daya SMC V67 Ultimate Engine Active"

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
        self.tf_states = {"1h": 0, "2h": 0, "3h": 0, "4h": 0, "1d": 0}
        self.tf_msg_ids = {"1h": None, "2h": None, "3h": None, "4h": None, "1d": None}
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
            └──────────────────────────────────────────────┘"
        )

    def send_telegram_matrix(self, tf, box_str, text_msg, update_existing=False):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
        escaped_box = box_str.replace('.', '\\.').replace('-', '\\-').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('|', '\\|')
        formatted_text = f"{text_msg}\n\n```text\n{escaped_box}\n
        
