from flask import Flask, request, jsonify, render_template_string
import requests
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for web API access

# Ollama API configuration
OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "empathy-support"

def chat_with_empathy_bot(message, conversation_history=None):
    """Send message to empathy bot and get response"""
    try:
        # Prepare the prompt with conversation context
        if conversation_history:
            # Include recent conversation for context
            context = "\n".join([f"Human: {h['human']}\nAI: {h['ai']}" for h in conversation_history[-3:]])
            full_prompt = f"Previous conversation:\n{context}\n\nHuman: {message}\nAI:"
        else:
            full_prompt = message
        
        # Make API call to Ollama
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.4,
                    "num_predict": 50,
                    "repeat_penalty": 1.4
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "I'm sorry, I couldn't process that right now.")
        else:
            return "I'm having trouble connecting right now. Please try again."
            
    except requests.exceptions.RequestException as e:
        return "I'm not available right now. Please try again later."

# Store conversation history (in production, use a database)
conversations = {}

@app.route('/')
def home():
    """Simple web interface for testing"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Empathy Support Bot</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .chat-container { border: 1px solid #ddd; height: 400px; overflow-y: scroll; padding: 10px; margin: 20px 0; }
            .message { margin: 10px 0; padding: 10px; border-radius: 10px; }
            .user { background-color: #e3f2fd; text-align: right; }
            .bot { background-color: #f3e5f5; }
            input[type="text"] { width: 70%; padding: 10px; }
            button { padding: 10px 20px; background-color: #2196f3; color: white; border: none; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>💙 Empathy Support Bot</h1>
        <div id="chat-container" class="chat-container"></div>
        <div>
            <input type="text" id="messageInput" placeholder="How are you feeling today?" onkeypress="handleKeyPress(event)">
            <button onclick="sendMessage()">Send</button>
        </div>
        
        <script>
            let sessionId = Math.random().toString(36).substring(7);
            
            function addMessage(message, isUser) {
                const container = document.getElementById('chat-container');
                const div = document.createElement('div');
                div.className = `message ${isUser ? 'user' : 'bot'}`;
                div.textContent = message;
                container.appendChild(div);
                container.scrollTop = container.scrollHeight;
            }
            
            function handleKeyPress(event) {
                if (event.key === 'Enter') {
                    sendMessage();
                }
            }
            
            async function sendMessage() {
                const input = document.getElementById('messageInput');
                const message = input.value.trim();
                if (!message) return;
                
                addMessage(message, true);
                input.value = '';
                
                try {
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            message: message,
                            session_id: sessionId
                        })
                    });
                    
                    const data = await response.json();
                    addMessage(data.response, false);
                } catch (error) {
                    addMessage('Sorry, I had trouble connecting. Please try again.', false);
                }
            }
            
            // Welcome message
            addMessage('Hi there! 😊 I\\'m here to listen and support you. How are you feeling today?', false);
        </script>
    </body>
    </html>
    """
    return html

@app.route('/chat', methods=['POST'])
def chat():
    """API endpoint for chat messages"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        session_id = data.get('session_id', 'default')
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Get or create conversation history
        if session_id not in conversations:
            conversations[session_id] = []
        
        # Get bot response
        bot_response = chat_with_empathy_bot(message, conversations[session_id])
        
        # Store conversation
        conversations[session_id].append({
            'human': message,
            'ai': bot_response
        })
        
        # Keep only last 10 exchanges to manage memory
        if len(conversations[session_id]) > 10:
            conversations[session_id] = conversations[session_id][-10:]
        
        return jsonify({
            'response': bot_response,
            'session_id': session_id
        })
        
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Clean API endpoint for external integration"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        user_id = data.get('user_id', 'anonymous')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Get conversation history for this user
        history = conversations.get(user_id, [])
        
        # Get bot response
        response = chat_with_empathy_bot(message, history)
        
        # Update conversation history
        if user_id not in conversations:
            conversations[user_id] = []
        
        conversations[user_id].append({
            'human': message,
            'ai': response
        })
        
        return jsonify({
            'response': response,
            'user_id': user_id,
            'timestamp': str(int(time.time())) if 'time' in globals() else None
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test connection to Ollama
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            return jsonify({'status': 'healthy', 'ollama': 'connected'})
        else:
            return jsonify({'status': 'unhealthy', 'ollama': 'disconnected'}), 503
    except:
        return jsonify({'status': 'unhealthy', 'ollama': 'disconnected'}), 503

if __name__ == '__main__':
    print("Starting Empathy Support Bot Web App...")
    print("Make sure Ollama is running: ollama serve")
    print("Make sure your model exists: ollama list")
    print("\nAccess the app at: http://localhost:5000")
    print("API endpoint: POST http://localhost:5000/api/chat")
    
    app.run(debug=True, host='0.0.0.0', port=5000)