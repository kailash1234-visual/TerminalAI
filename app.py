import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
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

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message")
    conversation_history.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[SYSTEM_PROMPT] + conversation_history,
    )

    reply = response.choices[0].message.content
    conversation_history.append({"role": "assistant", "content": reply})
    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
