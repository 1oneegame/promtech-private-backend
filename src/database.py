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

from models import Defect, Pipeline, PipelineObject, DefectResponse

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
        defects_by_location = {}
        depth_values = []
        
        for defect in defects:
            # По типу
            type_key = defect.defect_type.value
            defects_by_type[type_key] = defects_by_type.get(type_key, 0) + 1
            
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
            "defects_by_location": defects_by_location,
            "average_depth_percent": round(avg_depth, 2),
            "critical_defects_count": 0  # Пока не считаем
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
