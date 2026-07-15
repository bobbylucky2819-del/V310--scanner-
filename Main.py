import os
import time
import datetime
import requests

# -------------------------------------------------------------
# SYSTEM CREDENTIAL MANAGEMENT
# -------------------------------------------------------------
TELEGRAM_BOT_TOKEN = "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4"
TELEGRAM_CHAT_ID   = "-1004423772510"

class DayaSMCIntradayEngine:
    def __init__(self, symbol, timeframe):
        self.symbol = symbol
        self.timeframe = timeframe
        self.state = 0  # 0 = FLAT, 1 = BUY ACTIVE, -1 = SELL/PUT ACTIVE
        
        # Matrix Positioning Variables
        self.entry_price = 0.0
        self.target_price = 0.0
        self.stop_loss = 0.0
        self.peak_price = 0.0
        self.entry_timestamp = 0
        self.side = "" # "BUY" or "SELL/C.SEL"
        
        # Professional Institutional SMC State Trackers
        self.mbs_status = "[ ]"
        self.mrs_status = "[ ]"
        self.live_msg_id = None  # Strict 1-Box Tracking Pipeline
        
        self.is_forex = symbol.endswith("USD") or "-" in symbol or len(symbol) == 6

    def is_market_open(self):
        if self.is_forex:
            return True  
        now = datetime.datetime.now()
        if now.weekday() >= 5: 
            return False
        current_time_int = now.hour * 100 + now.minute
        return 915 <= current_time_int <= 1530

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

    def generate_live_box_string(self, ltp, time_run_mins, final_pnl_str):
        return (
            f"┌──────────────────────────────────────────────┐\n"
            f"│ 🟢 greendot running: {self.symbol:<7} [{self.timeframe:<3}]         │\n"
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

    def execute_tick_runtime(self, ltp, anchored_vwap, prev_day_high, prev_day_low, 
                             lowest_low_7, highest_high_7, delta_volume, 
                             institutional_order_flow, volume_profile_poc,
                             is_sideways, three_candle_confirm, amdh_state):
        
        if not self.is_market_open(): return
        if is_sideways and self.state == 0: return  

        delta_volume_breakout = delta_volume > 1.8  
        
        # 🟢 A. CALL SIDE / BUY LOGIC (Liquidity Swept at Bottom)
        buy_trigger = (
            (ltp <= prev_day_low or ltp <= volume_profile_poc) and 
            (institutional_order_flow == "BULLISH_INJECTION") and (ltp > anchored_vwap and ltp > highest_high_7) and 
            delta_volume_breakout and three_candle_confirm and (amdh_state == "Manipulation" or ltp > prev_day_high) and 
            (self.state == 0)
        )
        
        # 🔴 B. PUT SIDE / C.SEL LOGIC (Liquidity Swept at Top - Bearish Breakout)
        sell_trigger = (
            (ltp >= prev_day_high or ltp >= volume_profile_poc) and 
            (institutional_order_flow == "BEARISH_INJECTION") and (ltp < anchored_vwap and ltp < lowest_low_7) and 
            delta_volume_breakout and three_candle_confirm and (amdh_state == "Manipulation" or ltp < prev_day_low) and 
            (self.state == 0)
        )
        
        # --- ENTRY ORDERS BLOCK ---
        if buy_trigger:
            self.state = 1
            self.side = "BUY / CALL SIDE"
            self.entry_price = ltp
            self.peak_price = ltp
            self.target_price = ltp + (0.0050 if self.is_forex else 50.0)
            self.stop_loss = ltp - (0.0020 if self.is_forex else 20.0)
            self.entry_timestamp = time.time()
            self.mbs_status, self.mrs_status = "[🟢 Green Dot Active]", "[Monitoring Call Flow]"
            self.send_telegram_matrix(self.generate_live_box_string(ltp, 0, "PROFIT/LOSS RUNNING"), f"🚀 *SMC CALL SIDE ENTRY TRIGGERED ({self.timeframe})* 🚀", False)
            return

        elif sell_trigger:
            self.state = -1
            self.side = "PUT SIDE / C.SEL"
            self.entry_price = ltp
            self.peak_price = ltp  # Short trade లో peak అంటే లోయెస్ట్ ప్రైస్ ట్రాక్ చేస్తుంది
            self.target_price = ltp - (0.0050 if self.is_forex else 50.0)
            self.stop_loss = ltp + (0.0020 if self.is_forex else 20.0)
            self.entry_timestamp = time.time()
            self.mbs_status, self.mrs_status = "[🔴 Red Dot Active]", "[Monitoring Put Flow]"
            self.send_telegram_matrix(self.generate_live_box_string(ltp, 0, "PROFIT/LOSS RUNNING"), f"💥 *SMC PUT SIDE / C.SEL TRIGGERED ({self.timeframe})* 💥", False)
            return
        
        # --- LIVE RUNTIME MONITORING & EXIT BLOCK ---
        if self.state != 0:
            time_run_mins = int((time.time() - self.entry_timestamp) // 60)
            mrs_threshold = 0.0003 if self.is_forex else 3.0
            
            if self.state == 1:  # Buy Active
                self.peak_price = max(ltp, self.peak_price)
                current_diff = ltp - self.entry_price
                mrs_reversal_hit = (self.peak_price - ltp >= mrs_threshold)
                target_hit = ltp >= self.target_price
                stop_loss_hit = ltp <= self.stop_loss
            else:  # Sell / Put Active
                self.peak_price = min(ltp, self.peak_price) if self.peak_price != 0 else ltp
                current_diff = self.entry_price - ltp  # Short trade లో ప్రైస్ తగ్గుతుంటే ప్రాఫిట్
                mrs_reversal_hit = (ltp - self.peak_price >= mrs_threshold)
                target_hit = ltp <= self.target_price
                stop_loss_hit = ltp >= self.stop_loss

            if target_hit or mrs_reversal_hit or stop_loss_hit:
                if target_hit: 
                    self.mbs_status = "[✅ Target Hit Blocked]"
                    result_str = f"PROFIT: +{50.0 if not self.is_forex else 0.0050:.2f}"
                    msg = f"💰 *TRADE CLOSED: TARGET BOOKED ({self.timeframe})* 💰"
                elif mrs_reversal_hit: 
                    self.mrs_status = "[✅ Reversal Closed]"
                    result_str = f"PROFIT: +{current_diff:.2f}" if current_diff >= 0 else f"LOSS: {current_diff:.2f}"
                    msg = f"⚠️ *TRADE CLOSED: MRS REVERSAL HIT ({self.timeframe})* ⚠️"
                else: 
                    self.mbs_status = "[❌ Stop Loss Hit]"
                    result_str = f"LOSS: -{20.0 if not self.is_forex else 0.0020:.2f}"
                    msg = f"🚨 *TRADE CLOSED: STOPLOSS HIT ({self.timeframe})* 🚨"
                
                self.send_telegram_matrix(self.generate_live_box_string(ltp, time_run_mins, result_str), msg, True)
                self.state, self.live_msg_id = 0, None  
            else:
                pnl_live = f"PROFIT: +{current_diff:.2f}" if current_diff >= 0 else f"LOSS: {current_diff:.2f}"
                self.send_telegram_matrix(self.generate_live_box_string(ltp, time_run_mins, pnl_live), f"⏳ *TRADING REALTIME MONITORING ACTIVE ({self.timeframe})* ⏳", True)

if __name__ == "__main__":
    tfs = ["15m", "30m", "1h", "2h", "3h", "4h", "1d"]
    assets = ["RELIANCE", "TCS", "INFY", "SBIN", "EURUSD", "GBPUSD", "BTC-USD"]
    matrix = {a: {t: DayaSMCIntradayEngine(a, t) for t in tfs} for a in assets}
    print("Daya Master V62 Double-Sided SMC Engine Online.")
    while True:
        time.sleep(60)
                                 
