"""
JWT Authentication Module
Handles user authentication, token generation, and authorization
Uses MongoDB for admin users storage
"""

import os
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# Import configuration
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config.config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES

# HTTP Bearer token security scheme
security = HTTPBearer()

# Global admin repository - будет инициализирован в app.py
admin_repository = None


def set_admin_repository(repo):
    """Установить глобальный репозиторий админов"""
    global admin_repository
    admin_repository = repo


class TokenData(BaseModel):
    """Token payload data"""
    username: Optional[str] = None
    role: Optional[str] = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Authenticate a user by username and password from MongoDB
    
    Args:
        username: Username
        password: Plain text password
        
    Returns:
        User dict if authenticated, None otherwise
    """
    if admin_repository is None:
        return None
    
    # Get user from database
    user = admin_repository.get_user_by_username(username)
    if user is None:
        return None
    
    # Check if user is active
    if not user.is_active:
        return None
    
    # Verify password
    if not verify_password(password, user.password_hash):
        return None
    
    return {
        "username": user.username,
        "role": user.role
    }


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        data: Data to encode in the token
        expires_delta: Optional expiration time delta
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Decode and verify a JWT access token
    
    Args:
        token: JWT token string
        
    Returns:
        TokenData if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        
        if username is None:
            return None
        
        return TokenData(username=username, role=role)
    except JWTError:
        return None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency to get the current authenticated user from JWT token
    
    Args:
        credentials: HTTP Authorization credentials with Bearer token
        
    Returns:
        User dict with username and role
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    token_data = decode_access_token(token)
    
    if token_data is None or token_data.username is None:
        raise credentials_exception
    
    # Return user dict
    return {
        "username": token_data.username,
        "role": token_data.role
    }


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Dependency to ensure the current user has admin role
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        User dict if admin
        
    Raises:
        HTTPException: If user is not an admin
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    return current_user


# Utility function to generate password hash for configuration
def generate_password_hash(password: str) -> str:
    """
    Generate a bcrypt hash for a password (for .env configuration)
    
    Usage:
        python -c "from src.auth import generate_password_hash; print(generate_password_hash('mypassword'))"
    """
    return get_password_hash(password)
