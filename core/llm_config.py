import os
import time
import logging
import anthropic
from typing import List, Callable, Any, Tuple
from dotenv import load_dotenv

load_dotenv(override=True)
logger = logging.getLogger("LLMConfig")

# Primary model and fallback chain (Anthropic native model IDs)
PRIMARY_MODEL = "claude-sonnet-4-5"
MODEL_CHAIN = [
    "claude-sonnet-4-5",
    "claude-3-5-sonnet-20241022",
    "claude-3-haiku-20240307",
]


def get_anthropic_client() -> anthropic.Anthropic:
    """Returns an Anthropic SDK client using ANTHROPIC_API_KEY from env."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set in environment variables.")
    return anthropic.Anthropic(api_key=api_key)


def call_anthropic(prompt: str, model: str = PRIMARY_MODEL, max_tokens: int = 1024, system: str = None) -> str:
    """
    Makes a direct call to the Anthropic Messages API and returns the response text.

    Args:
        prompt: The user message content.
        model: Anthropic model ID (default: claude-sonnet-4-5).
        max_tokens: Maximum tokens to generate.
        system: Optional system prompt.

    Returns:
        The assistant's response as a plain string.
    """
    client = get_anthropic_client()
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    return response.content[0].text

def validate_model_chain() -> bool:
    """Startup check: verifies the Anthropic API key is configured."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set. LLM scoring will be disabled.")
        return False
    logger.info(f"✅ Anthropic API key found. Primary model: {PRIMARY_MODEL}")
    return True


def get_llm_for_model(model_name: str):
    """Returns a CrewAI LLM object for the given Anthropic model name.
    Uses ANTHROPIC_API_KEY via LiteLLM routing (anthropic/ prefix).
    Kept for backward compatibility with CrewAI agents.
    """
    try:
        from crewai import LLM
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set.")
        # Strip any existing provider prefix, then add 'anthropic/' for LiteLLM
        clean = model_name.replace("openrouter/", "").replace("anthropic/", "")
        litellm_model = f"anthropic/{clean}"
        return LLM(model=litellm_model, api_key=api_key, max_tokens=1024)
    except ImportError:
        # CrewAI not available — fall back to raw client
        return get_anthropic_client()


def get_llm():
    """Returns a CrewAI-compatible LLM for the primary model.
    Kept for backward compatibility with agents that pass llm= to CrewAI Agent()."""
    return get_llm_for_model(PRIMARY_MODEL)


def call_with_fallback(prompt_or_factory, model_chain: List[str] = MODEL_CHAIN) -> Tuple[Any, str]:
    """
    Calls the Anthropic API with sequential model fallback.

    If prompt_or_factory is a string, it is sent as a direct user message.
    Returns a tuple of (response_text, model_used_label).
    """
    if not callable(prompt_or_factory):
        prompt = prompt_or_factory
        for idx, model_id in enumerate(model_chain):
            max_retries = 2
            backoff_delay = 2.0
            for attempt in range(max_retries + 1):
                try:
                    logger.info(f"Attempting Anthropic call with model: {model_id} (Attempt {attempt + 1}/{max_retries + 1})")
                    result = call_anthropic(prompt, model=model_id)
                    label = f"used LLM successfully (Primary: {model_id})" if idx == 0 else f"used backup model in chain ({model_id})"
                    logger.info(f"✅ Executed task with model '{model_id}'")
                    return result, label
                except Exception as e:
                    err_str = str(e).lower()
                    if "overloaded" in err_str or "529" in err_str or "429" in err_str:
                        if attempt < max_retries:
                            logger.warning(f"⚠️ Model '{model_id}' overloaded/rate-limited. Retrying in {backoff_delay}s...")
                            time.sleep(backoff_delay)
                            backoff_delay *= 2.0
                        else:
                            logger.warning(f"⚠️ Model '{model_id}' failed after retries. Trying next model.")
                    else:
                        logger.warning(f"⚠️ Model '{model_id}' failed: {e}. Trying next model...")
                        break

        logger.error(f"❌ All models in MODEL_CHAIN failed: {model_chain}. Falling back to programmatic logic.")
        return None, "used programmatic fallback"

    # Legacy CrewAI crew_factory support
    logger.warning("call_with_fallback received a callable (CrewAI crew_factory). This path is deprecated; migrate to call_anthropic().")
    return None, "used programmatic fallback"

