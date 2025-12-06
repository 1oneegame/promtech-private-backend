"""
IntegrityOS FastAPI Backend
REST API для анализа дефектов трубопроводов
"""

import logging
from typing import Dict, Union
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import tempfile
import json
from contextlib import asynccontextmanager
from typing import Optional

from parser import CSVParser
from database import MongoDBConnection, DefectsRepository
from models import Defect, DefectResponse, DefectDetailsResponse, DefectListResponse, StatisticsResponse, DefectType

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ML модуль
try:
    from ml.inference import get_classifier, DefectClassifier
    from ml.config import METRICS_PATH
    ML_AVAILABLE = True
    logger.info("ML модуль импортирован успешно")
except ImportError as e:
    ML_AVAILABLE = False
    logger.warning(f"ML модуль недоступен: {e}")
    get_classifier = None


def defect_to_response(defect: Defect) -> DefectResponse:
    """Преобразует Defect в DefectResponse с структурированными деталями"""
    details = DefectDetailsResponse(
        type=defect.defect_type,
        parameters=defect.parameters,
        location=defect.location,
        surface_location=defect.surface_location,
        distance_to_weld_m=defect.distance_to_weld_m,
        erf_b31g_code=defect.erf_b31g_code
    )
    return DefectResponse(
        defect_id=defect.defect_id,
        segment_number=defect.segment_number,
        measurement_distance_m=defect.measurement_distance_m,
        pipeline_id=defect.pipeline_id,
        details=details
    )

# Глобальные переменные
db_connection: Optional[MongoDBConnection] = None
defects_repository: Optional[DefectsRepository] = None
ml_classifier: Optional['DefectClassifier'] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global db_connection, defects_repository, pipelines_repository, ml_classifier
    
    # Startup
    logger.info("[STARTUP] Initializing IntegrityOS API...")
    
    db_connection = MongoDBConnection(local_mode=False)
    defects_repository = DefectsRepository(db_connection)

    # Проверяем, есть ли уже дефекты в БД
    existing_defects = defects_repository.get_all_defects()
    if not existing_defects:
        logger.info("[STARTUP] No defects found in DB. Parsing CSV files...")
        parser = CSVParser(data_dir='data')
        defects, errors = parser.parse_all_csv_files()

        if errors:
            parser.save_errors_log(errors)
            logger.warning(f"[STARTUP] Found {len(errors)} parsing errors")

        # Вставляем дефекты в БД
        if defects:
            result = defects_repository.insert_defects(defects)
            logger.info(f"[STARTUP] Added {result['inserted']} defects to database")

            # Экспортируем в JSON
            defects_repository.export_to_json('defects_output.json')
            parser.export_to_json(defects, 'defects_parsed.json')
        logger.info("[STARTUP] Initialization complete (data loaded from CSV)")
    else:
        logger.info(f"[STARTUP] {len(existing_defects)} defects already present in DB. Skipping CSV import.")
        logger.info("[STARTUP] Initialization complete (data loaded from DB)")
    
    # Загрузка ML модели
    if ML_AVAILABLE:
        try:
            ml_classifier = get_classifier()
            if ml_classifier and ml_classifier.is_loaded:
                logger.info("[STARTUP] ML модель загружена и готова")
            else:
                logger.warning("[STARTUP] ML модель не загружена (возможно, требуется обучение)")
        except Exception as e:
            logger.error(f"[STARTUP] Ошибка загрузки ML модели: {e}")
            ml_classifier = None
    else:
        logger.info("[STARTUP] ML модуль недоступен")
    
    yield
    
    # Shutdown
    if db_connection:
        db_connection.close()
    logger.info("[SHUTDOWN] Application terminated")


# Инициализация FastAPI приложения с lifespan
app = FastAPI(
    title="IntegrityOS API",
    version="1.0.0",
    lifespan=lifespan,
    tags_metadata=[
        {
            "name": "Health",
            "description": "Проверка статуса API",
        },
        {
            "name": "Defects",
            "description": "Работа с дефектами - получение, поиск, фильтрация",
        },
        {
            "name": "Analytics",
            "description": "Статистика и аналитика по дефектам",
        },
        {
            "name": "Export",
            "description": "Экспорт данных в различные форматы",
        },
        {
            "name": "ML",
            "description": "Машинное обучение - предсказание критичности дефектов",
        },
        {
            "name": "Admin",
            "description": "Административные операции - перезагрузка и очистка данных",
        },
        {
            "name": "Info",
            "description": "Информация о системе",
        },
    ]
)

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== ENDPOINTS ====================

@app.get("/", tags=["Health"])
async def root():
    """Корневой эндпоинт - проверка статуса API"""
    return {
        "service": "IntegrityOS API",
        "version": "1.0.0",
        "status": "active",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health_check():
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


@app.get("/defects", response_model=DefectListResponse, tags=["Defects"])
async def get_defects(
    defect_type: Optional[str] = Query(None, description="Тип дефекта"),
    segment: Optional[int] = Query(None, description="Номер сегмента"),
):
    """
    Получить дефекты с опциональной фильтрацией
    
    **Параметры:**
    - `defect_type`: коррозия, сварной шов, металлический объект
    - `segment`: номер сегмента трубопровода
    """
    try:
        # Получаем все дефекты или отфильтрованные
        if defect_type:
            defects = defects_repository.get_defects_by_type(defect_type)
        elif segment:
            defects = defects_repository.get_defects_by_segment(segment)
        else:
            defects = defects_repository.get_all_defects()
        
        # Применяем комбинированные фильтры
        if defect_type and segment:
            defects = [d for d in defects if d.segment_number == segment]
        
        total = len(defects)
        
        # Конвертируем Defect в DefectResponse
        response_defects = [defect_to_response(d) for d in defects]
        
        return DefectListResponse(
            total=total,
            defects=response_defects,
            filters_applied={
                "defect_type": defect_type,
                "segment": segment
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting defects: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/defects/search", response_model=DefectListResponse, tags=["Defects"])
async def search_defects(
    defect_type: Optional[str] = None,
    segment: Optional[int] = None
):
    """Получить дефекты с применением множественных фильтров
    
    Примеры:
    - /defects/search?defect_type=коррозия
    - /defects/search?segment=3
    - /defects/search?defect_type=коррозия&segment=3
    """
    try:
        all_defects = defects_repository.get_all_defects()
        filtered_defects = all_defects
        
        # Применяем фильтры
        if defect_type:
            filtered_defects = [d for d in filtered_defects if d.defect_type.value == defect_type]
        
        if segment is not None:
            filtered_defects = [d for d in filtered_defects if d.segment_number == segment]
        
        response_defects = [defect_to_response(d) for d in filtered_defects]
        return DefectListResponse(
            total=len(filtered_defects),
            defects=response_defects,
            filters_applied={
                "defect_type": defect_type,
                "segment": segment
            }
        )
    except Exception as e:
        logger.error(f"Error searching defects: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/defects/{defect_id}", response_model=DefectResponse, tags=["Defects"])
async def get_defect(defect_id: str):
    """Получить дефект по ID"""
    try:
        defects = defects_repository.get_all_defects()
        # Простой поиск по индексу (для локального режима)
        for defect in defects:
            if str(defect.defect_id or "") == defect_id:
                return defect_to_response(defect)
        raise HTTPException(status_code=404, detail="Defect not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting defect: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/defects/type/{defect_type}", response_model=DefectListResponse, tags=["Defects"])
async def get_defects_by_type(defect_type: str):
    """Получить дефекты по типу"""
    try:
        valid_types = [t.value for t in DefectType]
        if defect_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid defect type. Allowed: {', '.join(valid_types)}"
            )
        
        defects = defects_repository.get_defects_by_type(defect_type)
        response_defects = [defect_to_response(d) for d in defects]
        return DefectListResponse(
            total=len(defects),
            defects=response_defects,
            filters_applied={"defect_type": defect_type}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting defects by type: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/defects/segment/{segment_id}", response_model=DefectListResponse, tags=["Defects"])
async def get_defects_by_segment(segment_id: int):
    """Получить дефекты по номеру сегмента"""
    try:
        defects = defects_repository.get_defects_by_segment(segment_id)
        response_defects = [defect_to_response(d) for d in defects]
        return DefectListResponse(
            total=len(defects),
            defects=response_defects,
            filters_applied={"segment": segment_id}
        )
    except Exception as e:
        logger.error(f"Error getting defects by segment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/statistics", response_model=StatisticsResponse, tags=["Analytics"])
async def get_statistics():
    """Получить статистику по дефектам"""
    try:
        stats = defects_repository.get_statistics()
        return StatisticsResponse(**stats)
    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/export/json", tags=["Export"])
async def export_to_json():
    """Экспортировать дефекты в JSON файл для скачивания"""
    try:
        defects = defects_repository.get_all_defects()
        if not defects:
            raise HTTPException(status_code=404, detail="No defects found")
        
        # Конвертируем в DefectResponse формат (как в других эндпоинтах)
        response_defects = [defect_to_response(d) for d in defects]
        defects_dict = [defect.model_dump() for defect in response_defects]
        
        # Создаём временный файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(defects_dict, temp_file, ensure_ascii=False, indent=2)
            temp_filename = temp_file.name
        
        # Возвращаем файл для скачивания
        return FileResponse(
            path=temp_filename,
            filename="defects_export.json",
            media_type='application/json',
            background=None  # Файл будет удалён автоматически после отправки
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting to JSON: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/info", tags=["Info"])
async def get_info():
    """Получить информацию о системе и доступных сервисах"""
    try:
        defects = defects_repository.get_all_defects()
        stats = defects_repository.get_statistics()
        
        return {
            "application": "IntegrityOS",
            "version": "1.0.0",
            "database_mode": "local" if db_connection.local_mode else "mongodb",
            "total_defects": len(defects),
            "ml_available": ML_AVAILABLE,
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


# ==================== BATCH OPERATIONS ====================

@app.post("/reload", tags=["Admin"])
async def reload_data():
    """Перезагрузить данные из CSV"""
    try:
        # Очищаем БД
        defects_repository.clear_all()
        
        # Парсим CSV заново
        parser = CSVParser(data_dir='data')
        defects, errors = parser.parse_all_csv_files()
        
        # Вставляем в БД
        result = defects_repository.insert_defects(defects)
        
        return {
            "status": "success",
            "message": "Data reloaded",
            "inserted": result["inserted"],
            "errors": len(errors),
            "error_log": "parse_errors.log" if errors else None
        }
    except Exception as e:
        logger.error(f"Error reloading data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/clear", tags=["Admin"])
async def clear_data():
    """Очистить все дефекты из БД"""
    try:
        success = defects_repository.clear_all()
        if success:
            return {"status": "success", "message": "All defects cleared"}
        else:
            raise HTTPException(status_code=500, detail="Clear failed")
    except Exception as e:
        logger.error(f"Error clearing data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ML ENDPOINTS ====================

# Модели для вложенной структуры (новый формат)
class DefectParameters(BaseModel):
    """
    Параметры дефекта.
    
    ВАЖНО: Все геометрические параметры теперь ИСПОЛЬЗУЮТСЯ в ML модели!
    
    Опциональные параметры (length_mm, width_mm, depth_mm, wall_thickness_mm)
    могут быть null - в этом случае модель заполнит их медианой из обучающей выборки.
    """
    length_mm: Optional[float] = Field(None, description="✓ ИСПОЛЬЗУЕТСЯ - Длина дефекта (мм). Может быть null → заполнится медианой")
    width_mm: Optional[float] = Field(None, description="✓ ИСПОЛЬЗУЕТСЯ - Ширина дефекта (мм). Может быть null → заполнится медианой")
    depth_mm: Optional[float] = Field(None, description="✓ ИСПОЛЬЗУЕТСЯ - Глубина дефекта в абсолютных единицах (мм). Может быть null → заполнится медианой")
    depth_percent: float = Field(..., description="✓ ИСПОЛЬЗУЕТСЯ - Глубина дефекта в % от толщины стенки (ОБЯЗАТЕЛЬНО)", ge=0, le=100)
    wall_thickness_mm: Optional[float] = Field(None, description="✓ ИСПОЛЬЗУЕТСЯ - Толщина стенки трубопровода (мм). Может быть null → заполнится медианой")


class DefectLocation(BaseModel):
    """Местоположение дефекта"""
    latitude: float = Field(..., description="Широта", ge=-90, le=90)
    longitude: float = Field(..., description="Долгота", ge=-180, le=180)
    altitude: float = Field(..., description="Высота над уровнем моря (м)")


class DefectDetails(BaseModel):
    """Детальная информация о дефекте"""
    type: str = Field(..., description="Тип дефекта")
    parameters: DefectParameters = Field(..., description="Параметры дефекта")
    location: DefectLocation = Field(..., description="Местоположение")
    surface_location: str = Field(..., description="Расположение на поверхности (ВНШ/ВНТ)")
    distance_to_weld_m: Optional[float] = Field(None, description="✓ ИСПОЛЬЗУЕТСЯ - Расстояние до сварного шва (м). Может быть null → заполнится медианой")
    erf_b31g_code: float = Field(..., description="Коэффициент ERF B31G", ge=0, le=1)


class MLPredictionRequestNested(BaseModel):
    """
    Запрос для предсказания критичности дефекта (вложенная структура).
    
    Поддерживает полный набор параметров дефекта в иерархической структуре.
    Все геометрические параметры (length_mm, width_mm, depth_mm, wall_thickness_mm, 
    distance_to_weld_m) теперь используются в модели.
    """
    defect_id: Optional[str] = Field(None, description="⚠️ НЕ ИСПОЛЬЗУЕТСЯ - ID дефекта (для идентификации)")
    segment_number: Optional[int] = Field(None, description="⚠️ НЕ ИСПОЛЬЗУЕТСЯ - Номер сегмента трубопровода")
    measurement_distance_m: float = Field(..., description="✓ ИСПОЛЬЗУЕТСЯ - Расстояние вдоль трубопровода (м)", ge=0)
    pipeline_id: Optional[str] = Field(None, description="⚠️ НЕ ИСПОЛЬЗУЕТСЯ - ID трубопровода (для идентификации)")
    details: DefectDetails = Field(..., description="Детали дефекта")

    class Config:
        json_schema_extra = {
            "example": {
                "measurement_distance_m": 6.201,
                "pipeline_id": "MT-03",
                "details": {
                    "type": "коррозия",
                    "parameters": {
                        "length_mm": 27.0,
                        "width_mm": 19.0,
                        "depth_mm": None,
                        "depth_percent": 9.0,
                        "wall_thickness_mm": 7.9
                    },
                    "location": {
                        "latitude": 48.480297,
                        "longitude": 57.666958,
                        "altitude": 265.2
                    },
                    "surface_location": "ВНШ",
                    "distance_to_weld_m": -1.869,
                    "erf_b31g_code": 0.52
                }
            }
        }


# Модели для плоской структуры (старый формат - обратная совместимость)
class MLPredictionRequest(BaseModel):
    """
    Запрос для предсказания критичности дефекта (плоская структура).
    
    Упрощенный формат для обратной совместимости. Содержит все параметры,
    которые используются в модели в плоской структуре без вложенности.
    """
    defect_id: Optional[str] = Field(None, description="⚠️ НЕ ИСПОЛЬЗУЕТСЯ - ID дефекта (для идентификации)")
    segment_number: Optional[int] = Field(None, description="⚠️ НЕ ИСПОЛЬЗУЕТСЯ - Номер сегмента")
    depth_percent: float = Field(..., description="✓ ИСПОЛЬЗУЕТСЯ - Глубина дефекта в процентах (ОБЯЗАТЕЛЬНО)", ge=0, le=100)
    depth_mm: Optional[float] = Field(None, description="✓ ИСПОЛЬЗУЕТСЯ - Глубина дефекта (мм). null → медиана")
    length_mm: Optional[float] = Field(None, description="✓ ИСПОЛЬЗУЕТСЯ - Длина дефекта (мм). null → медиана")
    width_mm: Optional[float] = Field(None, description="✓ ИСПОЛЬЗУЕТСЯ - Ширина дефекта (мм). null → медиана")
    wall_thickness_mm: Optional[float] = Field(None, description="✓ ИСПОЛЬЗУЕТСЯ - Толщина стенки (мм). null → медиана")
    distance_to_weld_m: Optional[float] = Field(None, description="✓ ИСПОЛЬЗУЕТСЯ - Расстояние до сварного шва (м). null → медиана")
    erf_b31g: float = Field(..., description="✓ ИСПОЛЬЗУЕТСЯ - Коэффициент ERF B31G", ge=0, le=1)
    altitude_m: float = Field(..., description="✓ ИСПОЛЬЗУЕТСЯ - Высота над уровнем моря (м)")
    latitude: float = Field(..., description="✓ ИСПОЛЬЗУЕТСЯ - Широта", ge=-90, le=90)
    longitude: float = Field(..., description="✓ ИСПОЛЬЗУЕТСЯ - Долгота", ge=-180, le=180)
    measurement_distance_m: float = Field(..., description="✓ ИСПОЛЬЗУЕТСЯ - Расстояние вдоль трубопровода (м)", ge=0)
    pipeline_id: Optional[str] = Field(None, description="⚠️ НЕ ИСПОЛЬЗУЕТСЯ - ID трубопровода (для идентификации)")
    defect_type: str = Field(..., description="✓ ИСПОЛЬЗУЕТСЯ - Тип дефекта")
    surface_location: str = Field(..., description="✓ ИСПОЛЬЗУЕТСЯ - Расположение на поверхности (ВНШ/ВНТ)")

    class Config:
        json_schema_extra = {
            "example": {
                "depth_percent": 9.0,
                "depth_mm": 0.7,
                "length_mm": 27.0,
                "width_mm": 19.0,
                "wall_thickness_mm": 7.9,
                "distance_to_weld_m": -1.869,
                "erf_b31g": 0.52,
                "altitude_m": 265.2,
                "latitude": 48.480297,
                "longitude": 57.666958,
                "measurement_distance_m": 6.201,
                "defect_type": "коррозия",
                "surface_location": "ВНШ",
                "pipeline_id": "MT-03"
            }
        }


class MLPredictionResponse(BaseModel):
    """
    Ответ с предсказанием критичности дефекта.
    
    Содержит предсказанный уровень критичности, вероятности всех классов
    и метаинформацию о модели.
    """
    severity: str = Field(..., description="Предсказанный уровень: normal (низкий риск) / medium (требует мониторинга) / high (критический)")
    probability: float = Field(..., description="Уверенность модели в предсказании (0-1)")
    probabilities: Dict[str, float] = Field(..., description="Вероятности всех классов: {normal: 0.x, medium: 0.y, high: 0.z}")
    model_type: str = Field(..., description="Название модели: RandomForest / XGBoost / LogisticRegression")
    prediction_timestamp: str = Field(..., description="Время предсказания в формате ISO 8601")


def convert_nested_to_flat(nested_request: MLPredictionRequestNested) -> dict:
    """Конвертация вложенной структуры в плоскую для ML модели"""
    return {
        "defect_id": nested_request.defect_id,
        "segment_number": nested_request.segment_number,
        "depth_percent": nested_request.details.parameters.depth_percent,
        "depth_mm": nested_request.details.parameters.depth_mm,
        "length_mm": nested_request.details.parameters.length_mm,
        "width_mm": nested_request.details.parameters.width_mm,
        "wall_thickness_mm": nested_request.details.parameters.wall_thickness_mm,
        "distance_to_weld_m": nested_request.details.distance_to_weld_m,
        "erf_b31g": nested_request.details.erf_b31g_code,
        "altitude_m": nested_request.details.location.altitude,
        "latitude": nested_request.details.location.latitude,
        "longitude": nested_request.details.location.longitude,
        "measurement_distance_m": nested_request.measurement_distance_m,
        "pipeline_id": nested_request.pipeline_id,
        "defect_type": nested_request.details.type,
        "surface_location": nested_request.details.surface_location
    }


@app.post("/ml/predict", response_model=MLPredictionResponse, tags=["ML"], 
          summary="Предсказание критичности дефекта",
          response_description="Предсказанный уровень критичности с вероятностями")
async def predict_defect_criticality(request: Union[MLPredictionRequest, MLPredictionRequestNested]):
    """
    # Предсказать критичность дефекта используя ML модель
    
    Анализирует параметры дефекта магистрального трубопровода и предсказывает уровень критичности.
    
    ## Поддерживаемые форматы запроса
    
    ### 1. Вложенная структура (рекомендуется) - более структурирована
    ```json
    {
      "measurement_distance_m": 6.201,
      "pipeline_id": "MT-03",
      "details": {
        "type": "коррозия",
        "parameters": {
          "depth_percent": 9.0,
          "length_mm": 27.0,
          "width_mm": 19.0,
          "depth_mm": null,
          "wall_thickness_nominal_mm": 7.9
        },
        "location": {
          "latitude": 48.480297,
          "longitude": 57.666958,
          "altitude": 265.2
        },
        "surface_location": "ВНШ",
        "distance_to_weld_m": -1.869,
        "erf_b31g_code": 0.52
      }
    }
    ```
    
    ### 2. Плоская структура (обратная совместимость) - упрощенная
    ```json
    {
      "depth_percent": 9.0,
      "erf_b31g": 0.52,
      "altitude_m": 265.2,
      "latitude": 48.480297,
      "longitude": 57.666958,
      "measurement_distance_m": 6.201,
      "defect_type": "коррозия",
      "surface_location": "ВНШ",
      "pipeline_id": "MT-03",
      "defect_id": "DEF-001",
      "segment_number": 3
    }
    ```
    
    ## Параметры, влияющие на предсказание (используются моделью):
    1. **depth_percent** - Глубина дефекта в процентах (от толщины стенки)
    2. **depth_mm** - Глубина дефекта в абсолютных единицах (мм)
    3. **length_mm** - Длина дефекта в миллиметрах
    4. **width_mm** - Ширина дефекта в миллиметрах
    5. **wall_thickness_mm** - Толщина стенки трубопровода в мм
    6. **distance_to_weld_m** - Расстояние до сварного шва (м)
    7. **erf_b31g_code** - Коэффициент ERF B31G для оценки прочности
    8. **latitude, longitude** - Географические координаты (климатические условия)
    9. **altitude** - Высота над уровнем моря (давление, климат)
    10. **measurement_distance_m** - Расстояние вдоль трубопровода
    11. **defect_type** - Тип дефекта (коррозия, трещина и т.д.)
    12. **surface_location** - Расположение на поверхности трубы (ВНШ/ВНТ)
    
    ## Параметры, НЕ используемые моделью (информационные/архивные):
    - **defect_id** - ID дефекта (только для идентификации, не влияет)
    - **segment_number** - Номер сегмента трубопровода (только для идентификации)
    - **pipeline_id** - ID трубопровода (только для идентификации, не влияет)
    
    ## Результат предсказания
    
    Возвращает объект с полями:
    - **severity** - Уровень критичности: `normal` / `medium` / `high`
    - **probability** - Уверенность модели в предсказании (0-1)
    - **probabilities** - Распределение вероятностей всех классов
    - **model_type** - Используемый алгоритм: RandomForest / XGBoost / LogisticRegression
    - **prediction_timestamp** - Время выполнения предсказания
    
    ## Типы дефектов:
    коррозия, трещина, вмятина, расслоение, царапина, выработка, потеря металла, деформация
    
    ## Уровни критичности:
    - **normal** - Нормальный (низкий риск) - дефект не требует срочного вмешательства
    - **medium** - Средний (требует мониторинга) - нужно отслеживать развитие дефекта
    - **high** - Высокий (критический) - требуется немедленное вмешательство
    """
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ML модуль недоступен. Проверьте установку зависимостей."
        )
    
    if ml_classifier is None or not ml_classifier.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="ML модель не загружена. При первом запросе будет выполнено автоматическое обучение (может занять 1-2 минуты)."
        )
    
    try:
        # Подготовить данные для предсказания
        if isinstance(request, MLPredictionRequestNested):
            # Конвертация вложенной структуры в плоскую
            sample = convert_nested_to_flat(request)
        else:
            # Плоская структура используется как есть
            sample = request.dict()
        
        # Предсказание
        result = ml_classifier.predict(sample)
        
        return MLPredictionResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Ошибка в данных: {str(e)}")
    except Exception as e:
        logger.error(f"ML prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка предсказания: {str(e)}")


@app.get("/ml/model/metrics", tags=["ML"], 
          summary="Метрики обученной ML модели",
          response_description="Classification report, confusion matrix, feature importance")
async def get_model_metrics():
    """
    # Получить метрики обученной модели
    
    Возвращает подробные метрики качества модели машинного обучения:
    - Classification report (precision, recall, f1-score для каждого класса)
    - Confusion matrix (матрица ошибок)
    - Feature importance (важность признаков для предсказания)
    - Общие показатели качества (accuracy, macro avg, weighted avg)
    
    ## Типы метрик:
    - **Precision** - точность (доля правильных позитивных предсказаний)
    - **Recall** - полнота (доля найденных дефектов нужного типа)
    - **F1-score** - гармоническое среднее precision и recall
    - **Support** - количество примеров каждого класса в тестовом наборе
    
    ## Классы (уровни критичности):
    - normal - Нормальный (низкий риск)
    - medium - Средний (требует мониторинга)
    - high - Высокий (критический)
    """
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ML модуль недоступен"
        )
    
    try:
        if not METRICS_PATH.exists():
            raise HTTPException(
                status_code=404,
                detail="Метрики не найдены. Модель не обучена. Запустите: python -m src.ml.train"
            )
        
        with open(METRICS_PATH, 'r', encoding='utf-8') as f:
            metrics = json.load(f)
        
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ml/model/info", tags=["ML"],
          summary="Информация о ML модели",
          response_description="Метаданные и характеристики загруженной модели")
async def get_model_info():
    """
    # Получить информацию о загруженной ML модели
    
    Возвращает метаинформацию о текущей модели машинного обучения:
    - Тип модели (RandomForest / XGBoost / LogisticRegression)
    - F1 score (средний показатель качества)
    - Дата обучения модели
    - Используемые признаки для предсказания
    - Классы предсказания (уровни критичности)
    - Состояние загрузки модели
    
    ## Используемые признаки:
    1. depth_percent - Глубина дефекта
    2. erf_b31g_code - Коэффициент ERF B31G
    3. latitude, longitude, altitude - Геолокация
    4. measurement_distance_m - Расстояние по трубопроводу
    5. defect_type - Тип дефекта
    6. surface_location - Расположение на поверхности
    """
    if not ML_AVAILABLE:
        return {
            "status": "unavailable",
            "message": "ML модуль не установлен"
        }
    
    if ml_classifier is None:
        return {
            "status": "not_initialized",
            "message": "ML классификатор не инициализирован"
        }
    
    try:
        info = ml_classifier.get_model_info()
        return info
    except Exception as e:
        logger.error(f"Error getting model info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
