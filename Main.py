import os
import time
import requests

TELEGRAM_BOT_TOKEN = "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4"
TELEGRAM_CHAT_ID   = "-1004423772510"

class DayaMasterIntegratedMatrix:
    def __init__(self, symbol, timeframe):
        self.symbol = symbol
        self.timeframe = timeframe
        self.state = 0  
        self.entry_price = 0.0
        self.target_price = 0.0
        self.stop_loss = 0.0
        self.peak_price = 0.0
        self.entry_timestamp = 0
        self.mbs_status = "[ ]"
        self.mrs_status = "[ ]"
        self.live_msg_id = None  

    def send_telegram_matrix(self, box_str, text_msg, update_existing=False):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
        escaped_box = box_str.replace('.', '\\.').replace('-', '\\-').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('|', '\\|')
        formatted_text = f"{text_msg}\n\n```text\n{escaped_box}\n```"
        if update_existing and self.live_msg_id:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
            try: requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "message_id": self.live_msg_id, "text": formatted_text, "parse_mode": "MarkdownV2"}, timeout=5); return
            except: pass
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            res = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": formatted_text, "parse_mode": "MarkdownV2"}, timeout=5).json()
            if res.get("ok"): self.live_msg_id = res["result"]["message_id"]
        except: pass

    def generate_live_box_string(self, ltp, time_run_mins, final_pnl_str):
        return (
            f"┌──────────────────────────────────────────────┐\n"
            f"│ 🟢 greendot running: {self.symbol:<7} [{self.timeframe:<3}]         │\n"
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

    def execute_tick_runtime(self, ltp, anchored_vwap, highest_high_7, ATR, volume, volume_ma_20, is_sideways, three_candle_confirm, delta_breakout, s_r_breakout):
        if is_sideways and self.state == 0: return
        if (ltp > highest_high_7) and (ltp > anchored_vwap) and (volume > (volume_ma_20 * 1.8)) and delta_breakout and three_candle_confirm and s_r_breakout and (self.state == 0):
            self.state = 1
            self.entry_price = ltp
            self.peak_price = ltp
            self.target_price = ltp + 50.0  
            self.stop_loss = ltp - 20.0     
            self.entry_timestamp = time.time()
            self.mbs_status, self.mrs_status = "[🟢 Green Dot Active]", "[Monitoring]"
            self.send_telegram_matrix(self.generate_live_box_string(ltp, 0, "PROFIT/LOSS RUNNING"), f"🚀 *NEW LIVE SIGNAL ENTRY TRIGGERED ({self.timeframe})* 🚀", False); return
        if self.state == 1:
            self.peak_price = max(ltp, self.peak_price)
            time_run_mins = int((time.time() - self.entry_timestamp) // 60)
            current_diff = ltp - self.entry_price
            if ltp >= self.target_price or (self.peak_price - ltp >= 3.0) or ltp <= self.stop_loss:
                if ltp >= self.target_price: self.mbs_status, result_str, msg = "[✅ Target Hit Blocked]", f"PROFIT: +{self.target_price - self.entry_price:.2f}", f"💰 *TRADE CLOSED: TARGET CONFIRMED HIT ({self.timeframe})* 💰"
                elif (self.peak_price - ltp >= 3.0): self.mrs_status, result_str, msg = "[✅ Reversal Closed]", f"PROFIT: +{current_diff:.2f}" if current_diff >= 0 else f"LOSS: {current_diff:.2f}", f"⚠️ *TRADE CLOSED: MRS REVERSAL HIT ({self.timeframe})* ⚠️"
                else: self.mbs_status, result_str, msg = "[❌ Stop Loss Hit]", f"LOSS: {self.stop_loss - self.entry_price:.2f}", f"🚨 *TRADE CLOSED: STOPLOSS DETECTED ({self.timeframe})* 🚨"
                self.send_telegram_matrix(self.generate_live_box_string(ltp, time_run_mins, result_str), msg, True)
                self.state, self.live_msg_id = 0, None
            else:
                self.send_telegram_matrix(self.generate_live_box_string(ltp, time_run_mins, f"PROFIT: +{current_diff:.2f}" if current_diff >= 0 else f"LOSS: {current_diff:.2f}"), f"⏳ *TRADING REALTIME MONITORING ACTIVE ({self.timeframe})* ⏳", True)

if __name__ == "__main__":
    # Exact mapping formatting arrays fix: 2h, 3h, 4h clean text setup
    tfs = ["15m", "30m", "1h", "2h", "3h", "4h", "1d"]
    assets = ["RELIANCE", "TCS", "EURUSD", "GBPUSD"]
    matrix = {a: {t: DayaMasterIntegratedMatrix(a, t) for t in tfs} for a in assets}
    while True:
        for a in assets:
            for t in tfs: matrix[a][t].execute_tick_runtime(105.0, 98.0, 99.0, 5.0, 50000, 20000, False, True, True, True)
        time.sleep(60)
