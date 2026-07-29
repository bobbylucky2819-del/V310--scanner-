import os
import requests
import pytz
from datetime import datetime, timedelta
from flask import Flask, jsonify
from SmartApi import SmartConnect
import pyotp

app = Flask(__name__)

# Credentials
API_KEY      = os.getenv("API_KEY", "5L3fPSxW")
CLIENT_CODE  = os.getenv("CLIENT_CODE", "AAAE383027")
PASSWORD     = os.getenv("PASSWORD", "2222")
TOTP_SECRET  = os.getenv("TOTP_SECRET", "CV42EVYE6UNCQKEIZWEQHSIUZM")

BOT_TOKEN    = os.getenv("BOT_TOKEN", "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4")
CHAT_ID      = os.getenv("CHAT_ID", "-1004423772510")

last_sent_signals = {}

def is_market_open():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    if now.weekday() >= 5: # Sat/Sun Skip
        return False
    market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end   = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_start <= now <= market_end

def send_telegram_alert(signal_action, exit_action, sweep_type, symbol, price, sl, target1, target2, tf):
    msg = f"🚨 *ANGEL ONE SMC SIGNAL*\n\n" \
          f"🟢 *ACTION:* `{signal_action}`\n" \
          f"🔴 *EXIT ALERT:* `{exit_action}`\n\n" \
          f"⚡ *Liquidity Type:* `{sweep_type}`\n" \
          f"📈 *Symbol:* `{symbol}`\n" \
          f"⏱️ *Timeframe:* `{tf}`\n\n" \
          f"💰 *Entry Price:* `{price}`\n" \
          f"🛑 *Stop Loss (Safe Buffer):* `{sl}`\n" \
          f"🎯 *Target 1 (1:2 RR):* `{target1}`\n" \
          f"🚀 *Target 2 (1:3 RR):* `{target2}`\n\n" \
          f"🤖 *Bot:* `@luckyTradingV310Bot`"
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram alert error: {e}")

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Angel One SMC Scanner Active!", "client": CLIENT_CODE}), 200

@app.route("/scan", methods=["GET", "POST"])
def scan_market():
    global last_sent_signals
    
    if not is_market_open():
        return jsonify({"status": "skipped", "reason": "Market is Closed"}), 200

    try:
        smart_api = SmartConnect(api_key=API_KEY)
        totp_code = pyotp.TOTP(TOTP_SECRET).now()
        login_res = smart_api.generateSession(CLIENT_CODE, PASSWORD, totp_code)
        
        if not login_res.get('status'):
            return jsonify({"status": "error", "message": "Angel One Login Failed"}), 400

        now = datetime.now()
        from_d = (now - timedelta(days=7)).strftime("%Y-%m-%d 09:15")
        to_d   = now.strftime("%Y-%m-%d %H:%M")

        symbols = [
            {"name": "NIFTY", "token": "99926000"},
            {"name": "BANKNIFTY", "token": "99926009"}
        ]

        timeframes = [
            {"tf_name": "1H", "interval": "ONE_HOUR"},
            {"tf_name": "2H", "interval": "TWO_HOUR"},
            {"tf_name": "3H", "interval": "THREE_HOUR"},
            {"tf_name": "4H", "interval": "FOUR_HOUR"}
        ]

        signals_found = []

        for item in symbols:
            # Daily Fetch for PDH / PDL (MAIN)
            daily_params = {
                "exchange": "NSE",
                "symboltoken": item["token"],
                "interval": "ONE_DAY",
                "fromdate": (now - timedelta(days=5)).strftime("%Y-%m-%d 09:15"),
                "todate": to_d
            }
            d_res = smart_api.getCandleData(daily_params)
            pdh, pdl = None, None
            if d_res and 'data' in d_res and len(d_res['data']) >= 2:
                pdh = d_res['data'][-2][2]
                pdl = d_res['data'][-2][3]

            for tf in timeframes:
                params = {
                    "exchange": "NSE",
                    "symboltoken": item["token"],
                    "interval": tf["interval"],
                    "fromdate": from_d,
                    "todate": to_d
                }
                res = smart_api.getCandleData(params)
                if res and 'data' in res and len(res['data']) >= 2:
                    candles = res['data']
                    prev_c, curr_c = candles[-2], candles[-1]
                    
                    candle_time = curr_c[0]
                    prev_high, prev_low = prev_c[2], prev_c[3]
                    curr_high, curr_low, curr_close = curr_c[2], curr_c[3], curr_c[4]

                    entry_act = None
                    exit_act  = None
                    sweep_cat = None
                    sl, t1, t2 = 0, 0, 0

                    # 1. MAIN SWEEP (PDH / PDL)
                    if pdl and curr_low < pdl and curr_close > pdl:
                        entry_act = "CALL BUY (Bullish Sweep)"
                        exit_act  = "PUT EXIT"
                        sweep_cat = "MAIN LIQUIDITY (PDL Cleared)"
                        # SL with 0.25% Volatility Buffer below low
                        sl = round(curr_low * 0.9975, 2)
                        risk = curr_close - sl
                        t1 = round(curr_close + (risk * 2), 2)
                        t2 = round(curr_close + (risk * 3), 2)

                    elif pdh and curr_high > pdh and curr_close < pdh:
                        entry_act = "PUT BUY (Bearish Sweep)"
                        exit_act  = "CALL EXIT"
                        sweep_cat = "MAIN LIQUIDITY (PDH Cleared)"
                        # SL with 0.25% Volatility Buffer above high
                        sl = round(curr_high * 1.0025, 2)
                        risk = sl - curr_close
                        t1 = round(curr_close - (risk * 2), 2)
                        t2 = round(curr_close - (risk * 3), 2)

                    # 2. INTERNAL SWEEP (1H, 2H, 3H, 4H Inner High/Low)
                    elif curr_low < prev_low and curr_close > prev_low:
                        entry_act = "CALL BUY (Bullish Sweep)"
                        exit_act  = "PUT EXIT"
                        sweep_cat = f"INTERNAL LIQUIDITY ({tf['tf_name']})"
                        sl = round(curr_low * 0.9975, 2)
                        risk = curr_close - sl
                        t1 = round(curr_close + (risk * 2), 2)
                        t2 = round(curr_close + (risk * 3), 2)

                    elif curr_high > prev_high and curr_close < prev_high:
                        entry_act = "PUT BUY (Bearish Sweep)"
                        exit_act  = "CALL EXIT"
                        sweep_cat = f"INTERNAL LIQUIDITY ({tf['tf_name']})"
                        sl = round(curr_high * 1.0025, 2)
                        risk = sl - curr_close
                        t1 = round(curr_close - (risk * 2), 2)
                        t2 = round(curr_close - (risk * 3), 2)

                    if entry_act:
                        sig_key = f"{item['name']}_{tf['tf_name']}_{entry_act}_{candle_time}"
                        
                        if last_sent_signals.get(f"{item['name']}_{tf['tf_name']}") != sig_key:
                            send_telegram_alert(entry_act, exit_act, sweep_cat, item["name"], curr_close, sl, t1, t2, tf['tf_name'])
                            last_sent_signals[f"{item['name']}_{tf['tf_name']}"] = sig_key
                            signals_found.append(f"{item['name']} {tf['tf_name']} - {entry_act}")

        return jsonify({"status": "success", "signals": signals_found}), 200

    except Exception as e:
        return jsonify({"status": "error", "details": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
