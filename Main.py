import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Telegram Configuration (Render Environment Variables nunchi fetch chestundi)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8736794778:AAHusM5e2JCHty4KDx6QKdZl26SeY65s5d4")
CHAT_ID = os.getenv("CHAT_ID", "-1004423772510")

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Server is running smoothly!"}), 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        
        # Message construction from TradingView Alert Payload
        action = data.get("action", "ALERT")
        ticker = data.get("ticker", "UNKNOWN")
        price = data.get("price", "N/A")
        timeframe = data.get("tf", "")
        
        message = f"🚨 *TRADING SIGNAL: {action}*\n\n" \
                  f"📈 *Symbol:* `{ticker}`\n" \
                  f"⏱️ *Timeframe:* `{timeframe}`\n" \
                  f"💰 *Price:* `{price}`\n" \
                  f"🤖 *Bot:* `@luckyTradingV310Bot`"

        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        # Send message to Telegram Channel/Chat
        response = requests.post(TELEGRAM_URL, json=payload)
        
        if response.status_code == 200:
            return jsonify({"status": "success", "telegram_response": "message sent"}), 200
        else:
            return jsonify({"status": "error", "response": response.text}), 500

    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
        
