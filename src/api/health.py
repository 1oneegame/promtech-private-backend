"""
Health and info endpoints
"""

from fastapi import APIRouter, HTTPException
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", tags=["Health"])
async def root():
    """Корневой эндпоинт - проверка статуса API"""
    return {
        "service": "IntegrityOS API",
        "version": "1.0.0",
        "status": "active",
        "docs": "/docs"
    }


@router.get("/health", tags=["Health"])
async def health_check(db_connection=None, defects_repository=None):
    """Проверка здоровья API"""
    try:
        defects = defects_repository.get_all_defects()
        return {
            "status": "healthy",
            "database": "connected" if db_connection else "disconnected",
            "defects_count": len(defects)
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Health check failed")


@router.get("/info", tags=["Info"])
async def get_info(db_connection=None, defects_repository=None, ml_available=False):
    """Получить информацию о системе и доступных сервисах"""
    try:
        defects = defects_repository.get_all_defects()
        stats = defects_repository.get_statistics()
        
        return {
            "application": "IntegrityOS",
            "version": "1.0.0",
            "database_mode": "local" if db_connection.local_mode else "mongodb",
            "total_defects": len(defects),
            "ml_available": ml_available,
            "statistics": stats,
            "available_endpoints": {
                "defects": "/defects",
                "statistics": "/statistics",
                "export": "/export/json",
                "ml_predict": "/ml/predict",
                "ml_metrics": "/ml/model/metrics",
                "ml_info": "/ml/model/info",
                "docs": "/docs"
            }
        }
    except Exception as e:
        logger.error(f"Error getting info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
