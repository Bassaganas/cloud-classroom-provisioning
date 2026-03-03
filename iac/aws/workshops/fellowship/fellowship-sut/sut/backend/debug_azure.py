#!/usr/bin/env python3
"""Debug script to test Azure OpenAI connection and NPC response generation."""
import sys
sys.path.insert(0, '/app')

from flask import Flask
from config import Config

# Quick config check
config = Config()
print("\n" + "="*70)
print("AZURE OPENAI CONFIG CHECK")
print("="*70)
print(f"Endpoint: {config.AZURE_OPENAI_ENDPOINT}")
print(f"API Key Present: {bool(config.AZURE_OPENAI_API_KEY)}")
print(f"API Key Length: {len(config.AZURE_OPENAI_API_KEY) if config.AZURE_OPENAI_API_KEY else 0}")
print(f"Deployment: {config.AZURE_OPENAI_DEPLOYMENT}")
print(f"API Version: {config.AZURE_OPENAI_API_VERSION}")

# Try to create client
try:
    from openai import AzureOpenAI
    print("\n" + "="*70)
    print("CREATING AZURE OPENAI CLIENT")
    print("="*70)
    client = AzureOpenAI(
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        api_key=config.AZURE_OPENAI_API_KEY,
        api_version=config.AZURE_OPENAI_API_VERSION,
    )
    print("✅ Client created successfully")
    
    # Try a simple API call
    print("\n" + "="*70)
    print("TESTING SIMPLE CHAT COMPLETION")
    print("="*70)
    response = client.chat.completions.create(
        model=config.AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": "You are Frodo Baggins. Respond briefly in one sentence."},
            {"role": "user", "content": "Do you like sports?"}
        ],
        temperature=0.7,
        max_tokens=100,
    )
    print(f"✅ API Call Successful!")
    print(f"\nFrodo's Response: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"\n✗ ERROR: {type(e).__name__}")
    print(f"Details: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
