from flask import Flask, render_template_string, request, session, redirect, url_for
import secrets
import requests
import json
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Add secret key for sessions

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
    except Exception as e:
        return f"Unexpected error: {e}"

# HTML template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your AI Friend</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 10px;
        }
        
        .chat-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 450px;
            height: 700px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .chat-header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 20px;
            text-align: center;
            position: relative;
        }
        
        .chat-header h1 {
            font-size: 1.5em;
            margin-bottom: 5px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }
        
        .bot-avatar {
            width: 40px;
            height: 40px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2em;
        }
        
        .chat-subtitle {
            font-size: 0.9em;
            opacity: 0.9;
            margin-top: 5px;
        }
        
        .settings-btn {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            padding: 8px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.1em;
            transition: all 0.3s ease;
        }
        
        .settings-btn:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: rotate(90deg);
        }
        
        .settings-panel {
            display: none;
            background: #f8f9fa;
            padding: 20px;
            border-bottom: 1px solid #e9ecef;
        }
        
        .settings-panel.active {
            display: block;
        }
        
        .form-group {
            margin-bottom: 15px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #495057;
        }
        
        .form-group input {
            width: 100%;
            padding: 10px 15px;
            border: 2px solid #e9ecef;
            border-radius: 25px;
            font-size: 14px;
            transition: border-color 0.3s ease;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: #4facfe;
        }
        
        .btn {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
            margin-right: 10px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(79, 172, 254, 0.4);
        }
        
        .btn-secondary {
            background: #6c757d;
        }
        
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f8f9fa;
        }
        
        .message {
            margin-bottom: 20px;
            animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .message.user {
            text-align: right;
        }
        
        .message.bot {
            text-align: left;
        }
        
        .message-content {
            display: inline-block;
            padding: 15px 20px;
            border-radius: 20px;
            max-width: 80%;
            word-wrap: break-word;
            line-height: 1.4;
            position: relative;
        }
        
        .message.user .message-content {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            border-bottom-right-radius: 5px;
        }
        
        .message.bot .message-content {
            background: white;
            color: #333;
            border: 1px solid #e9ecef;
            border-bottom-left-radius: 5px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        
        .welcome-message .message-content {
            background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
            color: #8b4513;
            border: none;
        }
        
        .message-sender {
            font-size: 0.8em;
            margin-bottom: 5px;
            font-weight: 600;
            opacity: 0.7;
        }
        
        .chat-input {
            padding: 20px;
            background: white;
            border-top: 1px solid #e9ecef;
        }
        
        .input-group {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .message-input {
            flex: 1;
            padding: 15px 20px;
            border: 2px solid #e9ecef;
            border-radius: 25px;
            font-size: 16px;
            resize: none;
            transition: border-color 0.3s ease;
        }
        
        .message-input:focus {
            outline: none;
            border-color: #4facfe;
        }
        
        .send-btn {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            border: none;
            padding: 15px 20px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.2em;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .send-btn:hover {
            transform: scale(1.1);
            box-shadow: 0 5px 15px rgba(79, 172, 254, 0.4);
        }
        
        .send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .typing-indicator {
            display: none;
            text-align: center;
            padding: 10px;
            font-style: italic;
            color: #6c757d;
        }
        
        .clear-btn {
            background: #dc3545;
            font-size: 0.9em;
            padding: 8px 15px;
        }
        
        .clear-btn:hover {
            box-shadow: 0 5px 15px rgba(220, 53, 69, 0.4);
        }
        
        @media (max-width: 480px) {
            .chat-container {
                height: 100vh;
                border-radius: 0;
                max-width: 100%;
            }
            
            body {
                padding: 0;
            }
        }
        
        /* Scrollbar styling */
        .chat-messages::-webkit-scrollbar {
            width: 6px;
        }
        
        .chat-messages::-webkit-scrollbar-track {
            background: #f1f1f1;
        }
        
        .chat-messages::-webkit-scrollbar-thumb {
            background: #c1c1c1;
            border-radius: 3px;
        }
        
        .chat-messages::-webkit-scrollbar-thumb:hover {
            background: #a8a8a8;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <button class="settings-btn" onclick="toggleSettings()" title="Settings">⚙️</button>
            <h1>
                <div class="bot-avatar">🤖</div>
                <span id="bot-name">{{ bot_name or 'Alex' }}</span>
            </h1>
            <div class="chat-subtitle">Your AI Friend</div>
        </div>
        
        <div class="settings-panel" id="settingsPanel">
            <form method="post" id="settingsForm">
                <input type="hidden" name="action" value="set_names">
                <div class="form-group">
                    <label for="bot_name_input">AI Friend's Name:</label>
                    <input type="text" id="bot_name_input" name="bot_name" placeholder="Enter AI name..." value="{{ bot_name or 'Alex' }}">
                </div>
                <div class="form-group">
                    <label for="user_name_input">Your Name:</label>
                    <input type="text" id="user_name_input" name="user_name" placeholder="Enter your name..." value="{{ user_name or 'Friend' }}">
                </div>
                <button type="submit" class="btn">Save Names</button>
                <button type="button" class="btn btn-secondary" onclick="toggleSettings()">Cancel</button>
            </form>
        </div>
        
        <div class="chat-messages" id="chatMessages">
            <!-- Initial welcome message (only show if no chat history) -->
            {% if not chat %}
            <div class="message bot welcome-message">
                <div class="message-sender">🤖 {{ bot_name or 'Alex' }}</div>
                <div class="message-content">
                    Hi {{ user_name or 'Friend' }}! I'm {{ bot_name or 'Alex' }}, your AI companion. I'm here to chat, help, and support you. What's on your mind today? 😊
                </div>
            </div>
            {% endif %}
            
            <!-- Chat messages will appear here -->
            {% for msg in chat %}
                {% if msg.user %}
                    <div class="message user">
                        <div class="message-sender">{{ user_name or 'You' }}</div>
                        <div class="message-content">{{ msg.user }}</div>
                    </div>
                {% endif %}
                <div class="message bot">
                    <div class="message-sender">🤖 {{ bot_name or 'Alex' }}</div>
                    <div class="message-content">{{ msg.bot|safe }}</div>
                </div>
            {% endfor %}
        </div>
        
        <div class="typing-indicator" id="typingIndicator">
            🤖 <span id="bot-name-typing">{{ bot_name or 'Alex' }}</span> is typing...
        </div>
        
        <div class="chat-input">
            <form method="post" id="chatForm">
                <input type="hidden" name="action" value="chat">
                <div class="input-group">
                    <input type="text" name="message" class="message-input" placeholder="Type your message..." autocomplete="off" required>
                    <button type="submit" class="send-btn" title="Send message">📤</button>
                </div>
            </form>
            <div style="margin-top: 10px; text-align: center;">
                <form method="post" style="display: inline;" onsubmit="return confirmClear()">
                    <input type="hidden" name="action" value="clear">
                    <button type="submit" class="btn clear-btn">🗑️ Clear Chat</button>
                </form>
            </div>
        </div>
    </div>

    <script>
        let botName = '{{ bot_name or "Alex" }}';
        let userName = '{{ user_name or "Friend" }}';

        function toggleSettings() {
            const panel = document.getElementById('settingsPanel');
            panel.classList.toggle('active');
        }

        function confirmClear() {
            return confirm('Are you sure you want to clear all messages? This cannot be undone.');
        }

        function updateBotName(name) {
            botName = name || 'Alex';
            document.getElementById('bot-name').textContent = botName;
            document.getElementById('bot-name-typing').textContent = botName;
            
            // Update all bot message senders
            const botSenders = document.querySelectorAll('.message.bot .message-sender');
            botSenders.forEach(sender => {
                sender.textContent = `🤖 ${botName}`;
            });
        }

        // Handle settings form submission
        document.getElementById('settingsForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            
            // Update names immediately
            const newBotName = formData.get('bot_name') || 'Alex';
            const newUserName = formData.get('user_name') || 'Friend';
            
            updateBotName(newBotName);
            userName = newUserName;
            
            // Submit form
            fetch('/', {
                method: 'POST',
                body: formData
            }).then(response => {
                if (response.ok) {
                    location.reload();
                }
            }).catch(error => {
                console.error('Error:', error);
                alert('Failed to save settings');
            });
        });

        // Handle chat form submission with typing indicator
        document.getElementById('chatForm').addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('.send-btn');
            const messageInput = this.querySelector('.message-input');
            const typingIndicator = document.getElementById('typingIndicator');
            
            if (messageInput.value.trim()) {
                // Show typing indicator
                typingIndicator.style.display = 'block';
                submitBtn.disabled = true;
                
                // Scroll to bottom
                setTimeout(() => {
                    const chatMessages = document.getElementById('chatMessages');
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                }, 100);
            }
        });

        // Auto-scroll to bottom on page load
        window.addEventListener('load', function() {
            const chatMessages = document.getElementById('chatMessages');
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });

        // Handle Enter key in message input
        document.querySelector('.message-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                document.getElementById('chatForm').submit();
            }
        });

        // Auto-resize input and focus
        document.querySelector('.message-input').addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 100) + 'px';
        });

        // Focus input on load
        document.querySelector('.message-input').focus();
    </script>
</body>
</html>
'''

@app.route("/", methods=["GET", "POST"])
def chat():
    # Initialize session data with proper defaults
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
                        prompt = f"You are {session['bot_name']}, a friendly AI companion. {get_tone_instruction(user_msg)}\nUser ({session['user_name']}): {user_msg}"
                        bot_response = get_completion(prompt)

                    # Ensure chat_history is a list
                    if not isinstance(session.get('chat_history'), list):
                        session['chat_history'] = []
                    
                    session['chat_history'].append({"user": user_msg, "bot": bot_response})
                    session.modified = True
            
            elif action == "clear":
                session['chat_history'] = []
                session.modified = True
                return redirect(url_for('chat'))
                
        except Exception as e:
            print(f"Error in POST request: {e}")
            # Reset session data if there's an error
            session['chat_history'] = []
            session.modified = True

    # Ensure we always have valid session data before rendering
    chat_history = session.get('chat_history', [])
    bot_name = session.get('bot_name', 'Alex')
    user_name = session.get('user_name', 'Friend')
    
    return render_template_string(HTML_TEMPLATE, 
                                chat=chat_history, 
                                bot_name=bot_name,
                                user_name=user_name)

if __name__ == "__main__":
    app.run(debug=True)