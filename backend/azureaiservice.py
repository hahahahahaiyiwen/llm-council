"""Azure OpenAI API client for making LLM requests."""

from typing import List, Dict, Any, Optional
from .config import AZURE_AISERVICE_ENDPOINT
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

api_version = "2024-12-01-preview"

token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=AZURE_AISERVICE_ENDPOINT,
    azure_ad_token_provider=token_provider)

async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via Azure AI Service.

    Args:
        model: Azure AI Service model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    
    try:
        response = client.chat.completions.create(
            messages=messages,
            max_completion_tokens=16384,
            model=model
        )

        return {
            'content': response.choices[0].message.content,
            #'reasoning_details': response.choices[0].message.reasoning_content
        }

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}
