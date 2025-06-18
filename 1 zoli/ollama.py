from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import secrets
import requests
import json
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import random

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

# Enhanced Conversation model with user preferences
class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100))
    bot_name = db.Column(db.String(100))
    bot_avatar = db.Column(db.String(10), default='🤖')
    user_message = db.Column(db.Text)
    bot_response = db.Column(db.Text)
    sentiment_score = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# User preferences model
class UserPreferences(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100), unique=True)
    bot_name = db.Column(db.String(100), default='EmpathyBot')
    bot_avatar = db.Column(db.String(10), default='🤖')
    avatar_type = db.Column(db.String(20), default='robot')
    favorite_music = db.Column(db.String(50))
    mood_history = db.Column(db.Text)  # JSON string of mood scores
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Activity tracking model
class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100))
    activity_type = db.Column(db.String(50))  # music, bubble_game, memory_game, breathing, color_therapy
    activity_data = db.Column(db.Text)  # JSON string for activity-specific data
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
        return "The user is experiencing anxiety. Be calming and suggest relaxation activities like breathing exercises or calming music."
    
    if any(word in lower for word in ["depressed", "depression", "sad", "empty", "hopeless"]):
        return "The user may be dealing with depression. Be extra supportive, gentle, and suggest uplifting activities."
    
    if any(word in lower for word in ["angry", "furious", "mad", "frustrated"]):
        return "The user is angry or frustrated. Validate their feelings and suggest stress-relief activities like bubble popping."
    
    if any(word in lower for word in ["lonely", "alone", "isolated", "nobody cares"]):
        return "The user feels lonely. Provide warmth, companionship, and suggest interactive activities."
    
    if any(word in lower for word in ["confused", "lost", "don't know", "unclear"]):
        return "The user is confused or lost. Offer clarity, gentle guidance, and suggest calming activities."
    
    if any(word in lower for word in ["music", "sound", "song"]):
        return "The user mentioned music. Suggest the music features and ask about their preferences."
    
    if any(word in lower for word in ["game", "play", "fun", "activity"]):
        return "The user is interested in activities. Suggest the available games and interactive features."
    
    # Use sentiment score for general tone
    if sentiment_score <= -0.6:
        return "The user is feeling very negative. Provide strong emotional support and suggest calming activities."
    elif -0.6 < sentiment_score <= -0.2:
        return "The user seems down. Offer gentle encouragement, validation, and suggest mood-lifting activities."
    elif -0.2 < sentiment_score <= 0.2:
        return "The user has neutral feelings. Be supportive and gently suggest interactive features."
    elif 0.2 < sentiment_score <= 0.6:
        return "The user seems positive. Match their energy while staying supportive and suggest fun activities."
    else:
        return "The user is very positive. Share in their happiness and suggest engaging activities to maintain the mood."

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

# Enhanced AI response generation
def generate_enhanced_response(user_message, user_name, bot_name, bot_avatar):
    """Generate enhanced AI response with activity suggestions"""
    sentiment_score = vader.polarity_scores(user_message)['compound']
    lower_message = user_message.lower()
    
    # Activity-specific responses
    if any(word in lower_message for word in ['sad', 'down', 'depressed', 'upset']):
        activities = ["calming music 🎵", "bubble popping game 🫧", "breathing exercises 🫁"]
        activity = random.choice(activities)
        return f"I hear that you're feeling down, {user_name}. That's completely valid. Would you like to try some {activity}? I'm here for you. 💙"
    
    elif any(word in lower_message for word in ['anxious', 'worried', 'stress', 'nervous']):
        activities = ["deep breathing 🫁", "bubble popping 🫧", "calming ocean sounds 🌊"]
        activity = random.choice(activities)
        return f"Anxiety can be overwhelming, {user_name}. Let's try {activity} to help calm your mind. You're not alone in this! 🤗"
    
    elif any(word in lower_message for word in ['angry', 'mad', 'frustrated', 'annoyed']):
        return f"I can sense your frustration, {user_name}. Those feelings are completely valid. Try popping some bubbles 🫧 to release that tension! Let it all out safely."
    
    elif any(word in lower_message for word in ['happy', 'good', 'great', 'wonderful', 'excited']):
        activities = ["memory game 🧠", "color therapy 🎨", "uplifting music 🎵"]
        activity = random.choice(activities)
        return f"I'm so glad to hear you're feeling positive, {user_name}! 😊 Want to try the {activity} to keep those good vibes going? Your happiness makes me happy too! ✨"
    
    elif any(word in lower_message for word in ['music', 'sound', 'song', 'listen']):
        return f"Music is such a wonderful healer, {user_name}! 🎵 Try the different nature sounds - rain, forest, or ocean waves. Which type of sounds usually calm you the most?"
    
    elif any(word in lower_message for word in ['game', 'play', 'fun', 'activity', 'bored']):
        return f"Games can be great for relaxation, {user_name}! 🎮 Try bubble popping for stress relief, memory game for focus, or breathing exercise for calmness. What sounds fun to you?"
    
    elif any(word in lower_message for word in ['tired', 'exhausted', 'sleepy']):
        return f"It sounds like you need some rest, {user_name}. Try the breathing exercise 🫁 or some gentle forest sounds 🌲 to help you unwind. Self-care is important! 😴"
    
    elif any(word in lower_message for word in ['lonely', 'alone', 'isolated']):
        return f"You're not alone, {user_name}. I'm here with you! 🤗 Let's do something together - maybe the memory game 🧠 or just chat while listening to some calming sounds? You matter! 💕"
    
    # Default supportive responses with activity suggestions
    responses = [
        f"I'm here to listen and support you, {user_name}. How can I help you feel better today? Try the activities above! 💙",
        f"Thank you for sharing with me, {user_name}. Your feelings are important and valid. What would help you right now? 🤗",
        f"I care about how you're feeling, {user_name}. Would you like to try one of the relaxing activities above? 🌟",
        f"You're not alone in whatever you're going through, {user_name}. I'm here for you. What's on your mind? 💕",
        f"Every feeling you have is valid, {user_name}. Let's work through this together. What would bring you some peace right now? 🌸"
    ]
    
    return random.choice(responses)

# Send prompt to Ollama empathy bot
def get_ollama_response(user_message, user_name, bot_name):
    """Get response from Ollama empathy bot"""
    try:
        # Get sentiment and context
        sentiment_score = vader.polarity_scores(user_message)['compound']
        empathy_context = get_empathy_context(user_message, sentiment_score)
        conversation_context = get_conversation_context(user_name, bot_name)
        
        # Build the full prompt with activity awareness
        activity_context = """
        You have access to these interactive features to suggest to users:
        - Calming music (rain, forest, ocean, birds, meditation sounds)
        - Bubble popping game for stress relief
        - Memory game for mental focus
        - Breathing exercises for anxiety
        - Color therapy for mood enhancement
        
        Suggest these activities when appropriate based on the user's emotional state.
        """
        
        if conversation_context:
            full_prompt = f"""You are an empathetic AI companion with interactive wellness features.

{activity_context}

Previous conversation:
{conversation_context}

{empathy_context}

Human ({user_name}): {user_message}
AI ({bot_name}):"""
        else:
            full_prompt = f"""You are an empathetic AI companion with interactive wellness features.

{activity_context}

{empathy_context}

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
                    "num_predict": 80,
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
            return generate_enhanced_response(user_message, user_name, bot_name, "🤖")
            
    except requests.exceptions.ConnectionError:
        return generate_enhanced_response(user_message, user_name, bot_name, "🤖")
    except requests.exceptions.Timeout:
        return "I'm taking a bit longer to respond. Please give me a moment, but try the activities above while you wait! 🎵🎮"
    except Exception as e:
        print(f"Ollama error: {e}")
        return generate_enhanced_response(user_message, user_name, bot_name, "🤖")

# Fallback to Groq (enhanced with activity suggestions)
def get_groq_completion(prompt, user_name, bot_name):
    """Fallback to Groq API if Ollama is unavailable"""
    # Enhanced prompt for empathy with activity features
    empathy_prompt = f"""You are {bot_name}, a compassionate AI companion with interactive wellness features.

Available features to suggest:
- Calming music (rain, forest, ocean, birds, meditation)
- Bubble popping game for stress relief 🫧
- Memory game for focus 🧠  
- Breathing exercises for anxiety 🫁
- Color therapy for mood 🎨

Keep responses to 1-2 sentences. Be warm, validating, suggest appropriate activities, and use emojis.
    
User ({user_name}): {prompt}
{bot_name}:"""
    
    payload = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": empathy_prompt}],
        "temperature": 0.5,
        "max_tokens": 120,
        "stream": False
    }

    try:
        response = requests.post(GROQ_API_URL, headers=GROQ_HEADERS, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        else:
            return generate_enhanced_response(prompt, user_name, bot_name, "🤖")
    except Exception as e:
        print(f"Groq error: {e}")
        return generate_enhanced_response(prompt, user_name, bot_name, "🤖")

# Check if Ollama is available
def is_ollama_available():
    """Check if Ollama service is running and model is available"""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json()
            model_names = [model.get('name', '') for model in models.get('models', [])]
            is_available = any(EMPATHY_MODEL in name or name.startswith(EMPATHY_MODEL.split(':')[0]) for name in model_names)
            return is_available
        return False
    except Exception as e:
        print(f"Ollama connection error: {e}")
        return False

# Main completion function
def get_ai_response(user_message, user_name, bot_name, bot_avatar):
    """Get AI response, preferring Ollama but falling back to enhanced responses"""
    if is_ollama_available():
        print("Using Ollama empathy model")
        response = get_ollama_response(user_message, user_name, bot_name)
        return response
    else:
        print("Using enhanced response generation")
        response = generate_enhanced_response(user_message, user_name, bot_name, bot_avatar)
        return response

# Save or update user preferences
def save_user_preferences(user_name, bot_name, bot_avatar, avatar_type):
    """Save user preferences to database"""
    prefs = UserPreferences.query.filter_by(user_name=user_name).first()
    if prefs:
        prefs.bot_name = bot_name
        prefs.bot_avatar = bot_avatar
        prefs.avatar_type = avatar_type
        prefs.updated_at = datetime.utcnow()
    else:
        prefs = UserPreferences(
            user_name=user_name,
            bot_name=bot_name,
            bot_avatar=bot_avatar,
            avatar_type=avatar_type
        )
        db.session.add(prefs)
    db.session.commit()

# Get user preferences
def get_user_preferences(user_name):
    """Get user preferences from database"""
    prefs = UserPreferences.query.filter_by(user_name=user_name).first()
    if prefs:
        return {
            'bot_name': prefs.bot_name,
            'bot_avatar': prefs.bot_avatar,
            'avatar_type': prefs.avatar_type
        }
    return {
        'bot_name': 'EmpathyBot',
        'bot_avatar': '🤖',
        'avatar_type': 'robot'
    }

# Log activity usage
def log_activity(user_name, activity_type, activity_data=None):
    """Log user activity for analytics"""
    activity = ActivityLog(
        user_name=user_name,
        activity_type=activity_type,
        activity_data=json.dumps(activity_data) if activity_data else None
    )
    db.session.add(activity)
    db.session.commit()

# Enhanced chat route
@app.route("/", methods=["GET", "POST"])
def chat():
    if 'user_name' not in session:
        session['user_name'] = 'Friend'
    
    # Load user preferences
    prefs = get_user_preferences(session['user_name'])
    if 'bot_name' not in session:
        session['bot_name'] = prefs['bot_name']
        session['bot_avatar'] = prefs['bot_avatar']
        session['avatar_type'] = prefs['avatar_type']

    if request.method == "POST":
        action = request.form.get("action", "chat")
        try:
            if action == "set_names":
                new_bot_name = request.form.get("bot_name", "EmpathyBot").strip() or "EmpathyBot"
                new_user_name = request.form.get("user_name", "Friend").strip() or "Friend"
                new_bot_avatar = request.form.get("bot_avatar", "🤖")
                new_avatar_type = request.form.get("avatar_type", "robot")
                
                session['bot_name'] = new_bot_name
                session['user_name'] = new_user_name
                session['bot_avatar'] = new_bot_avatar
                session['avatar_type'] = new_avatar_type
                session.modified = True
                
                # Save preferences
                save_user_preferences(new_user_name, new_bot_name, new_bot_avatar, new_avatar_type)
                
                return jsonify({"status": "success"})

            elif action == "chat":
                user_msg = request.form.get("message", "").strip()
                if user_msg:
                    sentiment_score = vader.polarity_scores(user_msg)['compound']
                    
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
                            session['bot_name'],
                            session['bot_avatar']
                        )

                    # Save to database with sentiment
                    db.session.add(Conversation(
                        user_name=session['user_name'],
                        bot_name=session['bot_name'],
                        bot_avatar=session['bot_avatar'],
                        user_message=user_msg,
                        bot_response=bot_response,
                        sentiment_score=sentiment_score
                    ))
                    db.session.commit()
                    
                    return jsonify({
                        "status": "success",
                        "bot_response": bot_response,
                        "bot_avatar": session['bot_avatar']
                    })

            elif action == "clear":
                # Clear chat history
                Conversation.query.filter_by(
                    user_name=session['user_name'],
                    bot_name=session['bot_name']
                ).delete()
                db.session.commit()
                
                return jsonify({"status": "success"})

        except Exception as e:
            print(f"Error in POST request: {e}")
            return jsonify({"status": "error", "message": str(e)})

    # Fetch conversation history
    history = Conversation.query.filter_by(
        user_name=session['user_name'],
        bot_name=session['bot_name']
    ).order_by(Conversation.timestamp.asc()).all()

    # Format for template
    chat_history = [{
        "user": entry.user_message, 
        "bot": entry.bot_response,
        "bot_avatar": entry.bot_avatar or session['bot_avatar']
    } for entry in history]

    return render_template("index.html", 
        chat=chat_history, 
        bot_name=session['bot_name'],
        user_name=session['user_name'],
        bot_avatar=session['bot_avatar'],
        avatar_type=session['avatar_type'])

# API endpoint for logging activities
@app.route("/api/log-activity", methods=["POST"])
def log_user_activity():
    """Log user activity for analytics"""
    try:
        data = request.get_json()
        user_name = session.get('user_name', 'Friend')
        activity_type = data.get('activity_type')
        activity_data = data.get('activity_data', {})
        
        log_activity(user_name, activity_type, activity_data)
        
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Error logging activity: {e}")
        return jsonify({"status": "error", "message": str(e)})

# API endpoint for getting mood analytics
@app.route("/api/mood-analytics")
def mood_analytics():
    """Get user's mood analytics"""
    user_name = session.get('user_name', 'Friend')
    
    # Get recent conversations with sentiment scores
    recent_conversations = Conversation.query.filter_by(
        user_name=user_name
    ).order_by(Conversation.timestamp.desc()).limit(20).all()
    
    mood_data = []
    for conv in reversed(recent_conversations):
        if conv.sentiment_score is not None:
            mood_data.append({
                'timestamp': conv.timestamp.isoformat(),
                'sentiment': conv.sentiment_score,
                'message_preview': conv.user_message[:50] + "..." if len(conv.user_message) > 50 else conv.user_message
            })
    
    # Calculate mood trends
    if len(mood_data) >= 2:
        recent_avg = sum(item['sentiment'] for item in mood_data[-5:]) / min(len(mood_data), 5)
        older_avg = sum(item['sentiment'] for item in mood_data[:-5]) / max(len(mood_data) - 5, 1)
        trend = "improving" if recent_avg > older_avg else "declining" if recent_avg < older_avg else "stable"
    else:
        trend = "insufficient_data"
    
    return jsonify({
        'mood_history': mood_data,
        'average_mood': sum(item['sentiment'] for item in mood_data) / len(mood_data) if mood_data else 0,
        'total_conversations': len(mood_data),
        'mood_trend': trend
    })

# API endpoint for activity suggestions
@app.route("/api/activity-suggestions")
def activity_suggestions():
    """Get personalized activity suggestions based on recent mood"""
    user_name = session.get('user_name', 'Friend')
    
    # Get recent sentiment
    recent_conv = Conversation.query.filter_by(
        user_name=user_name
    ).order_by(Conversation.timestamp.desc()).first()
    
    # Get recent activity usage
    recent_activities = ActivityLog.query.filter_by(
        user_name=user_name
    ).order_by(ActivityLog.timestamp.desc()).limit(10).all()
    
    used_activities = [act.activity_type for act in recent_activities]
    
    suggestions = []
    
    if recent_conv and recent_conv.sentiment_score is not None:
        score = recent_conv.sentiment_score
        
        if score < -0.4:  # Negative mood
            potential_activities = [
                {"activity": "breathing", "icon": "🫁", "reason": "Help reduce stress and anxiety"},
                {"activity": "music", "icon": "🎵", "reason": "Calming sounds to soothe your mind"},
                {"activity": "bubbles", "icon": "🫧", "reason": "Pop bubbles to release tension"}
            ]
        elif score < 0.2:  # Neutral mood
            potential_activities = [
                {"activity": "memory", "icon": "🧠", "reason": "Gentle mental stimulation"},
                {"activity": "music", "icon": "🎵", "reason": "Background sounds for relaxation"},
                {"activity": "colors", "icon": "🎨", "reason": "Color therapy for mood enhancement"}
            ]
        else:  # Positive mood
            potential_activities = [
                {"activity": "memory", "icon": "🧠", "reason": "Challenge yourself while feeling good"},
                {"activity": "colors", "icon": "🎨", "reason": "Enhance your positive energy"},
                {"activity": "bubbles", "icon": "🫧", "reason": "Fun and playful stress relief"}
            ]
        
        # Prioritize activities not recently used
        for activity in potential_activities:
            if activity["activity"] not in used_activities[:3]:  # Not used in last 3 activities
                suggestions.append(activity)
        
        # If all recent activities were used, suggest anyway but mention variety
        if not suggestions:
            suggestions = potential_activities[:2]
            for suggestion in suggestions:
                suggestion["reason"] += " (try something new!)"
    
    else:
        suggestions = [
            {"activity": "breathing", "icon": "🫁", "reason": "Start with some calming breaths"},
            {"activity": "music", "icon": "🎵", "reason": "Set a peaceful mood with nature sounds"}
        ]
    
    return jsonify({"suggestions": suggestions})

# API endpoint for activity statistics
@app.route("/api/activity-stats")
def activity_stats():
    """Get user's activity usage statistics"""
    user_name = session.get('user_name', 'Friend')
    
    # Get all user activities
    activities = ActivityLog.query.filter_by(user_name=user_name).all()
    
    # Count activities by type
    activity_counts = {}
    for activity in activities:
        activity_type = activity.activity_type
        activity_counts[activity_type] = activity_counts.get(activity_type, 0) + 1
    
    # Get recent activity (last 7 days)
    from datetime import timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_activities = ActivityLog.query.filter(
        ActivityLog.user_name == user_name,
        ActivityLog.timestamp >= week_ago
    ).count()
    
    return jsonify({
        "total_activities": len(activities),
        "activity_breakdown": activity_counts,
        "recent_week_count": recent_activities,
        "most_used_activity": max(activity_counts.items(), key=lambda x: x[1])[0] if activity_counts else None
    })

# Status endpoint
@app.route("/status")
def status():
    """Check system status"""
    ollama_status = is_ollama_available()
    
    # Get some basic stats
    total_conversations = Conversation.query.count()
    total_users = UserPreferences.query.count()
    total_activities = ActivityLog.query.count()
    
    return jsonify({
        "ollama_available": ollama_status,
        "empathy_model": EMPATHY_MODEL,
        "fallback": "Enhanced local responses" if not ollama_status else "Not needed",
        "total_conversations": total_conversations,
        "total_users": total_users,
        "total_activities": total_activities,
        "interactive_features": ["music", "bubble_game", "memory_game", "breathing", "color_therapy"],
        "database_tables": ["conversations", "user_preferences", "activity_log"],
        "timestamp": datetime.utcnow().isoformat()
    })

# Health check endpoint
@app.route("/health")
def health_check():
    """Simple health check"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0-interactive"
    })

# Run the app
if __name__ == "__main__":
    print("Starting Enhanced Interactive AI Empathy Web App v2.0")
    print("Features: Music, Games, Breathing Exercises, Animated Pets")
    print("Ollama Model: Primary")
    print("Enhanced Responses: Fallback")
    print("Access at: http://localhost:5000")
    print("Status check: http://localhost:5000/status")
    print("Mood analytics: http://localhost:5000/api/mood-analytics")
    print("Activity suggestions: http://localhost:5000/api/activity-suggestions")
    print("Activity stats: http://localhost:5000/api/activity-stats")
    print("Health check: http://localhost:5000/health")
    
    if is_ollama_available():
        print(f"Ollama model '{EMPATHY_MODEL}' is ready!")
    else:
        print("Ollama not available - using enhanced local responses")
    
    print("\nInteractive Features Available:")
    print("   * Calming Music (Rain, Forest, Ocean, Birds, Meditation)")
    print("   * Bubble Popping Game (Stress Relief)")
    print("   * Memory Game (Mental Focus)")
    print("   * Breathing Exercises (Anxiety Relief)")
    print("   * Color Therapy (Mood Enhancement)")
    print("   * Animated Pet Companions (Robot, Dog, Cat)")
    
    print("\nDatabase Features:")
    print("   * User Preferences (Avatar, Names, Settings)")
    print("   * Mood Tracking (Sentiment Analysis)")
    print("   * Activity Logging (Usage Analytics)")
    print("   * Conversation History (Context Memory)")
    
    print("\nAPI Endpoints:")
    print("   POST /api/log-activity - Log user activities")
    print("   GET /api/mood-analytics - Mood tracking data")
    print("   GET /api/activity-suggestions - Personalized recommendations")
    print("   GET /api/activity-stats - Usage statistics")
    print("   GET /status - System status and metrics")
    print("   GET /health - Health check")
    
    print("\nUsage Tips:")
    print("   * Click your AI pet to interact with it")
    print("   * Use music during stressful moments")
    print("   * Try breathing exercises when anxious")
    print("   * Play games for mental wellness breaks")
    print("   * Settings save automatically per user")
    
    print("\nEaster Eggs:")
    print("   * Pet animations change based on avatar type")
    print("   * Bubble pops create sparkle effects")
    print("   * Color therapy changes background")
    print("   * AI suggests activities based on your mood")
    print("   * Each pet responds differently to clicks")
    
    app.run(debug=True)