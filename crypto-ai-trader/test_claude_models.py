"""
Test with available Claude models
"""
import os
from dotenv import load_dotenv

load_dotenv()

claude_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')

if not claude_key:
    print("❌ No Claude API key found")
    exit(1)

print(f"Testing with key: {claude_key[:15]}...{claude_key[-4:]}")

import anthropic

client = anthropic.Anthropic(api_key=claude_key)

# Try different models
models_to_test = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-20240620", 
    "claude-3-sonnet-20240229",
    "claude-3-opus-20240229",
    "claude-3-haiku-20240307",
]

print("\nTesting available models:\n")

for model in models_to_test:
    try:
        print(f"Trying {model}...", end=" ")
        message = client.messages.create(
            model=model,
            max_tokens=20,
            messages=[{"role": "user", "content": "Say: OK"}]
        )
        response = message.content[0].text
        print(f"✅ WORKS! Response: {response}")
        print(f"   Tokens: {message.usage.input_tokens + message.usage.output_tokens}")
        break
    except Exception as e:
        error_msg = str(e)
        if "not_found_error" in error_msg:
            print("❌ Model not available")
        elif "authentication" in error_msg.lower() or "unauthorized" in error_msg.lower():
            print(f"❌ Auth error: {error_msg[:100]}")
            print("\n⚠️  API key may be invalid or expired")
            break
        else:
            print(f"❌ Error: {error_msg[:100]}")
