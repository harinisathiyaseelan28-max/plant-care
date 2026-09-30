import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

import chatbot_config as config

load_dotenv()

MODEL_NAME = "gemini-3.1-flash-lite"
MAX_MESSAGE_LENGTH = 1000
MAX_HISTORY_ITEMS = 12
MAX_HISTORY_TEXT = 4000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None


def make_content(role, text):
    return types.Content(role=role, parts=[types.Part.from_text(text=text)])


def build_contents(history, message):
    contents = []
    for item in history[-MAX_HISTORY_ITEMS:]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()[:MAX_HISTORY_TEXT]
        if not text:
            continue
        role = "model" if item.get("role") == "bot" else "user"
        contents.append(make_content(role, text))
    contents.append(make_content("user", message))
    return contents


@app.route("/")
def index():
    return render_template(
        "index.html",
        title=config.CHATBOT_TITLE,
        heading=config.WELCOME_HEADING,
        welcome=config.WELCOME_TEXT,
        suggestions=config.SUGGESTIONS,
    )


@app.route("/chat", methods=["POST"])
def chat():
    if client is None:
        return jsonify(error="The server is missing its Gemini API key."), 500

    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    history = payload.get("history", [])

    if not message:
        return jsonify(error="Please type a question first."), 400
    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify(error=f"Keep your question under {MAX_MESSAGE_LENGTH} characters."), 400
    if not isinstance(history, list):
        history = []

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=build_contents(history, message),
            config=types.GenerateContentConfig(
                system_instruction=config.SYSTEM_PROMPT,
                temperature=0.5,
                max_output_tokens=1024,
            ),
        )
        reply = (response.text or "").strip() or config.FALLBACK_MESSAGE
        return jsonify(reply=reply)
    except Exception:
        logger.exception("Gemini request failed")
        return jsonify(error="The assistant is unavailable right now. Please try again."), 502


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
