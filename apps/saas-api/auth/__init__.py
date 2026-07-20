"""
Authentication module for Saas-api.

Uses Neon Auth for authentication.
"""

from .neon_auth import (
    neon_auth_router,
    get_current_user,
    get_current_org,
    create_neon_auth_user,
    verify_password,
    generate_token,
    decode_token,
)

__all__ = [
    "neon_auth_router",
    "get_current_user",
    "get_current_org",
    "create_neon_auth_user",
    "verify_password",
    "generate_token",
    "decode_token",
]
