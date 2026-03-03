#!/usr/bin/env python3
"""Verify Azure OpenAI configuration is loaded correctly."""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from config import Config

def main():
    config = Config()
    
    print("\n" + "=" * 70)
    print("Azure OpenAI Configuration Status")
    print("=" * 70)
    
    has_endpoint = bool(config.AZURE_OPENAI_ENDPOINT)
    has_api_key = bool(config.AZURE_OPENAI_API_KEY)
    
    status = "✅ ACTIVE" if (has_endpoint and has_api_key) else "❌ NOT CONFIGURED"
    print(f"\nStatus: {status}\n")
    
    print(f"Endpoint:       {config.AZURE_OPENAI_ENDPOINT if has_endpoint else '(not set)'}")
    print(f"API Key:        {'(loaded from .env)' if has_api_key else '(not set)'}")
    print(f"Deployment:     {config.AZURE_OPENAI_DEPLOYMENT}")
    print(f"API Version:    {config.AZURE_OPENAI_API_VERSION}")
    print(f"Max Tokens:     {config.AZURE_OPENAI_MAX_TOKENS}")
    print(f"Temperature:    {config.AZURE_OPENAI_TEMPERATURE}")
    
    print("\n" + "=" * 70)
    
    if has_endpoint and has_api_key:
        print("🤖 AI-powered NPC responses are ACTIVE")
        print("🎯 Context-aware quest generation is ENABLED")
        print("\nNPC conversations will now:")
        print("  • Use character personalities for authentic responses")
        print("  • Reference user's specific situation in replies")
        print("  • Generate quests matched to conversation context")
        print("  • Fall back to templates only if API fails")
        return 0
    else:
        print("⚠️  Azure OpenAI not configured")
        print("\nTo enable AI:")
        print("  1. Create/update .env file with Azure credentials")
        print("  2. Restart the backend service")
        return 1

if __name__ == '__main__':
    sys.exit(main())
