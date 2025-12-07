"""
MongoDB Database Layer for IntegrityOS
Слой для работы с базой данных MongoDB
"""

import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from pydantic import BaseModel
import json
from dotenv import load_dotenv

from core.models import Defect, Pipeline, PipelineObject, DefectResponse, AdminUser

# Загружаем переменные окружения из .env
load_dotenv()

# Настройка логирования
logger = logging.getLogger(__name__)


class MongoDBConnection:
    """Управление подключением к MongoDB"""
    
    def __init__(self, 
                 mongo_uri: Optional[str] = None,
                 database_name: str = "integrityos",
                 local_mode: bool = True):
        """Инициализация подключения
        
        Args:
            mongo_uri: URI подключения MongoDB (если None, использует переменную окружения или локальный)
            database_name: Название базы данных
            local_mode: Использовать локальный режим (хранение в памяти/JSON)
        """
        # Берём URI из аргумента, переменной окружения или используем локальный
        self.mongo_uri = mongo_uri or os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
        self.database_name = database_name
        self.local_mode = local_mode
        self.client = None
        self.db = None
        self.defects_data = []  # Для локального режима
        
        if not local_mode:
            self._connect()
    
    def _connect(self):
        """Подключается к MongoDB"""
        try:
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            # Проверка подключения
            self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            logger.info("Успешное подключение к MongoDB")
            
            # Создаём коллекции и индексы
            self._initialize_collections()
            
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.warning(f"Не удалось подключиться к MongoDB: {str(e)}")
            logger.info("Переход в локальный режим")
            self.local_mode = True
            return False
    
    def _initialize_collections(self):
        """Инициализирует коллекции и индексы"""
        try:
            # Коллекция дефектов
            if 'defects' not in self.db.list_collection_names():
                self.db.create_collection('defects')
                logger.info("Создана коллекция 'defects'")
            
            # Создаём индексы для дефектов
            defects_collection = self.db['defects']
            defects_collection.create_index('defect_id', unique=True, sparse=True)
            defects_collection.create_index('pipeline_id')
            defects_collection.create_index('segment_number')
            defects_collection.create_index('defect_type')
            logger.info("Индексы для коллекции 'defects' созданы")
            
            # Коллекция админ-пользователей
            if 'admin_users' not in self.db.list_collection_names():
                self.db.create_collection('admin_users')
                logger.info("Создана коллекция 'admin_users'")
            
            # Создаём индексы для админов
            admin_collection = self.db['admin_users']
            admin_collection.create_index('username', unique=True)
            logger.info("Индексы для коллекции 'admin_users' созданы")
            
            # Коллекция профилей пользователей
            if 'user_profiles' not in self.db.list_collection_names():
                self.db.create_collection('user_profiles')
                logger.info("Создана коллекция 'user_profiles'")
            
            user_profiles_collection = self.db['user_profiles']
            user_profiles_collection.create_index('username', unique=True)
            
            # Коллекция настроек пользователей
            if 'user_settings' not in self.db.list_collection_names():
                self.db.create_collection('user_settings')
                logger.info("Создана коллекция 'user_settings'")
            
            user_settings_collection = self.db['user_settings']
            user_settings_collection.create_index('username', unique=True)
            
            # Коллекция задач
            if 'tasks' not in self.db.list_collection_names():
                self.db.create_collection('tasks')
                logger.info("Создана коллекция 'tasks'")
            
            tasks_collection = self.db['tasks']
            tasks_collection.create_index('assigned_to')
            tasks_collection.create_index('status')
            tasks_collection.create_index('date')
            
            # Коллекция журнала аудита
            if 'audit_logs' not in self.db.list_collection_names():
                self.db.create_collection('audit_logs')
                logger.info("Создана коллекция 'audit_logs'")
            
            audit_logs_collection = self.db['audit_logs']
            audit_logs_collection.create_index('user')
            audit_logs_collection.create_index('action')
            audit_logs_collection.create_index('created_at')
            
            # Коллекция избранного
            if 'favorites' not in self.db.list_collection_names():
                self.db.create_collection('favorites')
                logger.info("Создана коллекция 'favorites'")
            
            favorites_collection = self.db['favorites']
            favorites_collection.create_index([('username', 1), ('object_id', 1)], unique=True)
            
        except Exception as e:
            logger.warning(f"Ошибка при инициализации коллекций: {str(e)}")
    
    def close(self):
        """Закрывает подключение"""
        if self.client:
            self.client.close()
            logger.info("Подключение к MongoDB закрыто")


class DefectsRepository:
    """Репозиторий для работы с дефектами"""
    
    def __init__(self, db_connection: MongoDBConnection):
        """Инициализация репозитория
        
        Args:
            db_connection: Объект подключения к БД
        """
        self.db_connection = db_connection
        self.collection_name = 'defects'
    
    def _get_collection(self):
        """Получает коллекцию из БД или локального хранилища"""
        if self.db_connection.local_mode:
            return None  # Используем локальный список
        return self.db_connection.db[self.collection_name]
    
    def insert_defects(self, defects: List[Defect]) -> Dict[str, Any]:
        """Вставляет дефекты в БД
        
        Args:
            defects: Список дефектов
            
        Returns:
            Dict с результатами операции
        """
        result = {
            "inserted": 0,
            "failed": 0,
            "errors": []
        }
        
        try:
            if self.db_connection.local_mode:
                # Локальный режим - добавляем в список
                for defect in defects:
                    self.db_connection.defects_data.append(defect)
                result["inserted"] = len(defects)
                logger.info(f"Добавлено {len(defects)} дефектов в локальное хранилище")
            else:
                # MongoDB режим
                collection = self._get_collection()
                defect_dicts = [json.loads(d.model_dump_json()) for d in defects]
                insert_result = collection.insert_many(defect_dicts)
                result["inserted"] = len(insert_result.inserted_ids)
                logger.info(f"Добавлено {result['inserted']} дефектов в MongoDB")
        
        except Exception as e:
            error_msg = f"Ошибка при вставке дефектов: {str(e)}"
            logger.error(error_msg)
            result["failed"] = len(defects)
            result["errors"].append(error_msg)
        
        return result
    
    def get_all_defects(self) -> List[Defect]:
        """Получает все дефекты
        
        Returns:
            List[Defect]: Список дефектов
        """
        try:
            if self.db_connection.local_mode:
                return self.db_connection.defects_data
            else:
                collection = self._get_collection()
                defect_dicts = list(collection.find())
                return [Defect(**d) for d in defect_dicts]
        except Exception as e:
            logger.error(f"Ошибка при получении дефектов: {str(e)}")
            return []
    
    def get_defect_by_id(self, defect_id: str) -> Optional[Defect]:
        """Получает дефект по ID
        
        Args:
            defect_id: ID дефекта
            
        Returns:
            Defect или None если не найден
        """
        try:
            if self.db_connection.local_mode:
                for defect in self.db_connection.defects_data:
                    if defect.defect_id == defect_id:
                        return defect
                return None
            else:
                collection = self._get_collection()
                defect_dict = collection.find_one({"defect_id": defect_id})
                if defect_dict:
                    return Defect(**defect_dict)
                return None
        except Exception as e:
            logger.error(f"Ошибка при получении дефекта по ID: {str(e)}")
            return None
    
    def check_defect_exists(self, defect_id: str) -> bool:
        """Проверяет существование дефекта по ID
        
        Args:
            defect_id: ID дефекта
            
        Returns:
            bool: True если существует
        """
        try:
            if self.db_connection.local_mode:
                return any(d.defect_id == defect_id for d in self.db_connection.defects_data)
            else:
                collection = self._get_collection()
                return collection.count_documents({"defect_id": defect_id}) > 0
        except Exception as e:
            logger.error(f"Ошибка при проверке существования дефекта: {str(e)}")
            return False
    
    def insert_single_defect(self, defect: Defect) -> Dict[str, Any]:
        """Вставляет один дефект в БД
        
        Args:
            defect: Объект дефекта
            
        Returns:
            Dict с результатом операции
        """
        result = {
            "inserted": False,
            "defect_id": defect.defect_id,
            "error": None
        }
        
        try:
            # Проверка уникальности
            if self.check_defect_exists(defect.defect_id):
                result["error"] = f"Defect with ID '{defect.defect_id}' already exists"
                return result
            
            if self.db_connection.local_mode:
                self.db_connection.defects_data.append(defect)
                result["inserted"] = True
                logger.info(f"Добавлен дефект {defect.defect_id} в локальное хранилище")
            else:
                collection = self._get_collection()
                defect_dict = json.loads(defect.model_dump_json())
                collection.insert_one(defect_dict)
                result["inserted"] = True
                logger.info(f"Добавлен дефект {defect.defect_id} в MongoDB")
        
        except Exception as e:
            error_msg = f"Ошибка при вставке дефекта: {str(e)}"
            logger.error(error_msg)
            result["error"] = error_msg
        
        return result
    
    def update_defect_severity(self, defect_id: str, severity: str, probability: float) -> bool:
        """Обновляет severity и probability дефекта
        
        Args:
            defect_id: ID дефекта
            severity: Новый уровень критичности
            probability: Вероятность предсказания
            
        Returns:
            bool: Успешность операции
        """
        try:
            from datetime import datetime
            
            if self.db_connection.local_mode:
                for defect in self.db_connection.defects_data:
                    if defect.defect_id == defect_id:
                        defect.severity = severity
                        defect.probability = probability
                        defect.updated_at = datetime.utcnow()
                        logger.info(f"Обновлен severity дефекта {defect_id}: {severity} ({probability:.2f})")
                        return True
                return False
            else:
                collection = self._get_collection()
                result = collection.update_one(
                    {"defect_id": defect_id},
                    {
                        "$set": {
                            "severity": severity,
                            "probability": probability,
                            "updated_at": datetime.utcnow()
                        },
                        "$unset": {
                            "details.severity": "",
                            "details.probability": "",
                            "ml_prediction_probability": ""
                        }
                    }
                )
                if result.modified_count > 0:
                    logger.info(f"Обновлен severity дефекта {defect_id}: {severity} ({probability:.2f})")
                    return True
                return False
        except Exception as e:
            logger.error(f"Ошибка при обновлении severity дефекта: {str(e)}")
            return False
    
    def get_defects_by_type(self, defect_type: str) -> List[Defect]:
        """Получает дефекты по типу
        
        Args:
            defect_type: Тип дефекта
            
        Returns:
            List[Defect]: Отфильтрованный список
        """
        try:
            if self.db_connection.local_mode:
                return [d for d in self.db_connection.defects_data 
                        if d.defect_type.value == defect_type]
            else:
                collection = self._get_collection()
                defect_dicts = list(collection.find({"defect_type": defect_type}))
                return [Defect(**d) for d in defect_dicts]
        except Exception as e:
            logger.error(f"Ошибка при фильтрации по типу: {str(e)}")
            return []
    
    def get_defects_by_segment(self, segment_number: int) -> List[Defect]:
        """Получает дефекты по номеру сегмента
        
        Args:
            segment_number: Номер сегмента
            
        Returns:
            List[Defect]: Отфильтрованный список
        """
        try:
            if self.db_connection.local_mode:
                return [d for d in self.db_connection.defects_data 
                        if d.segment_number == segment_number]
            else:
                collection = self._get_collection()
                defect_dicts = list(collection.find({"segment_number": segment_number}))
                return [Defect(**d) for d in defect_dicts]
        except Exception as e:
            logger.error(f"Ошибка при фильтрации по сегменту: {str(e)}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получает статистику по дефектам
        
        Returns:
            Dict с статистикой
        """
        defects = self.get_all_defects()
        
        if not defects:
            return {
                "total_defects": 0,
                "defects_by_type": {},
                "defects_by_severity": {},
                "defects_by_location": {},
                "average_depth_percent": 0,
                "critical_defects_count": 0
            }
        
        # Подсчитываем статистику
        defects_by_type = {}
        defects_by_severity = {}
        defects_by_location = {}
        depth_values = []
        critical_count = 0
        
        for defect in defects:
            # По типу
            type_key = defect.defect_type.value
            defects_by_type[type_key] = defects_by_type.get(type_key, 0) + 1
            
            # По severity
            if defect.severity:
                severity_key = defect.severity.value
                defects_by_severity[severity_key] = defects_by_severity.get(severity_key, 0) + 1
                if severity_key == "critical":
                    critical_count += 1
            
            # По локации
            location_key = defect.surface_location.value
            defects_by_location[location_key] = defects_by_location.get(location_key, 0) + 1
            
            # Глубина
            depth_values.append(defect.parameters.depth_percent)
        
        # Средняя глубина
        avg_depth = sum(depth_values) / len(depth_values) if depth_values else 0
        
        return {
            "total_defects": len(defects),
            "defects_by_type": defects_by_type,
            "defects_by_severity": defects_by_severity,
            "defects_by_location": defects_by_location,
            "average_depth_percent": round(avg_depth, 2),
            "critical_defects_count": critical_count
        }
    
    def clear_all(self) -> bool:
        """Очищает все дефекты из БД
        
        Returns:
            bool: Успешность операции
        """
        try:
            if self.db_connection.local_mode:
                self.db_connection.defects_data = []
                logger.info("Локальное хранилище очищено")
            else:
                collection = self._get_collection()
                collection.delete_many({})
                logger.info("Коллекция дефектов в MongoDB очищена")
            return True
        except Exception as e:
            logger.error(f"Ошибка при очистке: {str(e)}")
            return False
    
    def export_to_json(self, output_file: str = 'defects_db.json') -> bool:
        """Экспортирует дефекты из БД в JSON
        
        Args:
            output_file: Файл для сохранения
            
        Returns:
            bool: Успешность операции
        """
        try:
            defects = self.get_all_defects()
            defects_data = [json.loads(d.model_dump_json()) for d in defects]
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(defects_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Экспортировано {len(defects)} дефектов в {output_file}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при экспорте в JSON: {str(e)}")
            return False


class PipelinesRepository:
    """Репозиторий для работы с трубопроводами"""
    
    def __init__(self, db_connection: MongoDBConnection):
        self.db_connection = db_connection
        self.collection_name = 'pipelines'
        self.data = []  # Локальное хранилище
    
    def insert_pipeline(self, pipeline: Pipeline) -> bool:
        """Вставляет трубопровод в БД
        
        Args:
            pipeline: Объект трубопровода
            
        Returns:
            bool: Успешность операции
        """
        try:
            if self.db_connection.local_mode:
                self.data.append(pipeline)
            else:
                collection = self.db_connection.db[self.collection_name]
                collection.insert_one(json.loads(pipeline.model_dump_json()))
            return True
        except Exception as e:
            logger.error(f"Ошибка при вставке трубопровода: {str(e)}")
            return False
    
    def get_all_pipelines(self) -> List[Pipeline]:
        """Получает все трубопроводы
        
        Returns:
            List[Pipeline]: Список трубопроводов
        """
        try:
            if self.db_connection.local_mode:
                return self.data
            else:
                collection = self.db_connection.db[self.collection_name]
                pipeline_dicts = list(collection.find())
                return [Pipeline(**p) for p in pipeline_dicts]
        except Exception as e:
            logger.error(f"Ошибка при получении трубопроводов: {str(e)}")
            return []


class AdminUsersRepository:
    def __init__(self, db_connection: MongoDBConnection):
        self.db_connection = db_connection
        self.local_admins: List[AdminUser] = []
    
    def get_user_by_username(self, username: str) -> Optional[AdminUser]:
        if self.db_connection.local_mode:
            for user in self.local_admins:
                if user.username == username:
                    return user
            return None
        else:
            try:
                user_doc = self.db_connection.db['admin_users'].find_one({"username": username})
                if user_doc:
                    return AdminUser(**user_doc)
                return None
            except Exception as e:
                logger.error(f"Error getting user: {str(e)}")
                return None
    
    def create_admin(self, admin_user: AdminUser) -> Dict[str, Any]:
        if self.db_connection.local_mode:
            if any(u.username == admin_user.username for u in self.local_admins):
                return {"success": False, "error": "User already exists"}
            self.local_admins.append(admin_user)
            logger.info(f"[LOCAL] Created admin: {admin_user.username}")
            return {"success": True, "username": admin_user.username}
        else:
            try:
                user_doc = admin_user.model_dump()
                result = self.db_connection.db['admin_users'].insert_one(user_doc)
                logger.info(f"[MONGODB] Created admin: {admin_user.username}")
                return {"success": True, "username": admin_user.username, "id": str(result.inserted_id)}
            except Exception as e:
                logger.error(f"Error creating admin: {str(e)}")
                return {"success": False, "error": str(e)}
    
    def get_all_admins(self) -> List[AdminUser]:
        if self.db_connection.local_mode:
            return self.local_admins
        else:
            try:
                users = []
                for doc in self.db_connection.db['admin_users'].find({"is_active": True}):
                    users.append(AdminUser(**doc))
                return users
            except Exception as e:
                logger.error(f"Error getting admins: {str(e)}")
                return []
    
    def delete_admin(self, username: str) -> bool:
        if self.db_connection.local_mode:
            original_len = len(self.local_admins)
            self.local_admins = [u for u in self.local_admins if u.username != username]
            return len(self.local_admins) < original_len
        else:
            try:
                result = self.db_connection.db['admin_users'].delete_one({"username": username})
                return result.deleted_count > 0
            except Exception as e:
                logger.error(f"Error deleting admin: {str(e)}")
                return False
