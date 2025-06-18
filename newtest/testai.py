from flask import Flask, render_template, redirect, url_for, request, session, jsonify
import sqlite3
import hashlib
import datetime
import json
import re
import requests
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# Configuration - Llama 3 via Groq
GROQ_API_TOKEN = "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"  
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
LLAMA_MODEL = "llama3-8b-8192"  # Using Llama 3 8B model

# Initialize database
def init_db():
    conn = sqlite3.connect('emotional_support.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            preferred_name TEXT,
            age INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Emotional support sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            emotions TEXT,
            ai_response TEXT,
            mood_score INTEGER,
            session_notes TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Mood tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mood_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            mood_rating INTEGER,
            energy_level INTEGER,
            stress_level INTEGER,
            gratitude_note TEXT,
            daily_reflection TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Chat history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            response TEXT,
            emotion_detected TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Personal goals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personal_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            goal_text TEXT,
            category TEXT,
            status TEXT DEFAULT 'active',
            progress_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Emotional Support AI powered by Llama 3
class EmotionalSupportAI:
    def __init__(self):
        if not GROQ_API_TOKEN:
            raise ValueError("GROQ_API_TOKEN is required for Llama 3 functionality")
    
    def get_llama3_response(self, user_message, user_context=None, analysis_mode=False):
        """Get empathetic response from Llama 3 via Groq API"""
        
        # Create specialized system prompts for emotional support
        if analysis_mode:
            system_prompt = """You are Aria, a compassionate AI friend powered by Llama 3, specializing in emotional support and understanding.

Your role as an emotional support companion:
- Listen with genuine empathy and without judgment
- Help users process their emotions in a healthy way
- Provide gentle guidance and coping strategies
- Offer validation and emotional comfort
- Help identify patterns in emotions and thoughts
- Suggest self-care activities and mindfulness techniques
- Recognize when someone might benefit from professional help (but never diagnose)

For emotional analysis, provide:
- Emotional state recognition
- Mood assessment (1-10 scale)
- Underlying feelings or concerns
- Gentle suggestions for coping
- Affirmations and validation
- Self-care recommendations

Always be warm, understanding, and genuinely caring. Remember that sometimes people just need to be heard."""
        else:
            system_prompt = """You are Aria, a warm and empathetic AI friend created to provide emotional support and companionship. You're powered by Llama 3 and designed to be a caring listener and supportive companion.

Your personality and approach:
- Be genuinely caring, warm, and approachable
- Listen actively and respond with empathy
- Validate emotions without trying to "fix" everything
- Offer gentle guidance when appropriate
- Share in both joys and struggles
- Be encouraging and hopeful while remaining realistic
- Use a conversational, friend-like tone
- Sometimes share gentle insights or perspectives
- Suggest healthy coping strategies and self-care
- Celebrate small victories and progress

Key principles:
- Everyone deserves to be heard and understood
- Emotions are valid and natural
- Small steps forward are meaningful
- Self-compassion is essential
- Connection and support make a difference
- Professional help is valuable when needed

You're not a therapist, but a supportive friend who cares deeply about emotional wellbeing."""
        
        # Add user context if available
        if user_context:
            preferred_name = user_context.get('preferred_name') or user_context.get('username', 'friend')
            age_info = f"Age: {user_context.get('age', 'not specified')}"
            context_info = f"\nUser context - {age_info}. They prefer to be called {preferred_name}. Make your response personal and caring."
            system_prompt += context_info
        
        headers = {
            "Authorization": f"Bearer {GROQ_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": LLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.8,  # Slightly higher for more natural, empathetic responses
            "max_tokens": 800,
            "top_p": 0.9,
            "stream": False
        }
        
        try:
            response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                raise Exception("No valid response from Llama 3")
                
        except Exception as e:
            print(f"Llama 3 API Error: {e}")
            return "I'm so sorry, but I'm having some technical difficulties right now. Please know that I'm here for you, and you can try talking to me again in a moment. If you're going through something urgent, please don't hesitate to reach out to someone you trust or a professional support service."

    def analyze_emotions_with_llama3(self, emotional_text, preferred_name=None, age=None):
        """Use Llama 3 for emotional analysis and support"""
        
        # Prepare detailed prompt for emotional analysis
        analysis_prompt = f"""
        A person has shared the following with you. Please provide a compassionate emotional analysis and support:
        
        What they shared: {emotional_text}
        Preferred name: {preferred_name if preferred_name else 'Not specified'}
        Age: {age if age else 'Not specified'}
        
        Please provide:
        1. What emotions you're sensing
        2. Mood assessment (1-10 scale, where 1 is very low/difficult and 10 is very positive)
        3. Key feelings or concerns they might be experiencing
        4. Gentle validation and support
        5. Practical coping suggestions
        6. Self-care recommendations
        7. Encouraging words or affirmations
        
        Be warm, understanding, and genuinely supportive. Sometimes people just need to feel heard and understood.
        """
        
        # Get Llama 3 analysis
        llama_response = self.get_llama3_response(
            analysis_prompt, 
            {'preferred_name': preferred_name, 'age': age}, 
            analysis_mode=True
        )
        
        # Parse Llama 3 response to extract structured data
        try:
            # Extract key information from Llama 3 response
            mood_score = self._extract_mood_score(llama_response)
            emotions_detected = self._extract_emotions(llama_response)
            support_level = self._assess_support_needed(llama_response)
            
            return {
                'ai_analysis': llama_response,
                'mood_score': mood_score,
                'emotions_detected': emotions_detected,
                'support_level': support_level,
                'original_message': emotional_text,
                'model_used': 'Aria (Llama 3 8B)'
            }
            
        except Exception as e:
            print(f"Error parsing Llama 3 emotional analysis: {e}")
            return {
                'ai_analysis': llama_response,
                'mood_score': 5,  # Neutral default
                'emotions_detected': 'mixed',
                'support_level': 'moderate',
                'original_message': emotional_text,
                'model_used': 'Aria (Llama 3 8B)',
                'parsing_error': str(e)
            }
    
    def _extract_mood_score(self, response):
        """Extract mood score from Llama 3 response"""
        import re
        patterns = [
            r'mood[:\s]+(\d+)',
            r'score[:\s]+(\d+)',
            r'(\d+)/10',
            r'(\d+)\s*out\s*of\s*10',
            r'rating[:\s]+(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response.lower())
            if match:
                score = int(match.group(1))
                return min(max(score, 1), 10)  # Clamp between 1-10
        
        return 5  # Default neutral mood

    def _extract_emotions(self, response):
        """Extract primary emotions from Llama 3 response"""
        emotion_keywords = {
            'happy': ['happy', 'joy', 'excited', 'cheerful', 'delighted'],
            'sad': ['sad', 'down', 'depressed', 'melancholy', 'blue'],
            'anxious': ['anxious', 'worried', 'nervous', 'stressed', 'tense'],
            'angry': ['angry', 'frustrated', 'irritated', 'mad', 'furious'],
            'lonely': ['lonely', 'isolated', 'alone', 'disconnected'],
            'grateful': ['grateful', 'thankful', 'appreciative', 'blessed'],
            'confused': ['confused', 'uncertain', 'lost', 'unclear'],
            'hopeful': ['hopeful', 'optimistic', 'positive', 'encouraged'],
            'overwhelmed': ['overwhelmed', 'stressed', 'burdened', 'pressured']
        }
        
        response_lower = response.lower()
        detected_emotions = []
        
        for emotion, keywords in emotion_keywords.items():
            if any(keyword in response_lower for keyword in keywords):
                detected_emotions.append(emotion)
        
        return ', '.join(detected_emotions) if detected_emotions else 'mixed emotions'

    def _assess_support_needed(self, response):
        """Assess the level of support needed based on response"""
        response_lower = response.lower()
        
        high_support_indicators = ['crisis', 'professional help', 'therapist', 'counselor', 'urgent']
        moderate_support_indicators = ['support', 'help', 'guidance', 'coping', 'strategies']
        
        if any(indicator in response_lower for indicator in high_support_indicators):
            return 'high'
        elif any(indicator in response_lower for indicator in moderate_support_indicators):
            return 'moderate'
        else:
            return 'low'

# Initialize Emotional Support AI
support_ai = EmotionalSupportAI()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        preferred_name = data.get('preferred_name', username)
        age = data.get('age')
        
        if not username or not email or not password:
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = sqlite3.connect('emotional_support.db')
        cursor = conn.cursor()
        
        try:
            # Check if user exists
            cursor.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
            if cursor.fetchone():
                return jsonify({'error': 'User already exists'}), 400
            
            # Create user
            password_hash = generate_password_hash(password)
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, preferred_name, age)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, email, password_hash, preferred_name, age))
            
            conn.commit()
            return jsonify({'message': 'Welcome! I\'m excited to be your emotional support companion.'})
            
        except Exception as e:
            return jsonify({'error': 'Registration failed'}), 500
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        conn = sqlite3.connect('emotional_support.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT id, password_hash, preferred_name, age FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['username'] = username
                session['preferred_name'] = user[2] or username
                session['age'] = user[3]
                return jsonify({'message': f'Welcome back, {user[2] or username}! I\'m here for you.'})
            else:
                return jsonify({'error': 'Invalid credentials'}), 401
                
        except Exception as e:
            return jsonify({'error': 'Login failed'}), 500
        finally:
            conn.close()
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('dashboard.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handle emotional support conversations with Llama 3 integration"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    # Prepare user context
    user_context = {
        'username': session.get('username'),
        'preferred_name': session.get('preferred_name'),
        'age': session.get('age')
    }
    
    # Get Aria's empathetic response
    ai_response = support_ai.get_llama3_response(user_message, user_context)
    
    # Quick emotion detection for logging
    emotions_detected = support_ai._extract_emotions(ai_response)
    
    # Save chat history
    conn = sqlite3.connect('emotional_support.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO chat_history (user_id, message, response, emotion_detected)
            VALUES (?, ?, ?, ?)
        ''', (session['user_id'], user_message, ai_response, emotions_detected))
        conn.commit()
    except Exception as e:
        print(f"Error saving chat: {e}")
    finally:
        conn.close()
    
    return jsonify({
        'response': ai_response,
        'companion': 'Aria',
        'emotions_detected': emotions_detected,
        'timestamp': datetime.datetime.now().isoformat()
    })

@app.route('/emotional_support', methods=['POST'])
def emotional_support():
    """Provide detailed emotional analysis and support using Llama 3"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    emotional_text = data.get('emotions', '')
    
    if not emotional_text:
        return jsonify({'error': 'No emotional content provided'}), 400
    
    # Llama 3 Emotional Analysis
    analysis = support_ai.analyze_emotions_with_llama3(
        emotional_text, 
        preferred_name=session.get('preferred_name'), 
        age=session.get('age')
    )
    
    # Save to database
    conn = sqlite3.connect('emotional_support.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO support_sessions (user_id, emotions, ai_response, mood_score, session_notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            session['user_id'],
            emotional_text,
            analysis.get('ai_analysis', ''),
            analysis.get('mood_score', 5),
            json.dumps(analysis)
        ))
        conn.commit()
    except Exception as e:
        print(f"Error saving emotional support session: {e}")
    finally:
        conn.close()
    
    return jsonify(analysis)

@app.route('/track_mood', methods=['POST'])
def track_mood():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    
    conn = sqlite3.connect('emotional_support.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO mood_tracking (user_id, mood_rating, energy_level, stress_level, 
                                     gratitude_note, daily_reflection)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'],
            data.get('mood_rating'),
            data.get('energy_level'),
            data.get('stress_level'),
            data.get('gratitude_note'),
            data.get('daily_reflection')
        ))
        conn.commit()
        return jsonify({'message': 'Thank you for sharing your feelings with me. Tracking your emotions is a wonderful step in self-care.'})
    except Exception as e:
        return jsonify({'error': 'Failed to save mood tracking'}), 500
    finally:
        conn.close()

@app.route('/add_goal', methods=['POST'])
def add_goal():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    
    conn = sqlite3.connect('emotional_support.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO personal_goals (user_id, goal_text, category)
            VALUES (?, ?, ?)
        ''', (
            session['user_id'],
            data.get('goal_text'),
            data.get('category', 'personal')
        ))
        conn.commit()
        return jsonify({'message': 'I\'m so proud of you for setting this goal! I\'ll be here to support you along the way.'})
    except Exception as e:
        return jsonify({'error': 'Failed to save goal'}), 500
    finally:
        conn.close()

@app.route('/get_emotional_history')
def get_emotional_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    conn = sqlite3.connect('emotional_support.db')
    cursor = conn.cursor()
    
    try:
        # Get support sessions
        cursor.execute('''
            SELECT emotions, ai_response, mood_score, timestamp FROM support_sessions 
            WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10
        ''', (session['user_id'],))
        sessions = cursor.fetchall()
        
        # Get mood tracking
        cursor.execute('''
            SELECT mood_rating, energy_level, stress_level, gratitude_note, 
                   daily_reflection, timestamp FROM mood_tracking 
            WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10
        ''', (session['user_id'],))
        moods = cursor.fetchall()
        
        # Get chat history
        cursor.execute('''
            SELECT message, response, emotion_detected, timestamp FROM chat_history 
            WHERE user_id = ? ORDER BY timestamp DESC LIMIT 20
        ''', (session['user_id'],))
        chats = cursor.fetchall()
        
        # Get personal goals
        cursor.execute('''
            SELECT goal_text, category, status, progress_notes, created_at FROM personal_goals 
            WHERE user_id = ? ORDER BY created_at DESC
        ''', (session['user_id'],))
        goals = cursor.fetchall()
        
        return jsonify({
            'support_sessions': [
                {
                    'emotions': session[0],
                    'ai_response': session[1],
                    'mood_score': session[2],
                    'timestamp': session[3]
                } for session in sessions
            ],
            'mood_history': [
                {
                    'mood_rating': mood[0],
                    'energy_level': mood[1],
                    'stress_level': mood[2],
                    'gratitude_note': mood[3],
                    'daily_reflection': mood[4],
                    'timestamp': mood[5]
                } for mood in moods
            ],
            'conversations': [
                {
                    'message': chat[0],
                    'response': chat[1],
                    'emotions_detected': chat[2],
                    'timestamp': chat[3]
                } for chat in chats
            ],
            'personal_goals': [
                {
                    'goal_text': goal[0],
                    'category': goal[1],
                    'status': goal[2],
                    'progress_notes': goal[3],
                    'created_at': goal[4]
                } for goal in goals
            ],
            'companion_info': 'Your caring friend Aria, powered by Llama 3'
        })
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve emotional history'}), 500
    finally:
        conn.close()

@app.route('/ai_status')
def ai_status():
    """Check Aria's emotional support AI status"""
    try:
        # Test Llama 3 connection with an emotional support context
        test_response = support_ai.get_llama3_response("Hi Aria, how are you doing today?")
        
        return jsonify({
            'status': 'ready to listen',
            'companion': 'Aria',
            'model': 'Llama 3 (8B)',
            'api_provider': 'Groq',
            'message': 'I\'m here and ready to support you emotionally',
            'test_response': test_response[:150] + "..." if len(test_response) > 150 else test_response
        })
    except Exception as e:
        return jsonify({
            'status': 'experiencing difficulties',
            'companion': 'Aria',
            'error': 'I\'m having some technical troubles, but I\'ll be back soon',
            'technical_error': str(e)
        }), 500

@app.route('/logout')
def logout():
    preferred_name = session.get('preferred_name', 'friend')
    session.clear()
    return jsonify({'message': f'Take care, {preferred_name}. Remember, I\'m always here when you need someone to talk to.'})

if __name__ == '__main__':
    init_db()
    print("Emotional Support AI - Aria")
    print("Your caring AI companion powered by Llama 3")
    print("Ready to listen, support, and be a friend to those in need")
    app.run(host='0.0.0.0', port=5000, debug=True)