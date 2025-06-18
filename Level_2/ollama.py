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

# Ollama configuration (replacing Groq)
OLLAMA_URL = "http://localhost:11434"
EMPATHY_MODEL = "empathy-support:latest"

# Groq API configuration (keeping as fallback)
GROQ_API_TOKEN = "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"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_HEADERS = {
    "Authorization": f"Bearer {GROQ_API_TOKEN}",
    "Content-Type": "application/json"
}

# VADER sentiment analyzer
vader = SentimentIntensityAnalyzer()

# Conversation model (REMOVED model_used column)
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
        "ending it all", "i don't want to live", "life is meaningless", "worthless", "no way out",
        "self harm", "hurt myself", "cut myself", "overdose", "jump off"
    ]
    lower = text.lower()
    return any(phrase in lower for phrase in keywords)

# Enhanced tone detection for empathy bot
def get_empathy_context(user_input, sentiment_score):
    """Generate context for empathy bot based on user input and sentiment"""
    lower = user_input.lower()
    
    # Check for specific emotional states
    if any(word in lower for word in ["anxious", "anxiety", "panic", "worried", "stress"]):
        return "The user is experiencing anxiety. Be calming and offer grounding techniques."
    
    if any(word in lower for word in ["depressed", "depression", "sad", "empty", "hopeless"]):
        return "The user may be dealing with depression. Be extra supportive and gentle."
    
    if any(word in lower for word in ["angry", "furious", "mad", "frustrated"]):
        return "The user is angry or frustrated. Validate their feelings and help them process."
    
    if any(word in lower for word in ["lonely", "alone", "isolated", "nobody cares"]):
        return "The user feels lonely. Provide warmth and remind them they're not alone."
    
    if any(word in lower for word in ["confused", "lost", "don't know", "unclear"]):
        return "The user is confused or lost. Offer clarity and gentle guidance."
    
    # Use sentiment score for general tone
    if sentiment_score <= -0.6:
        return "The user is feeling very negative. Provide strong emotional support."
    elif -0.6 < sentiment_score <= -0.2:
        return "The user seems down. Offer gentle encouragement and validation."
    elif -0.2 < sentiment_score <= 0.2:
        return "The user has neutral feelings. Be supportive and ask gentle questions."
    elif 0.2 < sentiment_score <= 0.6:
        return "The user seems positive. Match their energy while staying supportive."
    else:
        return "The user is very positive. Share in their happiness while being authentic."

# Get conversation context for Ollama
def get_conversation_context(user_name, bot_name, limit=3):
    """Get recent conversation history for context"""
    recent_conversations = Conversation.query.filter_by(
        user_name=user_name,
        bot_name=bot_name
    ).order_by(Conversation.timestamp.desc()).limit(limit).all()
    
    context_parts = []
    for conv in reversed(recent_conversations):  # Reverse to get chronological order
        context_parts.append(f"Human: {conv.user_message}")
        context_parts.append(f"AI: {conv.bot_response}")
    
    return "\n".join(context_parts) if context_parts else ""

# Send prompt to Ollama empathy bot
def get_ollama_response(user_message, user_name, bot_name):
    """Get response from Ollama empathy bot"""
    try:
        # Get sentiment and context
        sentiment_score = vader.polarity_scores(user_message)['compound']
        empathy_context = get_empathy_context(user_message, sentiment_score)
        conversation_context = get_conversation_context(user_name, bot_name)
        
        # Build the full prompt
        if conversation_context:
            full_prompt = f"""Previous conversation:
{conversation_context}

{empathy_context}

Human ({user_name}): {user_message}
AI ({bot_name}):"""
        else:
            full_prompt = f"""{empathy_context}

Human ({user_name}): {user_message}
AI ({bot_name}):"""
        
        # Make request to Ollama
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": EMPATHY_MODEL,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.4,
                    "num_predict": 80,  # Slightly longer than the 50 we set
                    "repeat_penalty": 1.4,
                    "top_p": 0.8
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            bot_response = result.get("response", "").strip()
            
            # Clean up response
            if bot_response.startswith(f"AI ({bot_name}):"):
                bot_response = bot_response[len(f"AI ({bot_name}):")].strip()
            elif bot_response.startswith(f"{bot_name}:"):
                bot_response = bot_response[len(f"{bot_name}:")].strip()
            elif bot_response.startswith("AI:"):
                bot_response = bot_response[3:].strip()
            
            return bot_response or f"I'm here for you, {user_name}. How can I support you today? 😊"
        else:
            return "I'm having trouble connecting right now. Let me try another way to help you."
            
    except requests.exceptions.ConnectionError:
        return "I'm not available through my usual connection. Let me use an alternative to help you."
    except requests.exceptions.Timeout:
        return "I'm taking a bit longer to respond. Please give me a moment."
    except Exception as e:
        print(f"Ollama error: {e}")
        return "I'm having some technical difficulties, but I'm still here to support you."

# Fallback to Groq (keeping your original function with modifications)
def get_groq_completion(prompt, user_name, bot_name):
    """Fallback to Groq API if Ollama is unavailable"""
    # Enhanced prompt for empathy
    empathy_prompt = f"""You are {bot_name}, a compassionate AI companion focused on emotional support. 
    Keep responses to 1-2 sentences. Be warm, validating, and use appropriate emojis.
    
    User ({user_name}): {prompt}
    {bot_name}:"""
    
    payload = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": empathy_prompt}],
        "temperature": 0.5,
        "max_tokens": 100,  # Shorter responses like Ollama
        "stream": False
    }

    try:
        response = requests.post(GROQ_API_URL, headers=GROQ_HEADERS, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        else:
            return f"I'm here to listen, {user_name}. What's on your mind? 💙"
    except Exception as e:
        print(f"Groq error: {e}")
        return f"I'm having technical issues, but I care about you, {user_name}. Please try again."

# Check if Ollama is available
def is_ollama_available():
    """Check if Ollama service is running and model is available"""
    try:
        print("Checking Ollama connection...")
        # Check if Ollama is running
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        print(f"Ollama response status: {response.status_code}")
        
        if response.status_code == 200:
            models = response.json()
            print(f"Available models: {[m.get('name', '') for m in models.get('models', [])]}")
            # Check if our empathy model exists (with or without :latest)
            model_names = [model.get('name', '') for model in models.get('models', [])]
            is_available = any(EMPATHY_MODEL in name or name.startswith(EMPATHY_MODEL.split(':')[0]) for name in model_names)
            print(f"Empathy model available: {is_available}")
            return is_available
        return False
    except Exception as e:
        print(f"Ollama connection error: {e}")
        return False

# Main completion function that chooses between Ollama and Groq
def get_ai_response(user_message, user_name, bot_name):
    """Get AI response, preferring Ollama but falling back to Groq"""
    if is_ollama_available():
        print("Using Ollama empathy model")
        response = get_ollama_response(user_message, user_name, bot_name)
        return response
    else:
        print("Falling back to Groq API")
        response = get_groq_completion(user_message, user_name, bot_name)
        return response

# Chat route (modified to use new AI function)
@app.route("/", methods=["GET", "POST"])
def chat():
    if 'chat_history' not in session:
        session['chat_history'] = []
    if 'bot_name' not in session:
        session['bot_name'] = 'EmpathyBot'  # Changed default name
    if 'user_name' not in session:
        session['user_name'] = 'Friend'

    if request.method == "POST":
        action = request.form.get("action", "chat")
        try:
            if action == "set_names":
                session['bot_name'] = request.form.get("bot_name", "EmpathyBot").strip() or "EmpathyBot"
                session['user_name'] = request.form.get("user_name", "Friend").strip() or "Friend"
                session.modified = True
                return redirect(url_for('chat'))

            elif action == "chat":
                user_msg = request.form.get("message", "").strip()
                if user_msg:
                    if contains_suicidal_language(user_msg):
                        bot_response = (
                            f"Hey {session['user_name']}, I'm really concerned about you. You matter, and you're not alone. 💙\n\n"
                            "**🆘 Crisis Support:**\n"
                            "**Mauritius:** 800 93 93 (free, 24/7)\n"
                            "**International:** 988 or https://findahelpline.com/\n\n"
                            "Please reach out for professional help. I care about you and want you to be safe."
                        )
                    else:
                        bot_response = get_ai_response(
                            user_msg, 
                            session['user_name'], 
                            session['bot_name']
                        )

                    # Save to database (REMOVED model_used parameter)
                    db.session.add(Conversation(
                        user_name=session['user_name'],
                        bot_name=session['bot_name'],
                        user_message=user_msg,
                        bot_response=bot_response
                    ))
                    db.session.commit()

            elif action == "clear":
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

# Add a status endpoint to check which model is being used
@app.route("/status")
def status():
    """Check system status"""
    ollama_status = is_ollama_available()
    return {
        "ollama_available": ollama_status,
        "empathy_model": EMPATHY_MODEL,
        "fallback": "Groq API" if not ollama_status else "Not needed",
        "timestamp": datetime.utcnow().isoformat()
    }

# Run the app
if __name__ == "__main__":
    print("Starting Enhanced AI Empathy Web App")
    print("Ollama Empathy Model: Primary")
    print("Groq API: Fallback")
    print("Access at: http://localhost:5000")
    print("Status check: http://localhost:5000/status")
    
    if is_ollama_available():
        print(f"Ollama model '{EMPATHY_MODEL}' is ready!")
    else:
        print("Ollama not available - will use Groq fallback")
    
    app.run(debug=True)