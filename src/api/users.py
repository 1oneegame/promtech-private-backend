"""
User Profile and Settings API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
import logging

from core.models import UserProfile, UserProfileUpdate, UserSettings, UserSettingsUpdate, AdminUser
from core.user_repositories import UserProfileRepository, UserSettingsRepository
from auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


def get_profile_repository():
    """Dependency для получения репозитория профилей"""
    from app import db_connection
    return UserProfileRepository(db_connection)


def get_settings_repository():
    """Dependency для получения репозитория настроек"""
    from app import db_connection
    return UserSettingsRepository(db_connection)


@router.get("/profile", response_model=UserProfile,
            summary="Получить профиль текущего пользователя")
async def get_profile(
    current_user: dict = Depends(get_current_user),
    profile_repo: UserProfileRepository = Depends(get_profile_repository)
):
    """Получить профиль текущего аутентифицированного пользователя"""
    profile = profile_repo.get_profile(current_user["username"])
    
    if not profile:
        # Создаем дефолтный профиль
        profile = UserProfile(
            username=current_user["username"],
            full_name=current_user["username"],
            email=f"{current_user['username']}@integrityos.kz"
        )
        profile_repo.create_or_update_profile(
            current_user["username"],
            UserProfileUpdate(
                full_name=profile.full_name,
                email=profile.email
            )
        )
    
    return profile


@router.put("/profile", response_model=UserProfile,
            summary="Обновить профиль текущего пользователя")
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    profile_repo: UserProfileRepository = Depends(get_profile_repository)
):
    """Обновить профиль текущего пользователя"""
    success = profile_repo.create_or_update_profile(
        current_user["username"],
        profile_data
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )
    
    return profile_repo.get_profile(current_user["username"])


@router.get("/settings", response_model=UserSettings,
            summary="Получить настройки текущего пользователя")
async def get_settings(
    current_user: dict = Depends(get_current_user),
    settings_repo: UserSettingsRepository = Depends(get_settings_repository)
):
    """Получить настройки текущего пользователя"""
    return settings_repo.get_settings(current_user["username"])


@router.put("/settings", response_model=UserSettings,
            summary="Обновить настройки текущего пользователя")
async def update_settings(
    settings_data: UserSettingsUpdate,
    current_user: dict = Depends(get_current_user),
    settings_repo: UserSettingsRepository = Depends(get_settings_repository)
):
    """Обновить настройки текущего пользователя"""
    success = settings_repo.update_settings(
        current_user["username"],
        settings_data
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update settings"
        )
    
    return settings_repo.get_settings(current_user["username"])


@router.get("/list", response_model=List[dict],
            summary="Получить список всех пользователей (только для админов)")
async def list_users(
    current_user: dict = Depends(get_current_user),
    profile_repo: UserProfileRepository = Depends(get_profile_repository)
):
    """Получить список всех пользователей (только для админов)"""
    from auth import require_admin
    from app import admin_repository
    
    # Проверяем права администратора
    require_admin(current_user)
    
    # Получаем всех админов
    admins = admin_repository.get_all_admins()
    
    # Получаем профили для каждого админа
    users = []
    for admin in admins:
        profile = profile_repo.get_profile(admin.username)
        users.append({
            "username": admin.username,
            "role": admin.role,
            "email": profile.email if profile else f"{admin.username}@integrityos.kz",
            "full_name": profile.full_name if profile else admin.username,
            "is_active": admin.is_active
        })
    
    return users

