"""
Favorites API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
import logging

from core.models import Favorite
from core.user_repositories import FavoritesRepository
from auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/favorites", tags=["Favorites"])


def get_favorites_repository():
    """Dependency для получения репозитория избранного"""
    from app import db_connection
    return FavoritesRepository(db_connection)


@router.get("", response_model=List[Favorite],
            summary="Получить избранные объекты")
async def get_favorites(
    current_user: dict = Depends(get_current_user),
    favorites_repo: FavoritesRepository = Depends(get_favorites_repository)
):
    """Получить избранные объекты текущего пользователя"""
    return favorites_repo.get_favorites(current_user["username"])


@router.post("", response_model=Favorite,
             status_code=status.HTTP_201_CREATED,
             summary="Добавить объект в избранное")
async def add_favorite(
    favorite: Favorite,
    current_user: dict = Depends(get_current_user),
    favorites_repo: FavoritesRepository = Depends(get_favorites_repository)
):
    """Добавить объект в избранное"""
    # Устанавливаем username из текущего пользователя
    favorite.username = current_user["username"]
    
    success = favorites_repo.add_favorite(favorite)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Object already in favorites"
        )
    
    return favorite


@router.delete("/{object_id}",
               summary="Удалить объект из избранного")
async def remove_favorite(
    object_id: int,
    current_user: dict = Depends(get_current_user),
    favorites_repo: FavoritesRepository = Depends(get_favorites_repository)
):
    """Удалить объект из избранного"""
    success = favorites_repo.remove_favorite(
        current_user["username"],
        object_id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found"
        )
    return {"status": "success", "message": "Favorite removed"}

