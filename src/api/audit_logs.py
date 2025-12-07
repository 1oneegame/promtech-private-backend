"""
Audit Logs API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
import logging

from core.models import AuditLog, AuditLogAction
from core.user_repositories import AuditLogRepository
from auth import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


def get_audit_repository():
    """Dependency для получения репозитория логов"""
    from app import db_connection
    return AuditLogRepository(db_connection)


@router.get("", response_model=List[AuditLog],
            summary="Получить журнал аудита")
async def get_audit_logs(
    username: Optional[str] = None,
    action: Optional[AuditLogAction] = None,
    entity: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    audit_repo: AuditLogRepository = Depends(get_audit_repository)
):
    """Получить записи журнала аудита
    
    Только администраторы могут видеть все логи.
    Обычные пользователи видят только свои логи.
    """
    # Если не админ, показываем только логи текущего пользователя
    if current_user.get("role") != "admin":
        username = current_user["username"]
    
    return audit_repo.get_logs(
        username=username,
        action=action,
        entity=entity,
        limit=limit
    )


@router.post("", response_model=dict,
             summary="Создать запись в журнале аудита (внутренний)")
async def create_audit_log(
    log: AuditLog,
    current_user: dict = Depends(require_admin),
    audit_repo: AuditLogRepository = Depends(get_audit_repository)
):
    """Создать запись в журнале аудита (только для внутреннего использования)"""
    success = audit_repo.create_log(log)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create audit log"
        )
    return {"status": "success", "message": "Audit log created"}

