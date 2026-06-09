from __future__ import annotations

import hashlib
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


def _token_fingerprint(token: str) -> str:
    """Return a short hex fingerprint of a token without exposing the full value."""
    return hashlib.sha256(token.encode()).hexdigest()[:12]


def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """Validate bearer token and return its fingerprint."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        logger.warning("Missing or non-bearer authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided = credentials.credentials
    expected = settings.sidecar_api_token

    # Constant-time comparison to prevent timing attacks
    import hmac

    if not hmac.compare_digest(provided.encode(), expected.encode()):
        logger.warning("Invalid bearer token (fingerprint=%s)", _token_fingerprint(provided))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    fp = _token_fingerprint(provided)
    logger.debug("Authenticated request with token fingerprint=%s", fp)
    return fp
