import os
import time
import requests

# -------------------------------------------------------------
# ADVANCED RENDER / GITHUB CONFIGURATION ENGINE
# -------------------------------------------------------------
TELEGRAM_BOT_TOKEN = 8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = -1004423772510("TELEGRAM_CHAT_ID")

class DayaMasterObserverEngine:
    def __init__(self, symbol="RELIANCE", timeframe="1h"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.state = 0  # 0 = FLAT, 1 = BUY ACTIVE
        
        # Matrix Positioning Variables
        self.entry_price = 0.0
        self.target_price = 0.0
        self.stop_loss = 0.0
        self.peak_price = 0.0
        
        # Time Scales
        self.start_time = ""
        self.entry_timestamp = 0
        
        # Structural Verification Tags
        self.mbs_status = "[ ]"
        self.mrs_status = "[ ]"
        self.back_marks = "[SMC Sweep + CHOCH Valid]"

    def send_telegram_matrix(self, box_str, text_msg):
        """Sends absolute raw text representation and custom header notification directly to Telegram."""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("Error: Telegram credentials missing in Environment variables!")
            return
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        # 1. Advanced Alert Header Send
        payload_header = {"chat_id": TELEGRAM_CHAT_ID, "text": text_msg, "parse_mode": "Markdown"}
        # 2. Complete Live Execution Box Send (MarkdownV2 pre-formatted blocks code wrap)
        escaped_box = box_str.replace('.', '\\.').replace('-', '\\-').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('|', '\\|')
        payload_box = {"chat_id": TELEGRAM_CHAT_ID, "text": f"```text\n{escaped_box}\n```", "parse_mode": "MarkdownV2"}
        
        try:
            requests.post(url, json=payload_header, timeout=5)
            requests.post(url, json=payload_box, timeout=5)
        except Exception as e:
            print(f"Telegram Engine Network Delay: {e}")

    def generate_live_box_string(self, ltp, current_time_str, time_run_mins, status_str, result_str):
        """Renders the exact textual observer box structural alignment."""
        box = (
            f"┌──────────────────────────────────────────────┐\n"
            f"│        🏆 DAYA MASTER LIVE OBSERVER          │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🪙 Symbol     : {self.symbol} ({self.timeframe} Frame Engine)  │\n"
            f"│ 📅 Start Time : {self.start_time}                     │\n"
            f"│ ⏱️ Present Time: {current_time_str} [LIVE LOG]         │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 💰 Entry price: {self.entry_price:<10.2f} 🛑 Stop loss: {self.stop_loss:<10.2f}│\n"
            f"│ 🎯 Target     : {self.target_price:<10.2f} ⏳ Status   : {status_str:<10}  │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🟢 M.B.S. 🔴  : {self.mbs_status:<29}  │\n"
            f"│ ⚠️ M.R.S.      : {self.mrs_status:<29}  │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ ⏰ Time Run   : {time_run_mins:<3} Mins [1m - 60m Scale]     │\n"
            f"│ 📉 Back Marks : {self.back_marks:<29}  │\n"
            f"│ 📈 M.price live: [ {ltp:<7.2f} ]                 │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🏁 Result     : {result_str:<28} │\n"
            f"└──────────────────────────────────────────────┘"
        )
        return box

    def execute_tick_runtime(self, ltp, anchored_vwap, highest_high_7, atr, volume, volume_ma_20):
        """Pure speed condition verification logic engine loop."""
        current_time_str = time.strftime("%I:%M %p")
        
        # --- 1. BUY ENTRY TRACKING (M.B.S TRIGGER) ---
        is_high_volume_injection = volume > (volume_ma_20 * 1.8)
        buy_trigger = (ltp > highest_high_7) and (ltp > anchored_vwap) and is_high_volume_injection and (self.state == 0)
        
        if buy_trigger:
            self.state = 1
            self.entry_price = ltp
            self.peak_price = ltp
            self.target_price = ltp + (atr * 2.0)
            self.stop_loss = ltp - (atr * 1.5)
            self.start_time = current_time_str
            self.entry_timestamp = time.time()
            
            self.mbs_status = "[✅] Bullish (Green Dot)"
            self.mrs_status = "[ ]"
            
            box_output = self.generate_live_box_string(ltp, current_time_str, 0, "ACTIVE", "RUNNING MATRIX")
            alert_msg = "🔥 *ADVANCE TRADE:* NEW INITIALIZATION TRIGGERED 🔥"
            self.send_telegram_matrix(box_output, alert_msg)
            return

        # --- 2. RUNNING POSITION EVALUATION LOOP ---
        if self.state == 1:
            self.peak_price = max(ltp, self.peak_price)
            time_run_mins = int((time.time() - self.entry_timestamp) // 60)
            
            # Reversal & Boundary Condition Checks
            points_drop_from_peak = self.peak_price - ltp
            mrs_reversal_hit = points_drop_from_peak >= 3.0
            target_hit = ltp >= self.target_price
            stop_loss_hit = ltp <= self.stop_loss
            
            # --- 3. CRITICAL SINGLE-TICK CLOSE ENGINE ---
            if target_hit or mrs_reversal_hit or stop_loss_hit:
                if target_hit:
                    self.mbs_status = "[✅] Bullish (PROFIT HIT)"
                    result_str = f"{self.target_price:.2f} (TARGET DONE) ✅"
                    alert_msg = "💰 *ADVANCE TRADE CLOSED: TARGET HIT* 💰"
                elif mrs_reversal_hit:
                    self.mrs_status = "[✅] 3-Pt Reversal Triggered"
                    result_str = f"{ltp:.2f} (M.R.S. LOCKED) ✅"
                    alert_msg = "⚠️ *ADVANCE TRADE CLOSED: MRS REVERSAL* ⚠️"
                else:
                    result_str = f"{self.stop_loss:.2f} (STOP LOSS) ❌"
                    alert_msg = "🚨 *ADVANCE TRADE CLOSED: STOPLOSS* 🚨"
                
                # Render Final Complete Data Box Structure & Send
                final_box = self.generate_live_box_string(ltp, current_time_str, time_run_mins, "CLOSED", result_str)
                self.send_telegram_matrix(final_box, alert_msg)
                
                # Instant State Clean Reset
                self.state = 0
        
