from typing import Any
import instructor
from openai import OpenAI
from app.core.config import settings

_llm_client: Any | None = None
_gemini_client: Any | None = None

def get_llm_client() -> Any | None:
    """Dependency that returns the initialized OpenAI client pointing to NVIDIA NIM."""
    global _llm_client, _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    if _llm_client is not None:
        return _llm_client
    
    api_key = settings.NVIDIA_API_KEY or settings.GEMINI_API_KEY
    if not api_key:
        return None
        
    try:
        raw_client = OpenAI(
            base_url=settings.NVIDIA_BASE_URL,
            api_key=api_key,
            timeout=settings.NVIDIA_TIMEOUT_SEC,
        )
        _llm_client = instructor.from_openai(raw_client, mode=instructor.Mode.TOOLS)
        _gemini_client = _llm_client
        return _llm_client
    except Exception as e:  # noqa: BLE001
        print(f"[WARNING] Failed to initialize NVIDIA NIM / OpenAI client in dependency: {e}")
        return None

# Backward compatibility alias
get_gemini_client = get_llm_client

