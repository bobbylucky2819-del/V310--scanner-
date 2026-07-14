import os
import time
import requests

# -------------------------------------------------------------
# CORE LOGIC SETTINGS & CREDENTIAL MANAGEMENT
# -------------------------------------------------------------
TELEGRAM_BOT_TOKEN = "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4"
TELEGRAM_CHAT_ID   = "-1004423772510"

class DayaMasterIntegratedMatrix:
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
        
        # Advanced Structural SMC Tags
        self.mbs_status = "[ ]"
        self.mrs_status = "[ ]"
        self.back_marks = "[SMC Sweep + CHOCH Valid]"
        self.live_msg_id = None  # 1-Box tracking single framework message handler

    def send_telegram_matrix(self, box_str, text_msg, update_existing=False):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return
        
        escaped_box = box_str.replace('.', '\\.').replace('-', '\\-').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('|', '\\|')
        formatted_text = f"{text_msg}\n\n```text\n{escaped_box}\n```"
        
        # 1-Box Rule Architecture: Updates existing message logs seamlessly
        if update_existing and self.live_msg_id:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "message_id": self.live_msg_id, "text": formatted_text, "parse_mode": "MarkdownV2"}
            try:
                requests.post(url, json=payload, timeout=5)
                return
            except Exception as e:
                print(f"Edit Message Matrix Error: {e}")

        # Fresh message pipeline entry initialization
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": formatted_text, "parse_mode": "MarkdownV2"}
        try:
            res = requests.post(url, json=payload, timeout=5).json()
            if res.get("ok"):
                self.live_msg_id = res["result"]["message_id"]
        except Exception as e:
            print(f"Send Message Baseline Error: {e}")

    def generate_live_box_string(self, ltp, current_time_str, time_run_mins, status_str, result_str):
        box = (
            f"┌──────────────────────────────────────────────┐\n"
            f"│  📸 INSTAGRAM SIGNAL STORIES [LIVE FEED]     │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🪙 Asset Type : {self.symbol:<12} ⏱️ Frame: {self.timeframe:<4} │\n"
            f"│ 🎯 Target Run : +250.0 PTS   📈 Side : BUY    │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 💰 ENTRY PRICE: {self.entry_price:<28.2f} │\n"
            f"│ 🛑 STOP LOSS  : {self.stop_loss:<28.2f} │\n"
            f"│ 🏆 TARGET HIT : {self.target_price:<28.2f} │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🟢 M.B.S. STATUS : {self.mbs_status:<25} │\n"
            f"│ ⚠️ M.R.S. STATUS : {self.mrs_status:<25} │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ ⏱️ PRESENT TIME  : {current_time_str:<25} │\n"
            f"│ ⏰ RUNTIME CLOCK : {time_run_mins:<3} Mins [1m-60m Scale]     │\n"
            f"├──────────────────────────────────────────────┤\n"
            f"│ 🏁 POSITION RESULT: {status_str:<24} │\n"
            f"│ 📊 ENGINE LOGS    : {result_str:<24} │\n"
            f"└──────────────────────────────────────────────┘"
        )
        return box

    def execute_tick_runtime(self, ltp, anchored_vwap, highest_high_7, atr, volume, volume_ma_20, 
                             is_sideways, three_candle_confirm, delta_breakout, s_r_breakout):
        
        current_time_str = time.strftime("%I:%M %p")
        
        # Sideways avoidance condition processing
        if is_sideways and self.state == 0:
            return

        # SMC Structural Trigger Checklist Matrix
        is_high_volume_injection = volume > (volume_ma_20 * 1.8)
        buy_trigger = (
            (ltp > highest_high_7) and 
            (ltp > anchored_vwap) and 
            is_high_volume_injection and 
            delta_breakout and 
            three_candle_confirm and 
            s_r_breakout and 
            (self.state == 0)
        )
        
        # --- 1. BUY INITIALIZATION LOOP (Clean Green Dot Log) ---
        if buy_trigger:
            self.state = 1
            self.entry_price = ltp
            self.peak_price = ltp
            self.target_price = ltp + 250.0  # Target 250 point baseline calculation
            self.stop_loss = ltp - (atr * 1.5)
            self.start_time = current_time_str
            self.entry_timestamp = time.time()
            
            self.mbs_status = "[🟢 Green Dot Active]"
            self.mrs_status = "[Monitoring]"
            
            box_output = self.generate_live_box_string(ltp, current_time_str, 0, "ACTIVE MONITORING", "RUNNING: 0.00 PTS")
            self.send_telegram_matrix(box_output, "🔥 *ADVANCE TRADE INITIALIZED* 🔥", update_existing=False)
            return

        # --- 2. ACTIVE SYSTEM DEPLOYMENT RUNTIME FLOW ---
        if self.state == 1:
            self.peak_price = max(ltp, self.peak_price)
            time_run_mins = int((time.time() - self.entry_timestamp) // 60)
            
            points_drop_from_peak = self.peak_price - ltp
            mrs_reversal_hit = points_drop_from_peak >= 3.0  # MRS 3-Point Drop Condition
            target_hit = ltp >= self.target_price
            stop_loss_hit = ltp <= self.stop_loss
            
            current_diff = ltp - self.entry_price
            live_pnl_str = f"PROFIT: +{current_diff:.2f} PTS" if current_diff >= 0 else f"LOSS: {current_diff:.2f} PTS"

            # --- 3. EXITED ENGINE STATES MATRIX RESOLUTION ---
            if target_hit or mrs_reversal_hit or stop_loss_hit:
                if target_hit:
                    # Target Hit Rules: Green Tick Injected Only After Booked State
                    self.mbs_status = "[✅ Bullish PROFIT HIT]"
                    self.mrs_status = "[Monitoring]"
                    result_str = "PROFIT: +250.00 PTS"
                    status_str = "CLOSED"
                    alert_msg = "💰 *TRADE CLOSED: TARGET BOOKED* 💰"
                elif mrs_reversal_hit:
                    # MRS Reversal Rules: Early exit calculation locks points
                    self.mbs_status = "[🟢 Green Dot Active]"
                    self.mrs_status = "[✅ Reversal Hit]"
                    final_diff = ltp - self.entry_price
                    result_str = f"PROFIT: +{final_diff:.2f} PTS" if final_diff >= 0 else f"LOSS: {final_diff:.2f} PTS"
                    status_str = "CLOSED"
                    alert_msg = "⚠️ *TRADE CLOSED: MRS REVERSAL* ⚠️"
                else:
                    # Stop Loss Rules: Risk threshold boundary crossed
                    self.mbs_status = "[❌ Stop Loss Hit]"
                    self.mrs_status = "[Monitoring]"
                    final_diff = self.stop_loss - self.entry_price
                    result_str = f"LOSS: {final_diff:.2f} PTS"
                    status_str = "CLOSED"
                    alert_msg = "🚨 *TRADE CLOSED: STOPLOSS DETECTED* 🚨"
                
                final_box = self.generate_live_box_string(ltp, current_time_str, time_run_mins, status_str, result_str)
                self.send_telegram_matrix(final_box, alert_msg, update_existing=True)
                self.state = 0
                self.live_msg_id = None  # Clears loop target constraints lock
            else:
                # Live runtime loops execute clean monitoring refresh parameters
                live_box = self.generate_live_box_string(ltp, current_time_str, time_run_mins, "ACTIVE MONITORING", live_pnl_str)
                self.send_telegram_matrix(live_box, "⏳ *TRADING REALTIME MONITORING ACTIVE* ⏳", update_existing=True)

if __name__ == "__main__":
    print("Daya Master V61 Pipeline Initializing Framework Core Logs...")
    timeframes = ["15m", "30m", "1h", "2h", "3h", "4h", "1d"]
    indian_symbols = ["RELIANCE", "TCS", "INFY", "TATAMOTORS"]
    forex_symbols = ["EURUSD", "GBPUSD", "USDJPY"]
    
    all_assets = indian_symbols + forex_symbols
    matrix_engines = {}
    
    for asset in all_assets:
        matrix_engines[asset] = {}
        for tf in timeframes:
            matrix_engines[asset][tf] = DayaMasterIntegratedMatrix(symbol=asset, timeframe=tf)
            
    while True:
        for asset in all_assets:
            for tf in timeframes:
                matrix_engines[asset][tf].execute_tick_runtime(
                    ltp=2455.0 if asset in indian_symbols else 1.0850,
                    anchored_vwap=2440.0 if asset in indian_symbols else 1.0820,
                    highest_high_7=2445.0 if asset in indian_symbols else 1.0835,
                    atr=15.0 if asset in indian_symbols else 0.0020,
                    volume=50000,
                    volume_ma_20=20000,
                    is_sideways=False, three_candle_confirm=True, delta_breakout=True, s_r_breakout=True
                )
        time.sleep(60)
        
