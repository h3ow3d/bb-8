from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_GENERATE_TIMEOUT = 120.0
_CONNECT_TIMEOUT = 5.0


class OllamaError(Exception):
    pass


class OllamaUnavailableError(OllamaError):
    pass


class OllamaModelMissingError(OllamaError):
    pass


def chat(
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    timeout: float = _GENERATE_TIMEOUT,
) -> str:
    """Send a chat request to Ollama and return the response text."""
    url = base_url.rstrip("/") + "/api/chat"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=_CONNECT_TIMEOUT)) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 404:
                raise OllamaModelMissingError(
                    f"Model '{model}' not found in Ollama. "
                    f"Run scripts/pull-model.sh to download it."
                )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")
    except httpx.ConnectError as exc:
        raise OllamaUnavailableError(
            f"Cannot connect to Ollama at {base_url}. "
            "Ensure the ollama service is running. "
            "Run scripts/pull-model.sh to start it and pull a model."
        ) from exc
    except httpx.TimeoutException as exc:
        raise OllamaUnavailableError(
            f"Timeout connecting to Ollama at {base_url}."
        ) from exc


def check_model_available(base_url: str, model: str) -> bool:
    """Check if a model is available in Ollama. Returns False on any error."""
    url = base_url.rstrip("/") + "/api/tags"
    try:
        with httpx.Client(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
            resp = client.get(url)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            return any(m == model or m.startswith(model.split(":")[0]) for m in model_names)
    except Exception as exc:
        logger.warning("Could not check Ollama models: %s", exc)
        return False
