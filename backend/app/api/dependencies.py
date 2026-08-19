from typing import Any

import instructor
from google.genai import types

from app.core.config import settings

_gemini_client: Any | None = None

def get_gemini_client() -> Any | None:
    """Dependency that returns the initialized Gemini client."""
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return None
        
    try:
        # Initialize instructor with Gemini provider using google-genai
        _gemini_client = instructor.from_provider(
            model="google/gemini-2.5-flash",
            api_key=api_key,
            http_options=types.HttpOptions(timeout=settings.GEMINI_TIMEOUT_MS),
        )
        return _gemini_client
    except Exception as e:  # noqa: BLE001
        # Logger could be used here
        print(f"[WARNING] Failed to initialize Gemini client in dependency: {e}")
        return None
