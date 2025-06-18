from flask import Flask, render_template, redirect, url_for, request, session, jsonify
import sqlite3
import hashlib
import datetime
import json
import re
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

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
    
    conn.commit()
    conn.close()

# AI-powered symptom analysis (simulated - in real hackathon you'd use actual AI API)
class HealthAI:
    def __init__(self):
        # Symptom database with severity scoring
        self.symptom_database = {
            'fever': {'severity': 6, 'category': 'infection'},
            'headache': {'severity': 4, 'category': 'neurological'},
            'chest pain': {'severity': 9, 'category': 'cardiac'},
            'shortness of breath': {'severity': 8, 'category': 'respiratory'},
            'cough': {'severity': 3, 'category': 'respiratory'},
            'fatigue': {'severity': 3, 'category': 'general'},
            'nausea': {'severity': 4, 'category': 'gastrointestinal'},
            'dizziness': {'severity': 5, 'category': 'neurological'},
            'abdominal pain': {'severity': 6, 'category': 'gastrointestinal'},
            'rash': {'severity': 3, 'category': 'dermatological'}
        }
        
        # Treatment recommendations
        self.recommendations = {
            'infection': ['Rest and hydration', 'Monitor temperature', 'Consider consulting doctor if fever persists'],
            'cardiac': ['Seek immediate medical attention', 'Avoid physical exertion', 'Call emergency services if severe'],
            'respiratory': ['Ensure adequate ventilation', 'Stay hydrated', 'Monitor breathing patterns'],
            'neurological': ['Rest in quiet environment', 'Stay hydrated', 'Monitor symptoms'],
            'gastrointestinal': ['Stay hydrated', 'Eat bland foods', 'Monitor symptoms'],
            'dermatological': ['Keep area clean', 'Avoid irritants', 'Monitor for changes'],
            'general': ['Ensure adequate rest', 'Maintain healthy diet', 'Stay hydrated']
        }
    
    def analyze_symptoms(self, symptoms_text, age=None, gender=None):
        symptoms_text = symptoms_text.lower()
        detected_symptoms = []
        total_severity = 0
        categories = set()
        
        # Detect symptoms
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
            urgency = 'Consider consulting a healthcare provider'
        else:
            risk_level = 'Low'
            urgency = 'Monitor symptoms and rest'
        
        # Generate recommendations
        recommendations = []
        for category in categories:
            recommendations.extend(self.recommendations.get(category, []))
        
        # Add age/gender specific advice
        if age and age > 65:
            recommendations.append('Elderly patients should monitor symptoms closely')
        if age and age < 18:
            recommendations.append('Consult pediatrician for children')
        
        analysis = {
            'detected_symptoms': detected_symptoms,
            'risk_level': risk_level,
            'severity_score': total_severity,
            'urgency': urgency,
            'recommendations': list(set(recommendations)),
            'categories_affected': list(categories)
        }
        
        return analysis

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
        
        # Check if user exists
        cursor.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'User already exists'}), 400
        
        # Create user
        password_hash = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, age, gender)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, email, password_hash, age, gender))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Registration successful'})
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, password_hash, age, gender FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['username'] = username
            session['age'] = user[2]
            session['gender'] = user[3]
            return jsonify({'message': 'Login successful'})
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('dashboard.html')

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
    conn.close()
    
    return jsonify(analysis)

@app.route('/add_vitals', methods=['POST'])
def add_vitals():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    
    conn = sqlite3.connect('healthcare.db')
    cursor = conn.cursor()
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
    conn.close()
    
    return jsonify({'message': 'Vitals recorded successfully'})

@app.route('/get_health_history')
def get_health_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    conn = sqlite3.connect('healthcare.db')
    cursor = conn.cursor()
    
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
    
    conn.close()
    
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
        ]
    })

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# HTML Templates (create templates folder and add these files)

@app.route('/health_insights')
def health_insights():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    conn = sqlite3.connect('healthcare.db')
    cursor = conn.cursor()
    
    # Get user's health trends
    cursor.execute('''
        SELECT severity_score, timestamp FROM health_records 
        WHERE user_id = ? ORDER BY timestamp DESC LIMIT 30
    ''', (session['user_id'],))
    severity_data = cursor.fetchall()
    
    # Calculate health score trend
    if severity_data:
        recent_scores = [score[0] for score in severity_data[:7]]  # Last 7 entries
        avg_recent = sum(recent_scores) / len(recent_scores)
        
        if avg_recent < 5:
            health_status = "Good"
            status_color = "green"
        elif avg_recent < 10:
            health_status = "Fair"
            status_color = "orange"
        else:
            health_status = "Needs Attention"
            status_color = "red"
    else:
        health_status = "No Data"
        status_color = "gray"
    
    conn.close()
    
    return jsonify({
        'health_status': health_status,
        'status_color': status_color,
        'severity_trend': [{'score': s[0], 'date': s[1]} for s in severity_data]
    })

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)