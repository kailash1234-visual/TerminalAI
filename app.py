import os
import traceback
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Debug: Check if API key exists
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
        print("\n" + "="*50)
        print("DEBUG: /chat endpoint called")
        
        user_input = request.json.get("message")
        print(f"DEBUG: User message = '{user_input}'")
        
        conversation_history.append({"role": "user", "content": user_input})
        print(f"DEBUG: Conversation history length = {len(conversation_history)}")
        
        print("DEBUG: Calling Groq API with model 'llama-3.1-70b-versatile'...")
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[SYSTEM_PROMPT] + conversation_history,
        )
        print("DEBUG: Got response from Groq ✓")
        
        reply = response.choices[0].message.content
        print(f"DEBUG: Reply = '{reply[:50]}...'")
        
        conversation_history.append({"role": "assistant", "content": reply})
        print("DEBUG: Response sent successfully ✓")
        print("="*50 + "\n")
        
        return jsonify({"reply": reply})
        
    except Exception as e:
        print("\n" + "="*50)
        print(f"ERROR IN /chat: {str(e)}")
        print("FULL TRACEBACK:")
        print(traceback.format_exc())
        print("="*50 + "\n")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
