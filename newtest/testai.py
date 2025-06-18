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

# Configuration
GROQ_API_TOKEN = "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"  
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Initialize database
def init_db():
    conn = sqlite3.connect('healthcare.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Health records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            symptoms TEXT,
            analysis TEXT,
            recommendations TEXT,
            severity_score INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Vital signs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vital_signs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            heart_rate INTEGER,
            blood_pressure_systolic INTEGER,
            blood_pressure_diastolic INTEGER,
            temperature REAL,
            weight REAL,
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
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Enhanced AI-powered health assistant
class HealthAI:
    def __init__(self):
        # Emergency keywords that require immediate attention
        self.emergency_keywords = [
            'chest pain', 'difficulty breathing', 'shortness of breath',
            'severe headache', 'sudden weakness', 'loss of consciousness',
            'severe bleeding', 'poisoning', 'overdose', 'suicide'
        ]
        
        # Symptom database with enhanced categorization
        self.symptom_database = {
            'fever': {'severity': 6, 'category': 'infection', 'description': 'elevated body temperature'},
            'headache': {'severity': 4, 'category': 'neurological', 'description': 'pain in head or neck'},
            'chest pain': {'severity': 9, 'category': 'cardiac', 'description': 'pain in chest area'},
            'shortness of breath': {'severity': 8, 'category': 'respiratory', 'description': 'difficulty breathing'},
            'cough': {'severity': 3, 'category': 'respiratory', 'description': 'forceful expulsion of air'},
            'fatigue': {'severity': 3, 'category': 'general', 'description': 'extreme tiredness'},
            'nausea': {'severity': 4, 'category': 'gastrointestinal', 'description': 'feeling of sickness'},
            'dizziness': {'severity': 5, 'category': 'neurological', 'description': 'feeling unsteady'},
            'abdominal pain': {'severity': 6, 'category': 'gastrointestinal', 'description': 'stomach pain'},
            'rash': {'severity': 3, 'category': 'dermatological', 'description': 'skin irritation'},
            'joint pain': {'severity': 4, 'category': 'musculoskeletal', 'description': 'pain in joints'},
            'back pain': {'severity': 5, 'category': 'musculoskeletal', 'description': 'pain in back area'}
        }
        
        # Enhanced recommendations
        self.recommendations = {
            'infection': [
                'Rest and get plenty of sleep',
                'Stay hydrated with water and clear fluids',
                'Monitor temperature regularly',
                'Consider over-the-counter fever reducers if needed',
                'Consult doctor if symptoms worsen or persist'
            ],
            'cardiac': [
                'SEEK IMMEDIATE MEDICAL ATTENTION',
                'Call 911 if experiencing chest pain',
                'Avoid physical exertion',
                'Take prescribed medications as directed',
                'Do not drive yourself to hospital'
            ],
            'respiratory': [
                'Ensure good ventilation',
                'Stay hydrated',
                'Use humidifier if available',
                'Avoid smoking and pollutants',
                'Monitor breathing patterns'
            ],
            'neurological': [
                'Rest in quiet, dark environment',
                'Stay hydrated',
                'Avoid bright lights and loud noises',
                'Monitor symptoms closely',
                'Seek medical attention if symptoms worsen'
            ],
            'gastrointestinal': [
                'Stay hydrated with small sips of water',
                'Eat bland foods (BRAT diet: bananas, rice, applesauce, toast)',
                'Avoid dairy and fatty foods',
                'Rest and avoid solid foods if nauseous',
                'Monitor for dehydration signs'
            ],
            'dermatological': [
                'Keep affected area clean and dry',
                'Avoid scratching or rubbing',
                'Use gentle, fragrance-free products',
                'Apply cool compress if inflamed',
                'Monitor for signs of infection'
            ],
            'musculoskeletal': [
                'Rest and avoid aggravating activities',
                'Apply ice for acute injuries, heat for chronic pain',
                'Gentle stretching and movement as tolerated',
                'Over-the-counter pain relievers if needed',
                'Consult healthcare provider for persistent pain'
            ],
            'general': [
                'Ensure adequate rest and sleep',
                'Maintain healthy diet',
                'Stay hydrated',
                'Regular gentle exercise as tolerated',
                'Manage stress levels'
            ]
        }

    def get_ai_response(self, user_message, user_context=None):
        """Get response from Groq AI API"""
        if not GROQ_API_TOKEN:
            return self.get_fallback_response(user_message, user_context)
        
        # Create system prompt for health assistant
        system_prompt = """You are a compassionate AI health assistant. Provide helpful, accurate health guidance while being empathetic and supportive. Always remind users that you're not a replacement for professional medical care. For serious symptoms, always recommend seeking immediate medical attention. Keep responses concise but informative."""
        
        # Add user context if available
        if user_context:
            context_info = f"User context: Age {user_context.get('age', 'not specified')}, Gender {user_context.get('gender', 'not specified')}"
            system_prompt += f" {context_info}"
        
        headers = {
            "Authorization": f"Bearer {GROQ_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama3-8b-8192",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 500,
            "stream": False
        }
        
        try:
            response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                return self.get_fallback_response(user_message, user_context)
                
        except Exception as e:
            print(f"AI API Error: {e}")
            return self.get_fallback_response(user_message, user_context)

    def get_fallback_response(self, user_message, user_context=None):
        """Fallback response when AI API is unavailable"""
        message = user_message.lower()
        user_name = user_context.get('username', 'there') if user_context else 'there'
        
        # Check for emergency keywords
        for keyword in self.emergency_keywords:
            if keyword in message:
                return f"🚨 {user_name}, if this is a medical emergency, please call 911 immediately or go to the nearest emergency room. Your safety is my top priority."
        
        # Symptom analysis
        if any(word in message for word in ['symptom', 'pain', 'hurt', 'sick', 'feel', 'ache']):
            return f"I understand you're not feeling well, {user_name}. Can you tell me more about your symptoms? Please describe: the location, when it started, severity (1-10), and any other symptoms. Remember, I provide general guidance, but always consult healthcare professionals for proper diagnosis."
        
        # Wellness tips
        if any(word in message for word in ['wellness', 'healthy', 'tips', 'advice']):
            tips = [
                "Stay hydrated - aim for 8 glasses of water daily 💧",
                "Get 7-9 hours of quality sleep each night 😴",
                "Take regular walks for physical and mental health 🚶",
                "Practice stress management techniques like deep breathing 🧘",
                "Eat a balanced diet with plenty of fruits and vegetables 🥗"
            ]
            return f"Here's a wellness tip for you, {user_name}: {tips[len(user_name) % len(tips)]}\n\nSmall daily habits make a big difference! What specific health area would you like to focus on?"
        
        # Default supportive response
        return f"Thank you for reaching out, {user_name}. I'm here to help with your health questions. Could you tell me more about what's concerning you today? Whether it's symptoms, wellness advice, or health tracking, I'm here to support you. 💙"

    def analyze_symptoms(self, symptoms_text, age=None, gender=None):
        """Analyze symptoms and provide recommendations"""
        symptoms_text = symptoms_text.lower()
        detected_symptoms = []
        total_severity = 0
        categories = set()
        
        # Check for emergency keywords first
        for keyword in self.emergency_keywords:
            if keyword in symptoms_text:
                return {
                    'detected_symptoms': [keyword],
                    'risk_level': 'EMERGENCY',
                    'severity_score': 10,
                    'urgency': 'CALL 911 IMMEDIATELY',
                    'recommendations': ['Call emergency services immediately', 'Do not wait or drive yourself', 'This requires immediate medical attention'],
                    'categories_affected': ['emergency'],
                    'emergency': True
                }
        
        # Detect other symptoms
        for symptom, data in self.symptom_database.items():
            if symptom in symptoms_text:
                detected_symptoms.append(symptom)
                total_severity += data['severity']
                categories.add(data['category'])
        
        # Calculate risk level
        if total_severity >= 15:
            risk_level = 'High'
            urgency = 'Seek immediate medical attention'
        elif total_severity >= 8:
            risk_level = 'Medium'
            urgency = 'Consider consulting a healthcare provider soon'
        else:
            risk_level = 'Low'
            urgency = 'Monitor symptoms and practice self-care'
        
        # Generate recommendations
        recommendations = []
        for category in categories:
            recommendations.extend(self.recommendations.get(category, []))
        
        # Add demographic-specific advice
        if age and age > 65:
            recommendations.append('Elderly individuals should seek medical attention sooner for symptoms')
        if age and age < 18:
            recommendations.append('Children should be evaluated by a pediatrician')
        
        return {
            'detected_symptoms': detected_symptoms,
            'risk_level': risk_level,
            'severity_score': total_severity,
            'urgency': urgency,
            'recommendations': list(set(recommendations)),
            'categories_affected': list(categories),
            'emergency': False
        }

# Initialize AI
health_ai = HealthAI()

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
        age = data.get('age')
        gender = data.get('gender')
        
        if not username or not email or not password:
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        try:
            # Check if user exists
            cursor.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
            if cursor.fetchone():
                return jsonify({'error': 'User already exists'}), 400
            
            # Create user
            password_hash = generate_password_hash(password)
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, age, gender)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, email, password_hash, age, gender))
            
            conn.commit()
            return jsonify({'message': 'Registration successful'})
            
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
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT id, password_hash, age, gender FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['username'] = username
                session['age'] = user[2]
                session['gender'] = user[3]
                return jsonify({'message': 'Login successful'})
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
    """Handle chat messages with AI integration"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    # Prepare user context
    user_context = {
        'username': session.get('username'),
        'age': session.get('age'),
        'gender': session.get('gender')
    }
    
    # Get AI response
    ai_response = health_ai.get_ai_response(user_message, user_context)
    
    # Save chat history
    conn = sqlite3.connect('healthcare.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO chat_history (user_id, message, response)
            VALUES (?, ?, ?)
        ''', (session['user_id'], user_message, ai_response))
        conn.commit()
    except Exception as e:
        print(f"Error saving chat: {e}")
    finally:
        conn.close()
    
    return jsonify({'response': ai_response})

@app.route('/analyze_symptoms', methods=['POST'])
def analyze_symptoms():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    symptoms = data.get('symptoms', '')
    
    if not symptoms:
        return jsonify({'error': 'No symptoms provided'}), 400
    
    # AI Analysis
    analysis = health_ai.analyze_symptoms(
        symptoms, 
        age=session.get('age'), 
        gender=session.get('gender')
    )
    
    # Save to database
    conn = sqlite3.connect('healthcare.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO health_records (user_id, symptoms, analysis, recommendations, severity_score)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            session['user_id'],
            symptoms,
            json.dumps(analysis),
            json.dumps(analysis['recommendations']),
            analysis['severity_score']
        ))
        conn.commit()
    except Exception as e:
        print(f"Error saving analysis: {e}")
    finally:
        conn.close()
    
    return jsonify(analysis)

@app.route('/add_vitals', methods=['POST'])
def add_vitals():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    
    conn = sqlite3.connect('healthcare.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO vital_signs (user_id, heart_rate, blood_pressure_systolic, 
                                   blood_pressure_diastolic, temperature, weight)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'],
            data.get('heart_rate'),
            data.get('bp_systolic'),
            data.get('bp_diastolic'),
            data.get('temperature'),
            data.get('weight')
        ))
        conn.commit()
        return jsonify({'message': 'Vitals recorded successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to record vitals'}), 500
    finally:
        conn.close()

@app.route('/get_health_history')
def get_health_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    conn = sqlite3.connect('healthcare.db')
    cursor = conn.cursor()
    
    try:
        # Get health records
        cursor.execute('''
            SELECT symptoms, analysis, timestamp FROM health_records 
            WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10
        ''', (session['user_id'],))
        records = cursor.fetchall()
        
        # Get vital signs
        cursor.execute('''
            SELECT heart_rate, blood_pressure_systolic, blood_pressure_diastolic, 
                   temperature, weight, timestamp FROM vital_signs 
            WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10
        ''', (session['user_id'],))
        vitals = cursor.fetchall()
        
        # Get chat history
        cursor.execute('''
            SELECT message, response, timestamp FROM chat_history 
            WHERE user_id = ? ORDER BY timestamp DESC LIMIT 20
        ''', (session['user_id'],))
        chats = cursor.fetchall()
        
        return jsonify({
            'health_records': [
                {
                    'symptoms': record[0],
                    'analysis': json.loads(record[1]) if record[1] else {},
                    'timestamp': record[2]
                } for record in records
            ],
            'vital_signs': [
                {
                    'heart_rate': vital[0],
                    'blood_pressure': f"{vital[1]}/{vital[2]}" if vital[1] and vital[2] else None,
                    'temperature': vital[3],
                    'weight': vital[4],
                    'timestamp': vital[5]
                } for vital in vitals
            ],
            'chat_history': [
                {
                    'message': chat[0],
                    'response': chat[1],
                    'timestamp': chat[2]
                } for chat in chats
            ]
        })
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve history'}), 500
    finally:
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)