"""
Authentication endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, status
from datetime import timedelta
import logging

from core import LoginRequest, TokenResponse, UserInfo
from auth import authenticate_user, create_access_token, get_current_user
from config.config import JWT_ACCESS_TOKEN_EXPIRE_MINUTES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse,
             summary="Вход в систему",
             response_description="JWT токен для доступа к защищенным эндпоинтам")
async def login(credentials: LoginRequest):
    """
    Аутентификация пользователя и получение JWT токена.
    
    Для разработки:
    - Username: admin
    - Password: admin
    
    Токен нужно передавать в заголовке: Authorization: Bearer <token>
    """
    user = authenticate_user(credentials.username, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        role=user["role"]
    )


@router.get("/me", response_model=UserInfo,
            summary="Получить информацию о текущем пользователе")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Получить информацию о текущем аутентифицированном пользователе.
    Требует JWT токен в заголовке Authorization.
    """
    return UserInfo(
        username=current_user["username"],
        role=current_user["role"]
    )
