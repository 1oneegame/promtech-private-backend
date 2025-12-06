"""
Authentication module
JWT authentication and authorization
"""

from .jwt import (
    authenticate_user,
    create_access_token,
    get_current_user,
    require_admin,
    get_password_hash,
    verify_password,
    TokenData,
    set_admin_repository
)

__all__ = [
    'authenticate_user',
    'create_access_token',
    'get_current_user',
    'require_admin',
    'get_password_hash',
    'verify_password',
    'TokenData',
    'set_admin_repository'
]
