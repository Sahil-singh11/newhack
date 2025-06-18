import requests

# Replace with your own Hugging Face token
# 
API_TOKEN = "replace with token"

API_URL = "https://api-inference.huggingface.co/models/HuggingFaceH4/zephyr-7b-beta"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def get_completion(prompt):
    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": 0.5,
            "max_new_tokens": 100
        }
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    response.raise_for_status()
    result = response.json()

    if isinstance(result, list):
        return result[0]["generated_text"]
    elif isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"
    else:
        return str(result)

prompt = "Reply with a short hello message"
response = get_completion(prompt)
print(response)
