"""
User-related repositories for IntegrityOS
Репозитории для работы с пользователями, профилями, настройками, задачами, логами и избранным
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from pymongo.errors import DuplicateKeyError

from core.models import (
    UserProfile, UserProfileUpdate, UserSettings, UserSettingsUpdate,
    Task, TaskCreate, TaskUpdate, TaskStatus,
    AuditLog, AuditLogAction, Favorite
)

logger = logging.getLogger(__name__)


class UserProfileRepository:
    """Репозиторий для работы с профилями пользователей"""
    
    def __init__(self, db_connection):
        self.db_connection = db_connection
    
    def get_profile(self, username: str) -> Optional[UserProfile]:
        """Получить профиль пользователя"""
        if self.db_connection.local_mode:
            # В локальном режиме возвращаем дефолтный профиль
            return UserProfile(
                username=username,
                full_name=f"{username} User",
                email=f"{username}@integrityos.kz",
                phone="+7 (700) 000-00-00",
                organization="ТОО \"Интегрити ОС\"",
                position="Инженер",
                department="Отдел технического контроля"
            )
        
        try:
            doc = self.db_connection.db['user_profiles'].find_one({"username": username})
            if doc:
                doc['username'] = doc.get('username', username)
                return UserProfile(**doc)
            return None
        except Exception as e:
            logger.error(f"Error getting profile: {str(e)}")
            return None
    
    def create_or_update_profile(self, username: str, profile_data: UserProfileUpdate) -> bool:
        """Создать или обновить профиль"""
        if self.db_connection.local_mode:
            return True
        
        try:
            profile = self.get_profile(username)
            if profile:
                # Обновление
                update_data = profile_data.dict(exclude_unset=True)
                update_data['updated_at'] = datetime.utcnow()
                self.db_connection.db['user_profiles'].update_one(
                    {"username": username},
                    {"$set": update_data}
                )
            else:
                # Создание
                new_profile = UserProfile(
                    username=username,
                    full_name=profile_data.full_name or f"{username} User",
                    email=profile_data.email or f"{username}@integrityos.kz",
                    phone=profile_data.phone,
                    organization=profile_data.organization,
                    position=profile_data.position,
                    department=profile_data.department
                )
                self.db_connection.db['user_profiles'].insert_one(new_profile.dict())
            return True
        except Exception as e:
            logger.error(f"Error creating/updating profile: {str(e)}")
            return False


class UserSettingsRepository:
    """Репозиторий для работы с настройками пользователей"""
    
    def __init__(self, db_connection):
        self.db_connection = db_connection
    
    def get_settings(self, username: str) -> UserSettings:
        """Получить настройки пользователя"""
        if self.db_connection.local_mode:
            return UserSettings(username=username)
        
        try:
            doc = self.db_connection.db['user_settings'].find_one({"username": username})
            if doc:
                return UserSettings(**doc)
            # Создаем дефолтные настройки
            default_settings = UserSettings(username=username)
            self.db_connection.db['user_settings'].insert_one(default_settings.dict())
            return default_settings
        except Exception as e:
            logger.error(f"Error getting settings: {str(e)}")
            return UserSettings(username=username)
    
    def update_settings(self, username: str, settings_data: UserSettingsUpdate) -> bool:
        """Обновить настройки"""
        if self.db_connection.local_mode:
            return True
        
        try:
            update_data = settings_data.dict(exclude_unset=True)
            update_data['updated_at'] = datetime.utcnow()
            self.db_connection.db['user_settings'].update_one(
                {"username": username},
                {"$set": update_data},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error updating settings: {str(e)}")
            return False


class TasksRepository:
    """Репозиторий для работы с задачами планирования"""
    
    def __init__(self, db_connection):
        self.db_connection = db_connection
        self.local_tasks = []  # Для локального режима
    
    def get_all_tasks(self, username: Optional[str] = None, status: Optional[TaskStatus] = None) -> List[Task]:
        """Получить все задачи"""
        if self.db_connection.local_mode:
            tasks = self.local_tasks
            if username:
                tasks = [t for t in tasks if t.assigned_to == username]
            if status:
                tasks = [t for t in tasks if t.status == status]
            return tasks
        
        try:
            query = {}
            if username:
                query['assigned_to'] = username
            if status:
                query['status'] = status.value
            
            docs = list(self.db_connection.db['tasks'].find(query).sort("date", 1))
            tasks = []
            for doc in docs:
                doc['task_id'] = str(doc['_id'])
                del doc['_id']
                tasks.append(Task(**doc))
            return tasks
        except Exception as e:
            logger.error(f"Error getting tasks: {str(e)}")
            return []
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Получить задачу по ID"""
        if self.db_connection.local_mode:
            for task in self.local_tasks:
                if task.task_id == task_id:
                    return task
            return None
        
        try:
            from bson import ObjectId
            doc = self.db_connection.db['tasks'].find_one({"_id": ObjectId(task_id)})
            if doc:
                doc['task_id'] = str(doc['_id'])
                del doc['_id']
                return Task(**doc)
            return None
        except Exception as e:
            logger.error(f"Error getting task: {str(e)}")
            return None
    
    def create_task(self, username: str, task_data: TaskCreate) -> Optional[Task]:
        """Создать задачу"""
        task = Task(
            title=task_data.title,
            object_name=task_data.object_name,
            object_id=task_data.object_id,
            date=task_data.date,
            time=task_data.time,
            assigned_to=task_data.assigned_to,
            method=task_data.method,
            description=task_data.description,
            created_by=username
        )
        
        if self.db_connection.local_mode:
            task.task_id = f"task_{len(self.local_tasks) + 1}"
            self.local_tasks.append(task)
            return task
        
        try:
            task_dict = task.dict()
            if 'task_id' in task_dict:
                del task_dict['task_id']
            result = self.db_connection.db['tasks'].insert_one(task_dict)
            task.task_id = str(result.inserted_id)
            return task
        except Exception as e:
            logger.error(f"Error creating task: {str(e)}")
            return None
    
    def update_task(self, task_id: str, task_data: TaskUpdate) -> bool:
        """Обновить задачу"""
        if self.db_connection.local_mode:
            for task in self.local_tasks:
                if task.task_id == task_id:
                    update_data = task_data.dict(exclude_unset=True)
                    for key, value in update_data.items():
                        setattr(task, key, value)
                    task.updated_at = datetime.utcnow()
                    return True
            return False
        
        try:
            from bson import ObjectId
            update_data = task_data.dict(exclude_unset=True)
            update_data['updated_at'] = datetime.utcnow()
            result = self.db_connection.db['tasks'].update_one(
                {"_id": ObjectId(task_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating task: {str(e)}")
            return False
    
    def delete_task(self, task_id: str) -> bool:
        """Удалить задачу"""
        if self.db_connection.local_mode:
            original_len = len(self.local_tasks)
            self.local_tasks = [t for t in self.local_tasks if t.task_id != task_id]
            return len(self.local_tasks) < original_len
        
        try:
            from bson import ObjectId
            result = self.db_connection.db['tasks'].delete_one({"_id": ObjectId(task_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting task: {str(e)}")
            return False


class AuditLogRepository:
    """Репозиторий для работы с журналом аудита"""
    
    def __init__(self, db_connection):
        self.db_connection = db_connection
        self.local_logs = []  # Для локального режима
    
    def create_log(self, log: AuditLog) -> bool:
        """Создать запись в журнале"""
        if self.db_connection.local_mode:
            self.local_logs.append(log)
            return True
        
        try:
            self.db_connection.db['audit_logs'].insert_one(log.dict())
            return True
        except Exception as e:
            logger.error(f"Error creating audit log: {str(e)}")
            return False
    
    def get_logs(self, 
                 username: Optional[str] = None,
                 action: Optional[AuditLogAction] = None,
                 entity: Optional[str] = None,
                 limit: int = 100) -> List[AuditLog]:
        """Получить записи журнала"""
        if self.db_connection.local_mode:
            logs = self.local_logs
            if username:
                logs = [l for l in logs if l.user == username]
            if action:
                logs = [l for l in logs if l.action == action]
            if entity:
                logs = [l for l in logs if l.entity == entity]
            return sorted(logs, key=lambda x: x.created_at, reverse=True)[:limit]
        
        try:
            query = {}
            if username:
                query['user'] = username
            if action:
                query['action'] = action.value
            if entity:
                query['entity'] = entity
            
            docs = list(self.db_connection.db['audit_logs']
                       .find(query)
                       .sort("created_at", -1)
                       .limit(limit))
            logs = []
            for doc in docs:
                if '_id' in doc:
                    doc['log_id'] = str(doc['_id'])
                    del doc['_id']
                logs.append(AuditLog(**doc))
            return logs
        except Exception as e:
            logger.error(f"Error getting audit logs: {str(e)}")
            return []


class FavoritesRepository:
    """Репозиторий для работы с избранными объектами"""
    
    def __init__(self, db_connection):
        self.db_connection = db_connection
        self.local_favorites = []  # Для локального режима
    
    def get_favorites(self, username: str) -> List[Favorite]:
        """Получить избранные объекты пользователя"""
        if self.db_connection.local_mode:
            return [f for f in self.local_favorites if f.username == username]
        
        try:
            docs = list(self.db_connection.db['favorites'].find({"username": username}))
            favorites = []
            for doc in docs:
                if '_id' in doc:
                    doc['favorite_id'] = str(doc['_id'])
                    del doc['_id']
                favorites.append(Favorite(**doc))
            return favorites
        except Exception as e:
            logger.error(f"Error getting favorites: {str(e)}")
            return []
    
    def add_favorite(self, favorite: Favorite) -> bool:
        """Добавить в избранное"""
        if self.db_connection.local_mode:
            # Проверяем, нет ли уже такого объекта
            if not any(f.username == favorite.username and f.object_id == favorite.object_id 
                      for f in self.local_favorites):
                self.local_favorites.append(favorite)
                return True
            return False
        
        try:
            favorite_dict = favorite.dict()
            if 'favorite_id' in favorite_dict:
                del favorite_dict['favorite_id']
            self.db_connection.db['favorites'].insert_one(favorite_dict)
            return True
        except DuplicateKeyError:
            return False
        except Exception as e:
            logger.error(f"Error adding favorite: {str(e)}")
            return False
    
    def remove_favorite(self, username: str, object_id: int) -> bool:
        """Удалить из избранного"""
        if self.db_connection.local_mode:
            original_len = len(self.local_favorites)
            self.local_favorites = [
                f for f in self.local_favorites 
                if not (f.username == username and f.object_id == object_id)
            ]
            return len(self.local_favorites) < original_len
        
        try:
            result = self.db_connection.db['favorites'].delete_one({
                "username": username,
                "object_id": object_id
            })
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error removing favorite: {str(e)}")
            return False

