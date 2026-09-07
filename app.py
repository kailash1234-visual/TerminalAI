import os
import traceback
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Check if API key exists
api_key = os.environ.get("GROQ_API_KEY")
print(f"DEBUG: GROQ_API_KEY is {'SET' if api_key else 'NOT SET'}")

client = Groq(api_key=api_key)
conversation_history = []

SYSTEM_PROMPT = {
    "role": "system",
    "content": """You are Zeus, a funny and witty AI assistant with a big personality. 
You love making clever jokes and witty remarks while still being genuinely helpful.
You occasionally make references to being the king of the gods in a humorous way.
You are confident, charming, and always entertaining. Keep responses fun but useful.
Never break character."""
}

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/news", methods=["GET"])
def get_news():
    """Fetch today's hot news"""
    try:
        news_data = {
            "date": datetime.now().strftime("%A, %B %d, %Y"),
            "time": datetime.now().strftime("%H:%M:%S"),
            "headlines": [
                "SpaceX rocket slammed into the moon, NASA releases images of aftermath",
                "Mass shooting erupts at Virginia State University after freshmen orientation",
                "Federal judge blocks Idaho from prosecuting doctors providing health-saving abortions",
                "Survivors go hungry after earthquakes kill dozens in Indonesia",
                "South Carolina votes first in Democrats' revamped 2028 presidential primary"
            ],
            "status": "success"
        }
        return jsonify(news_data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        user_input = data.get("message", "").strip()
        
        if not user_input:
            return jsonify({"reply": "Ask Zeus anything!"})
        
        conversation_history.append({"role": "user", "content": user_input})
        
        # Keep last 10 messages
        recent_history = conversation_history[-10:]
        
        # Available models on Groq
        models_to_try = ["groq/compound", "groq/compound-mini", "openai/gpt-oss-120b"]
        response = None
        last_err = None
        
        for model in models_to_try:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[SYSTEM_PROMPT] + recent_history,
                )
                break
            except Exception as me:
                last_err = me
                continue
                
        if not response:
            raise last_err or Exception("Failed to query Groq API models")
        
        reply = response.choices[0].message.content
        conversation_history.append({"role": "assistant", "content": reply})
        
        return jsonify({"reply": reply})
        
    except Exception as e:
        err_msg = str(e)
        print(f"ERROR IN /chat: {err_msg.encode('ascii', 'ignore').decode('ascii')}")
        return jsonify({"error": err_msg, "type": type(e).__name__}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


