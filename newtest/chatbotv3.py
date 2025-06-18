from flask import Flask, render_template_string, request
import requests
import json
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

app = Flask(__name__)

# Groq API credentials
API_TOKEN = "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"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Initialize VADER analyzer
vader = SentimentIntensityAnalyzer()

# Suicide risk detection
def contains_suicidal_language(text):
    keywords = [
        "kill myself", "suicide", "want to die", "end my life", "die",
        "ending it all", "i don't want to live", "life is meaningless", "worthless", "no way out"
    ]
    lower = text.lower()
    return any(phrase in lower for phrase in keywords)

# Get tone instruction
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

# Build prompt
def build_prompt(user_input):
    tone_instruction = get_tone_instruction(user_input)
    prompt = f"{tone_instruction}\nUser: {user_input}"
    return prompt

# Get model response
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
    except requests.exceptions.RequestException as e:
        return f"Request failed: {e}"
    except json.JSONDecodeError as e:
        return f"JSON decode error: {e}"

# HTML template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Sentiment-Aware Chatbot</title>
    <style>
        body { font-family: Arial; background: #f0f2f5; padding: 20px; }
        .chatbox { max-width: 700px; margin: auto; background: white; border-radius: 10px; padding: 20px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }
        .bubble { padding: 12px 16px; margin: 10px 0; border-radius: 12px; max-width: 80%; }
        .user { background: #d1e7dd; text-align: right; margin-left: auto; }
        .bot { background: #f8d7da; text-align: left; margin-right: auto; }
        form { display: flex; gap: 10px; }
        input[type=text] { flex: 1; padding: 12px; border-radius: 6px; border: 1px solid #ccc; }
        input[type=submit] { padding: 12px 24px; border: none; background: #0d6efd; color: white; border-radius: 6px; cursor: pointer; }
        input[type=submit]:hover { background: #0b5ed7; }
    </style>
</head>
<body>
    <div class="chatbox">
        <h2>Sentiment-Aware Chatbot</h2>
        {% for pair in chat %}
            <div class="bubble user"><strong>You:</strong> {{ pair.user }}</div>
            <div class="bubble bot"><strong>Bot:</strong> {{ pair.bot }}</div>
        {% endfor %}
        <form method="POST">
            <input type="text" name="message" placeholder="Type something..." required>
            <input type="submit" value="Send">
        </form>
    </div>
</body>
</html>
'''

# Store chat history
chat_history = []

@app.route("/", methods=["GET", "POST"])
def chat():
    global chat_history
    if request.method == "POST":
        user_msg = request.form["message"]

        if contains_suicidal_language(user_msg):
            bot_response = (
                "I'm really sorry you're feeling this way. You're not alone — "
                "please consider talking to someone who can help.\n\n"
                "**📞 Suicide Prevention Helpline:**\n"
                "**Mauritius:** 800 93 93 (free, 24/7)\n"
                "**International:** https://findahelpline.com/\n\n"
                "There are people who care and want to support you."
            )
        else:
            prompt = build_prompt(user_msg)
            bot_response = get_completion(prompt)

        chat_history.append({"user": user_msg, "bot": bot_response})
    return render_template_string(HTML_TEMPLATE, chat=chat_history)

if __name__ == "__main__":
    app.run(debug=True)
