"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
#OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# OpenRouter API endpoint
#OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Azure AI Foundry API Endpoint
AZURE_AISERVICE_ENDPOINT = os.getenv("AZURE_AISERVICE_ENDPOINT")

# Council members - list of Azure AI Foundry model deployment identifiers
COUNCIL_MODELS = [
    "gpt-4.1-mini-global",
    "gpt-5-mini-global"
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "gpt-5-mini-global"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
