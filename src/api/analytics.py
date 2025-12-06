"""
Analytics endpoints
"""

from fastapi import APIRouter, HTTPException
import logging

from core import StatisticsResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Analytics"])


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(defects_repository=None):
    """Получить статистику по дефектам"""
    try:
        stats = defects_repository.get_statistics()
        return StatisticsResponse(**stats)
    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
