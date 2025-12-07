"""
Planning/Tasks API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
import logging

from core.models import Task, TaskCreate, TaskUpdate, TaskStatus
from core.user_repositories import TasksRepository
from auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def get_tasks_repository():
    """Dependency для получения репозитория задач"""
    from app import db_connection
    return TasksRepository(db_connection)


@router.get("", response_model=List[Task],
            summary="Получить список задач")
async def get_tasks(
    assigned_to: Optional[str] = None,
    status: Optional[TaskStatus] = None,
    current_user: dict = Depends(get_current_user),
    tasks_repo: TasksRepository = Depends(get_tasks_repository)
):
    """Получить список задач с фильтрацией"""
    username = assigned_to or current_user["username"]
    return tasks_repo.get_all_tasks(username=username, status=status)


@router.get("/{task_id}", response_model=Task,
            summary="Получить задачу по ID")
async def get_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    tasks_repo: TasksRepository = Depends(get_tasks_repository)
):
    """Получить задачу по ID"""
    task = tasks_repo.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    return task


@router.post("", response_model=Task,
            status_code=status.HTTP_201_CREATED,
            summary="Создать новую задачу")
async def create_task(
    task_data: TaskCreate,
    current_user: dict = Depends(get_current_user),
    tasks_repo: TasksRepository = Depends(get_tasks_repository)
):
    """Создать новую задачу"""
    task = tasks_repo.create_task(current_user["username"], task_data)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create task"
        )
    return task


@router.put("/{task_id}", response_model=Task,
            summary="Обновить задачу")
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    current_user: dict = Depends(get_current_user),
    tasks_repo: TasksRepository = Depends(get_tasks_repository)
):
    """Обновить задачу"""
    # Проверяем, существует ли задача
    task = tasks_repo.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    success = tasks_repo.update_task(task_id, task_data)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update task"
        )
    
    return tasks_repo.get_task(task_id)


@router.delete("/{task_id}",
               summary="Удалить задачу")
async def delete_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    tasks_repo: TasksRepository = Depends(get_tasks_repository)
):
    """Удалить задачу"""
    success = tasks_repo.delete_task(task_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    return {"status": "success", "message": "Task deleted"}

