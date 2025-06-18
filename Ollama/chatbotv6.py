from flask import Flask, render_template, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import secrets
import requests
import json
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Flask app and config
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_history.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Groq API configuration
API_TOKEN = "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"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# VADER sentiment analyzer
vader = SentimentIntensityAnalyzer()

# Conversation model
class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100))
    bot_name = db.Column(db.String(100))
    user_message = db.Column(db.Text)
    bot_response = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Create the database
with app.app_context():
    db.create_all()

# Detect suicidal content
def contains_suicidal_language(text):
    keywords = [
        "kill myself", "suicide", "want to die", "end my life", "die", "kms",
        "ending it all", "i don't want to live", "life is meaningless", "worthless", "no way out"
    ]
    lower = text.lower()
    return any(phrase in lower for phrase in keywords)

# Tone detection
def get_tone_instruction(user_input):
    lower = user_input.lower()
    if any(word in lower for word in ["angry", "furious", "hate"]):
        return "The user is angry. Remain calm and respond diplomatically."
    if any(word in lower for word in ["confused", "unclear", "don't get"]):
        return "The user is confused. Respond clearly and guide them step-by-step."
    if any(word in lower for word in ["lol", "funny", "haha"]):
        return "The user is joking. Respond with a light and humorous tone. Use laughing emojis in messages"

    score = vader.polarity_scores(user_input)['compound']
    if score <= -0.75:
        return "The user sounds very upset. Respond with great empathy and reassurance."
    elif -0.75 < score <= -0.4:
        return "The user seems frustrated. Respond with patience and support."
    elif -0.4 < score <= 0.1:
        return "The user feels neutral or uncertain. Respond in a balanced and helpful tone."
    elif 0.1 < score <= 0.5:
        return "The user sounds mildly positive. Respond with a friendly and upbeat tone."
    elif 0.5 < score <= 0.8:
        return "The user is excited or happy. Match their enthusiasm in your reply."
    else:
        return "The user is very excited or joyful. Respond enthusiastically and warmly."

# Send prompt to Groq model
def get_completion(prompt):
    payload = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 200,
        "stream": False
    }

    try:
        response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        elif "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return f"Unexpected response format: {result}"
    except Exception as e:
        return f"API request error: {e}"

# Chat route
@app.route("/", methods=["GET", "POST"])
def chat():
    if 'chat_history' not in session:
        session['chat_history'] = []
    if 'bot_name' not in session:
        session['bot_name'] = 'Alex'
    if 'user_name' not in session:
        session['user_name'] = 'Friend'

    if request.method == "POST":
        action = request.form.get("action", "chat")
        try:
            if action == "set_names":
                session['bot_name'] = request.form.get("bot_name", "Alex").strip() or "Alex"
                session['user_name'] = request.form.get("user_name", "Friend").strip() or "Friend"
                session.modified = True
                return redirect(url_for('chat'))

            elif action == "chat":
                user_msg = request.form.get("message", "").strip()
                if user_msg:
                    if contains_suicidal_language(user_msg):
                        bot_response = (
                            f"Hey {session['user_name']}, I'm really sorry you're feeling this way. You're not alone — "
                            "please consider talking to someone who can help.\n\n"
                            "**📞 Suicide Prevention Helpline:**\n"
                            "**Mauritius:** 800 93 93 (free, 24/7)\n"
                            "**International:** https://findahelpline.com/\n\n"
                            "There are people who care and want to support you. I care too. 💙"
                        )
                    else:
                        tone_instruction = get_tone_instruction(user_msg)
                        prompt = f"You are {session['bot_name']}, a friendly AI companion.\nUser ({session['user_name']}): {user_msg}"
                        bot_response = get_completion(prompt)

                    # Save to database
                    db.session.add(Conversation(
                        user_name=session['user_name'],
                        bot_name=session['bot_name'],
                        user_message=user_msg,
                        bot_response=bot_response
                    ))
                    db.session.commit()

            elif action == "clear":
                # Optional: Clear session but not the DB
                session['chat_history'] = []
                session.modified = True
                return redirect(url_for('chat'))

        except Exception as e:
            print(f"Error in POST request: {e}")

    # Fetch from database
    history = Conversation.query.filter_by(
        user_name=session['user_name'],
        bot_name=session['bot_name']
    ).order_by(Conversation.timestamp.asc()).all()

    # Format for template
    chat_history = [{"user": entry.user_message, "bot": entry.bot_response} for entry in history]

    return render_template("index.html", 
        chat=chat_history, 
        bot_name=session['bot_name'],
        user_name=session['user_name'])

# Run the app
if __name__ == "__main__":
    app.run(debug=True)