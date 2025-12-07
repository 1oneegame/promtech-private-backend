import logging
from contextlib import asynccontextmanager
from typing import Optional, Union

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import MongoDBConnection, DefectsRepository, AdminUsersRepository, AdminUser, SeverityLevel, AdminDefectCreateRequest
from parsers import CSVParser
from api import health, auth_routes, defects, analytics, export, admin, ml_routes, reports
from api.ml_routes import MLPredictionRequest, MLPredictionRequestNested
from auth import set_admin_repository, get_password_hash

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ML модуль
try:
    from ml.inference import get_classifier, defect_to_ml_input
    from ml.config import METRICS_PATH
    ML_AVAILABLE = True
    logger.info("ML модуль импортирован успешно")
except ImportError as e:
    ML_AVAILABLE = False
    METRICS_PATH = None
    defect_to_ml_input = None
    logger.warning(f"ML модуль недоступен: {e}")

# Глобальные переменные
db_connection: Optional[MongoDBConnection] = None
defects_repository: Optional[DefectsRepository] = None
admin_repository: Optional[AdminUsersRepository] = None
ml_classifier = None  # Тип зависит от ml модуля

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global db_connection, defects_repository, admin_repository, ml_classifier
    
    # Startup
    logger.info("[STARTUP] Initializing IntegrityOS API...")
    
    db_connection = MongoDBConnection(local_mode=False)
    defects_repository = DefectsRepository(db_connection)
    admin_repository = AdminUsersRepository(db_connection)
    
    # Установить глобальный репозиторий админов для auth модуля
    set_admin_repository(admin_repository)
    
    # Создать дефолтного админа если его нет
    default_admin = admin_repository.get_user_by_username("admin")
    if not default_admin:
        from datetime import datetime
        default_admin_user = AdminUser(
            username="admin",
            password_hash=get_password_hash("admin"),
            role="admin",
            created_at=datetime.utcnow(),
            is_active=True
        )
        result = admin_repository.create_admin(default_admin_user)
        if result["success"]:
            logger.info("[STARTUP] Created default admin user (username: admin, password: admin)")
        else:
            logger.warning(f"[STARTUP] Failed to create default admin: {result.get('error')}")
    else:
        logger.info("[STARTUP] Admin users loaded from database")

    existing_defects = defects_repository.get_all_defects()
    if not existing_defects:
        logger.info("[STARTUP] No defects found in DB. Parsing CSV files...")
        parser = CSVParser(data_dir='data')
        defects, errors = parser.parse_all_csv_files()

        if errors:
            parser.save_errors_log(errors)
            logger.warning(f"[STARTUP] Found {len(errors)} parsing errors")

        if defects:
            # Сначала загружаем ML модель
            if ML_AVAILABLE:
                try:
                    ml_classifier = get_classifier()
                    if ml_classifier and ml_classifier.is_loaded:
                        logger.info("[STARTUP] ML модель загружена, начинаем предсказание severity для дефектов...")
                        
                        # Предсказываем severity для каждого дефекта
                        predicted_count = 0
                        for defect in defects:
                            try:
                                ml_input = defect_to_ml_input(defect)
                                prediction = ml_classifier.predict(ml_input)
                                
                                # Сохраняем предсказание в объект дефекта
                                defect.severity = SeverityLevel(prediction["severity"])
                                defect.probability = prediction["probability"]
                                predicted_count += 1
                            except Exception as e:
                                logger.warning(f"[STARTUP] Не удалось предсказать severity для дефекта {defect.defect_id}: {e}")
                        
                        logger.info(f"[STARTUP] Предсказан severity для {predicted_count}/{len(defects)} дефектов")
                    else:
                        logger.warning("[STARTUP] ML модель не загружена, дефекты будут сохранены без severity")
                except Exception as e:
                    logger.error(f"[STARTUP] Ошибка загрузки ML модели: {e}")
                    logger.warning("[STARTUP] Дефекты будут сохранены без severity")
            
            result = defects_repository.insert_defects(defects)
            logger.info(f"[STARTUP] Added {result['inserted']} defects to database")
            defects_repository.export_to_json('defects_output.json')
            parser.export_to_json(defects, 'defects_parsed.json')
        logger.info("[STARTUP] Initialization complete (data loaded from CSV)")
    else:
        logger.info(f"[STARTUP] {len(existing_defects)} defects already present in DB. Skipping CSV import.")
        logger.info("[STARTUP] Initialization complete (data loaded from DB)")
    
    # Загрузка ML модели (если еще не загружена)
    if ML_AVAILABLE and ml_classifier is None:
        try:
            ml_classifier = get_classifier()
            if ml_classifier and ml_classifier.is_loaded:
                logger.info("[STARTUP] ML модель загружена и готова")
            else:
                logger.warning("[STARTUP] ML модель не загружена")
        except Exception as e:
            logger.error(f"[STARTUP] Ошибка загрузки ML модели: {e}")
            ml_classifier = None
    else:
        logger.info("[STARTUP] ML модуль недоступен")
    
    # Установить зависимости для admin роутов
    from api.admin import set_repository, set_ml_dependencies, set_audit_repository
    from core.user_repositories import AuditLogRepository
    set_repository(defects_repository)
    set_ml_dependencies(ml_classifier, ML_AVAILABLE)
    audit_repository = AuditLogRepository(db_connection)
    set_audit_repository(audit_repository)
    logger.info("[STARTUP] Admin routes dependencies initialized")
    
    yield
    
    # Shutdown
    if db_connection:
        db_connection.close()
    logger.info("[SHUTDOWN] Application terminated")


# Инициализация FastAPI приложения
app = FastAPI(
    title="IntegrityOS API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency injection для роутов
def get_dependencies():
    """Динамически получить зависимости"""
    return {
        'db_connection': db_connection,
        'defects_repository': defects_repository,
        'ml_classifier': ml_classifier,
        'ml_available': ML_AVAILABLE,
        'metrics_path': METRICS_PATH,
        'defect_to_ml_input': defect_to_ml_input
    }


# Подключение роутов с dependency injection
def setup_routes():
    """Настройка всех роутов с зависимостями"""
    
    # Health & Info
    @app.get("/", tags=["Health"],
             summary="Корневой endpoint",
             description="""Приветственная страница API.
             
    **Пример ответа:**
    ```json
    {
      "message": "IntegrityOS API is running",
      "version": "1.0.0",
      "docs": "/docs"
    }
    ```
    """)
    async def root():
        return await health.root()
    
    @app.get("/health", tags=["Health"],
             summary="Проверка здоровья системы",
             description="""Возвращает статус работы всех компонентов системы.
             
    **Пример ответа:**
    ```json
    {
      "status": "healthy",
      "database": "connected",
      "defects_count": 1234,
      "timestamp": "2025-12-07T10:30:00"
    }
    ```
    """)
    async def health_check():
        deps = get_dependencies()
        return await health.health_check(deps['db_connection'], deps['defects_repository'])
    
    @app.get("/info", tags=["Info"],
             summary="Информация о системе",
             description="""Детальная информация о конфигурации и возможностях системы.
             
    **Пример ответа:**
    ```json
    {
      "version": "1.0.0",
      "database": "MongoDB",
      "ml_available": true,
      "total_defects": 1234,
      "defect_types": ["коррозия", "трещина", "вмятина"]
    }
    ```
    """)
    async def get_info():
        deps = get_dependencies()
        return await health.get_info(deps['db_connection'], deps['defects_repository'], deps['ml_available'])
    
    # Auth
    from api.auth_routes import router as auth_router
    app.include_router(auth_router)
    
    # Users
    from api.users import router as users_router
    app.include_router(users_router)
    
    # Tasks
    from api.tasks import router as tasks_router
    app.include_router(tasks_router)
    
    # Audit Logs
    from api.audit_logs import router as audit_logs_router
    app.include_router(audit_logs_router)
    
    # Favorites
    from api.favorites import router as favorites_router
    app.include_router(favorites_router)
    
    # Admin
    from api.admin import router as admin_router
    app.include_router(admin_router, prefix="/admin")
    
    # Reports
    from api import reports
    
    @app.get("/reports/generate", tags=["Reports"],
             summary="Генерация отчета",
             description="Генерирует отчет в формате HTML или PDF")
    async def generate_report_endpoint(
        report_type: str = "summary",
        format: str = "html"
    ):
        deps = get_dependencies()
        return await reports.generate_report(report_type, format, deps['defects_repository'])
    
    @app.get("/reports/history", tags=["Reports"],
             summary="История отчетов",
             description="Возвращает список последних сгенерированных отчетов")
    async def get_reports_history_endpoint():
        return await reports.get_reports_history()
    
    @app.get("/reports/download", tags=["Reports"],
             summary="Скачать отчет",
             description="Скачивание ранее сгенерированного отчета")
    async def download_report_endpoint(filename: str):
        return await reports.download_report(filename)
    
    # Defects
    @app.get("/defects", tags=["Defects"],
             summary="Получить список дефектов",
             description="""Возвращает список всех дефектов с возможностью фильтрации.
             
    **Параметры запроса:**
    - `defect_type` (optional): Фильтр по типу дефекта (коррозия, трещина, вмятина и т.д.)
    - `segment` (optional): Фильтр по номеру сегмента трубопровода
    
    **Примеры запросов:**
    - `GET /defects` - все дефекты
    - `GET /defects?defect_type=коррозия` - только коррозия
    - `GET /defects?segment=3` - дефекты сегмента 3
    
    **Пример ответа:**
    ```json
    [
      {
        "defect_id": "65716dae-81e2-402d-8610-b583fe56dd1a",
        "segment_number": 3,
        "measurement_distance_m": 5.803,
        "pipeline_id": "MT-03",
        "severity": "medium",
        "details": {
          "type": "коррозия",
          "parameters": {
            "depth_percent": 11.0,
            "length_mm": 15.0,
            "width_mm": 15.0
          }
        }
      }
    ]
    ```
    """)
    async def get_defects_endpoint(defect_type: Optional[str] = None, segment: Optional[int] = None):
        deps = get_dependencies()
        return await defects.get_defects(defect_type, segment, deps['defects_repository'])
    
    @app.get("/defects/search", tags=["Defects"],
             summary="Поиск дефектов",
             description="""Расширенный поиск дефектов с фильтрацией.
             
    **Параметры:**
    - `defect_type`: Тип дефекта
    - `segment`: Номер сегмента
    
    **Пример:** `GET /defects/search?defect_type=коррозия&segment=3`
    """)
    async def search_defects_endpoint(defect_type=None, segment=None):
        deps = get_dependencies()
        return await defects.search_defects(defect_type, segment, deps['defects_repository'])
    
    @app.get("/defects/{defect_id}", tags=["Defects"],
             summary="Получить дефект по ID",
             description="""Возвращает полную информацию о конкретном дефекте.
             
    **Пример запроса:**
    ```
    GET /defects/65716dae-81e2-402d-8610-b583fe56dd1a
    ```
    
    **Пример ответа:**
    ```json
    {
      "defect_id": "65716dae-81e2-402d-8610-b583fe56dd1a",
      "segment_number": 3,
      "measurement_distance_m": 5.803,
      "pipeline_id": "MT-03",
      "severity": "medium",
      "details": {
        "type": "коррозия",
        "parameters": {
          "depth_percent": 11.0,
          "length_mm": 15.0,
          "width_mm": 15.0,
          "depth_mm": null,
          "wall_thickness_nominal_mm": 7.9
        },
        "location": {
          "latitude": 48.479509,
          "longitude": 57.665673,
          "altitude": 265.0
        },
        "surface_location": "ВНШ",
        "distance_to_weld_m": -1.471,
        "erf_b31g_code": 0.48
      }
    }
    ```
    """)
    async def get_defect_endpoint(defect_id: str):
        deps = get_dependencies()
        return await defects.get_defect(defect_id, deps['defects_repository'])
    
    @app.get("/defects/type/{defect_type}", tags=["Defects"],
             summary="Получить дефекты по типу",
             description="""Возвращает все дефекты указанного типа.
             
    **Доступные типы дефектов:**
    - коррозия
    - трещина
    - вмятина
    - расслоение
    - царапина
    - выработка
    - потеря металла
    - деформация
    
    **Пример запроса:**
    ```
    GET /defects/type/коррозия
    ```
    
    **Пример ответа:** Массив дефектов указанного типа
    """)
    async def get_defects_by_type_endpoint(defect_type: str):
        deps = get_dependencies()
        return await defects.get_defects_by_type(defect_type, deps['defects_repository'])
    
    @app.get("/defects/segment/{segment_id}", tags=["Defects"],
             summary="Получить дефекты по сегменту",
             description="""Возвращает все дефекты на указанном сегменте трубопровода.
             
    **Пример запроса:**
    ```
    GET /defects/segment/3
    ```
    
    **Пример ответа:** Массив всех дефектов на сегменте 3
    """)
    async def get_defects_by_segment_endpoint(segment_id: int):
        deps = get_dependencies()
        return await defects.get_defects_by_segment(segment_id, deps['defects_repository'])
    
    # Analytics
    @app.get("/statistics", tags=["Analytics"],
             summary="Статистика по дефектам",
             description="""Возвращает агрегированную статистику по всем дефектам.
             
    **Пример ответа:**
    ```json
    {
      "total_defects": 1234,
      "by_type": {
        "коррозия": 456,
        "трещина": 234,
        "вмятина": 123
      },
      "by_severity": {
        "normal": 800,
        "medium": 300,
        "high": 134
      },
      "by_segment": {
        "1": 200,
        "2": 300,
        "3": 400
      },
      "average_depth_percent": 12.5,
      "critical_defects_count": 134
    }
    ```
    """)
    async def get_statistics():
        deps = get_dependencies()
        return await analytics.get_statistics(deps['defects_repository'])
    
    # Export
    @app.get("/export/json", tags=["Export"],
             summary="Экспорт всех дефектов в JSON",
             description="""Экспортирует все дефекты в формате JSON для загрузки.
             
    **Пример использования:**
    ```
    GET /export/json
    ```
    
    Возвращает файл с полным списком всех дефектов в JSON формате.
    """)
    async def export_json():
        deps = get_dependencies()
        return await export.export_to_json(deps['defects_repository'])
    
    # Admin endpoints are now handled by admin router (included above)
    
    # ML
    @app.post("/ml/predict", tags=["ML"], 
              summary="Предсказание критичности дефекта",
              description="""
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
    """)
    async def predict(request: Union[MLPredictionRequest, MLPredictionRequestNested]):
        deps = get_dependencies()
        return await ml_routes.predict_defect_criticality(
            request, deps['ml_classifier'], deps['ml_available']
        )
    
    @app.get("/ml/model/metrics", tags=["ML"],
             summary="Метрики ML модели",
             description="""Возвращает метрики качества обученной ML модели.
             
    **Пример ответа:**
    ```json
    {
      "accuracy": 0.92,
      "f1_score": 0.89,
      "precision": 0.91,
      "recall": 0.88,
      "metadata": {
        "best_model": "RandomForest",
        "best_f1_score": 0.89,
        "training_date": "2025-12-07",
        "training_samples": 1234
      },
      "class_metrics": {
        "normal": {"precision": 0.95, "recall": 0.92, "f1_score": 0.93},
        "medium": {"precision": 0.88, "recall": 0.85, "f1_score": 0.86},
        "high": {"precision": 0.91, "recall": 0.87, "f1_score": 0.89}
      }
    }
    ```
    """)
    async def ml_metrics():
        deps = get_dependencies()
        return await ml_routes.get_model_metrics(deps['metrics_path'], deps['ml_available'])
    
    @app.get("/ml/model/info", tags=["ML"],
             summary="Информация о ML модели",
             description="""Возвращает информацию о загруженной ML модели.
             
    **Пример ответа (модель загружена):**
    ```json
    {
      "status": "loaded",
      "model_type": "RandomForest",
      "is_loaded": true,
      "model_path": "models/best_model.joblib",
      "features_count": 15,
      "training_date": "2025-12-07",
      "version": "1.0.0"
    }
    ```
    
    **Пример ответа (модель недоступна):**
    ```json
    {
      "status": "unavailable",
      "message": "ML модуль не установлен"
    }
    ```
    """)
    async def ml_info():
        deps = get_dependencies()
        return await ml_routes.get_model_info(deps['ml_classifier'], deps['ml_available'])


# Настройка роутов при старте
setup_routes()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
