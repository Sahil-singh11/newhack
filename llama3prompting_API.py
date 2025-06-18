import requests
import json

# Replace with your Groq API key
API_TOKEN = ""
API_URL = "https://api.groq.com/openai/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def get_completion(prompt):
    payload = {
        "model": "llama3-8b-8192",  # Free Llama 3 8B model
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.5,
        "max_tokens": 100,
        "stream": False
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
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

# Test the function
prompt = "Reply with a short hello message"
response = get_completion(prompt)
print(f"Prompt: {prompt}")
print(f"Response: {response}")