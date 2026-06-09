from __future__ import annotations

import logging
from typing import Any

from kubernetes import client, config  # type: ignore[import-untyped]
from kubernetes.client import ApiClient  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


def load_kube_client(kubeconfig: str, context: str | None = None) -> ApiClient:
    """Load Kubernetes API client from the given kubeconfig file."""
    try:
        cfg = client.Configuration()
        config.load_kube_config(
            config_file=kubeconfig if kubeconfig else None,
            context=context if context else None,
            client_configuration=cfg,
        )
        return ApiClient(configuration=cfg)
    except Exception as exc:
        logger.error("Failed to load kubeconfig from %s: %s", kubeconfig, exc)
        raise


def get_current_context(kubeconfig: str, context: str | None = None) -> str:
    """Return the active context name."""
    try:
        contexts, active = config.list_kube_config_contexts(config_file=kubeconfig or None)
        if context:
            return context
        return active.get("name", "") if active else ""
    except Exception as exc:
        logger.warning("Could not determine cluster context: %s", exc)
        return ""


def safe_get(obj: Any, *attrs: str, default: Any = None) -> Any:
    """Safely traverse nested attributes, returning default on any failure."""
    current = obj
    for attr in attrs:
        if current is None:
            return default
        try:
            current = getattr(current, attr)
        except AttributeError:
            return default
    return current if current is not None else default
