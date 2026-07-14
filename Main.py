import os
import time
import requests

# -------------------------------------------------------------
# DYNAMIC MATRIX CONFIGURATION (DIRECT TARGET CHANNELS)
# -------------------------------------------------------------
TELEGRAM_BOT_TOKEN = "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4"
TELEGRAM_CHAT_ID   = "-1004423772510"

class DayaMasterMultiFrameEngine:
    def __init__(self, symbol, timeframe):
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
        
        # SMC / Structure Tags
        self.mbs_status = "[ ]"
        self.mrs_status = "[ ]"
        self.back_marks = "[SMC Sweep + CHOCH Valid]"

    def send_telegram_matrix(self, box_str, text_msg):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload_header = {"chat_id": TELEGRAM_CHAT_ID, "text": text_msg, "parse_mode": "Markdown"}
        escaped_box = box_str.replace('.', '\\.').replace('-', '\\-').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('|', '\\|')
        payload_box = {"chat_id": TELEGRAM_CHAT_ID, "text": f"```text\n{escaped_box}\n```", "parse_mode": "MarkdownV2"}
        try:
            requests.post(url, json=payload_header, timeout=5)
            requests.post(url, json=payload_box, timeout=5)
        except Exception as e:
            print(f"Telegram Delay Error: {e}")

    def generate_live_box_string(self, ltp, current_time_str, time_run_mins, status_str, result_str):
        box = (
            f"┌──────────────────────────────────────────────┐\n"
            f"│        🏆 DAYA MASTER LIVE OBSERVER          │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🪙 Symbol     : {self.symbol:<12} ({self.timeframe:<3} Frame Engine) │\n"
            f"│ 📅 Start Time : {self.start_time:<29}  │\n"
            f"│ ⏱️ Present Time: {current_time_str:<12} [LIVE LOG]         │\n"
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
        current_time_str = time.strftime("%I:%M %p")
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
            self.send_telegram_matrix(box_output, f"🔥 *ADVANCE TRADE INITIALIZED:* {self.symbol} ({self.timeframe}) 🔥")
            return

        if self.state == 1:
            self.peak_price = max(ltp, self.peak_price)
            time_run_mins = int((time.time() - self.entry_timestamp) // 60)
            points_drop_from_peak = self.peak_price - ltp
            mrs_reversal_hit = points_drop_from_peak >= 3.0
            target_hit = ltp >= self.target_price
            stop_loss_hit = ltp <= self.stop_loss
            
            if target_hit or mrs_reversal_hit or stop_loss_hit:
                if target_hit:
                    self.mbs_status = "[✅] Bullish (PROFIT HIT)"
                    result_str = f"{self.target_price:.2f} (TARGET DONE) ✅"
                    alert_msg = f"💰 *TRADE CLOSED: TARGET HIT* [{self.symbol} {self.timeframe}] 💰"
                elif mrs_reversal_hit:
                    self.mrs_status = "[✅] 3-Pt Reversal Triggered"
                    result_str = f"{ltp:.2f} (M.R.S. LOCKED) ✅"
                    alert_msg = f"⚠️ *TRADE CLOSED: MRS REVERSAL* [{self.symbol} {self.timeframe}] ⚠️"
                else:
                    result_str = f"{self.stop_loss:.2f} (STOP LOSS) ❌"
                    alert_msg = f"🚨 *TRADE CLOSED: STOPLOSS* [{self.symbol} {self.timeframe}] 🚨"
                
                final_box = self.generate_live_box_string(ltp, current_time_str, time_run_mins, "CLOSED", result_str)
                self.send_telegram_matrix(final_box, alert_msg)
                self.state = 0

# -------------------------------------------------------------
# MULTI-ASSET CORE RUNTIME SCHEDULER MATRIX
# -------------------------------------------------------------
if __name__ == "__main__":
    print("Daya Master Multi-Asset Matrix Active...")
    
    # Complete Multi-Timeframe Matrix Target Arrays
    timeframes = ["15m", "30m", "1h", "2h", "3h", "4h", "1d"]
    indian_symbols = ["RELIANCE", "TCS", "INFY", "TATAMOTORS"]
    forex_symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    
    all_assets = indian_symbols + forex_symbols
    matrix_engines = {}
    
    # Mapping Loop Engines
    for asset in all_assets:
        matrix_engines[asset] = {}
        for tf in timeframes:
            matrix_engines[asset][tf] = DayaMasterMultiFrameEngine(symbol=asset, timeframe=tf)
            
    print(f"Initialized Matrix Engines for {len(all_assets)} symbols across {len(timeframes)} timeframes successfully.")

    # Live Processing Loop Verification
    while True:
        for asset in all_assets:
            for tf in timeframes:
                # Execution loop verification framework parameters
                matrix_engines[asset][tf].execute_tick_runtime(
                    ltp=2455.0 if asset in indian_symbols else 1.0850,
                    anchored_vwap=2440.0 if asset in indian_symbols else 1.0820,
                    highest_high_7=2445.0 if asset in indian_symbols else 1.0835,
                    atr=15.0 if asset in indian_symbols else 0.0020,
                    volume=50000,
                    volume_ma_20=20000
                )
        time.sleep(60)
