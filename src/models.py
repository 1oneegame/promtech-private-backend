"""
IntegrityOS Data Models
Модели данных для трубопроводов, объектов контроля и дефектов
"""

from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class DefectType(str, Enum):
    """Типы дефектов"""
    # Коррозия
    CORROSION = "коррозия"
    PITTING_CORROSION = "питтинг-коррозия"
    EXTERNAL_CORROSION = "внешняя коррозия"
    INTERNAL_CORROSION = "внутренняя коррозия"
    
    # Сварные швы
    WELD_SEAM = "сварной шов"
    WELD_CRACK = "трещина на шве"
    WELD_POROSITY = "пористость шва"
    LACK_OF_FUSION = "недоплав"
    
    # Механические повреждения
    DENT = "вмятина"
    GOUGE = "канавка/борозда"
    SCRATCH = "царапина"
    ABRASION = "истирание"
    
    # Деформации
    BUCKLE = "гофра/волна"
    OVALITY = "овальность"
    BEND = "изгиб"
    
    # Трещины и расслоение
    CRACK = "трещина"
    LAMINATION = "расслоение"
    SCC = "коррозионное растрескивание под напряжением"
    
    # Эрозия и включения
    EROSION = "эрозия"
    INCLUSION = "включение"
    OXIDE = "оксидное включение"
    
    # Инородные объекты
    METAL_OBJECT = "металлический объект"
    FOREIGN_OBJECT = "инородный объект"
    
    # Прочее
    OTHER = "другое"


class SurfaceLocation(str, Enum):
    """Локация дефекта на поверхности трубы"""
    EXTERNAL_TOP = "ВНТ"  # внешняя верхняя
    EXTERNAL_BOTTOM = "ВНШ"  # внешняя нижняя
    INTERNAL_TOP = "ВНТ_ВНУТРИ"
    INTERNAL_BOTTOM = "ВНШ_ВНУТРИ"
    OTHER = "другое"


class SeverityLevel(str, Enum):
    """Уровень критичности дефекта"""
    NORMAL = "normal"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class QualityGrade(str, Enum):
    """Оценка качества по результатам диагностики"""
    SATISFACTORY = "удовлетворительно"
    ACCEPTABLE = "допустимо"
    REQUIRES_MEASURES = "требует_мер"
    UNACCEPTABLE = "недопустимо"


class Location(BaseModel):
    """GPS координаты"""
    latitude: float = Field(..., description="Широта [°]")
    longitude: float = Field(..., description="Долгота [°]")
    altitude: Optional[float] = Field(None, description="Высота [м]")

    class Config:
        json_schema_extra = {
            "example": {
                "latitude": 48.476357,
                "longitude": 57.660536,
                "altitude": 264.8
            }
        }


class DefectParameters(BaseModel):
    """Параметры дефекта"""
    length_mm: Optional[float] = Field(None, description="Длина [мм]")
    width_mm: Optional[float] = Field(None, description="Ширина [мм]")
    depth_mm: Optional[float] = Field(None, description="Глубина абсолютная [мм]")
    depth_percent: float = Field(..., description="Глубина относительная [%]")
    wall_thickness_nominal_mm: Optional[float] = Field(None, description="Толщина стенки номинальная [мм]")

    class Config:
        json_schema_extra = {
            "example": {
                "length_mm": 16.0,
                "width_mm": 15.0,
                "depth_mm": 6.0,
                "depth_percent": 0.54,
                "wall_thickness_nominal_mm": 7.9
            }
        }


class Defect(BaseModel):
    """Модель дефекта/аномалии в трубопроводе"""
    defect_id: Optional[str] = Field(None, description="MongoDB ObjectId")
    segment_number: int = Field(..., description="Номер сегмента/участка трубы")
    measurement_number: int = Field(..., description="Номер замера")
    measurement_distance_m: float = Field(..., description="Расстояние измерения [м]")
    
    # Тип и тип дефекта
    defect_type: DefectType = Field(..., description="Тип дефекта")
    
    # Параметры
    parameters: DefectParameters = Field(..., description="Параметры дефекта")
    
    # Локация
    location: Location = Field(..., description="GPS координаты")
    surface_location: SurfaceLocation = Field(..., description="Локация на поверхности трубы")
    distance_to_weld_m: Optional[float] = Field(None, description="Расстояние до шва [м]")
    erf_b31g_code: Optional[float] = Field(None, description="ERF B31G коэффициент")
    
    # Стандарты и оценки
    quality_grade: Optional[QualityGrade] = Field(None, description="Оценка качества")
    
    # Метаданные
    pipeline_id: Optional[str] = Field(None, description="ID трубопровода")
    inspection_date: Optional[datetime] = Field(None, description="Дата проведения инспекции")
    inspection_method: Optional[str] = Field(None, description="Метод контроля (VIK, PVK, MFL и т.п.)")
    
    # Критичность (severity classification)
    severity: Optional[SeverityLevel] = Field(None, description="Уровень критичности (normal/medium/high/critical)")
    severity_probability: Optional[float] = Field(None, description="Вероятность классификации критичности (0-1)")
    
    # AI классификация
    ml_probability: Optional[float] = Field(None, description="Вероятность предсказания (0-1)")
    
    # Источник данных
    source_file: Optional[str] = Field(None, description="Исходный файл")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Дата создания записи")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Дата обновления записи")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "segment_number": 3,
                "measurement_number": 7,
                "measurement_distance_m": 5.125,
                "defect_type": "коррозия",
                "severity": "medium",
                "parameters": {
                    "length_mm": 16.0,
                    "width_mm": 15.0,
                    "depth_mm": 6.0,
                    "depth_percent": 0.54,
                    "wall_thickness_nominal_mm": 7.9
                },
                "location": {
                    "latitude": 48.477933,
                    "longitude": 57.663105,
                    "altitude": 264.9
                },
                "surface_location": "ВНШ"
            }
        }


class Pipeline(BaseModel):
    """Модель магистрального трубопровода"""
    pipeline_id: Optional[str] = Field(None, description="MongoDB ObjectId")
    pipeline_name: str = Field(..., description="Наименование трубопровода")
    pipeline_code: str = Field(..., description="Условный код (MT-01, MT-02 и т.п.)")
    
    # Параметры трубы
    diameter_mm: Optional[float] = Field(None, description="Диаметр трубы [мм]")
    wall_thickness_mm: Optional[float] = Field(None, description="Толщина стенки [мм]")
    material: Optional[str] = Field(None, description="Материал (Ст3, 09Г2С и т.п.)")
    construction_year: Optional[int] = Field(None, description="Год ввода в эксплуатацию")
    
    # География
    start_location: Optional[Location] = Field(None, description="Начальная точка")
    end_location: Optional[Location] = Field(None, description="Конечная точка")
    length_km: Optional[float] = Field(None, description="Длина участка [км]")
    
    # Статус
    is_active: bool = Field(default=True, description="Активный ли участок")
    
    # Метаданные
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PipelineObject(BaseModel):
    """Модель объекта контроля на трубопроводе"""
    object_id: Optional[str] = Field(None, description="MongoDB ObjectId")
    object_name: str = Field(..., description="Наименование объекта")
    object_type: str = Field(..., description="Тип объекта (crane, compressor, pipeline_section)")
    
    # Привязка
    pipeline_id: str = Field(..., description="ID трубопровода")
    
    # География
    location: Location = Field(..., description="GPS координаты")
    
    # Параметры
    year_manufactured: Optional[int] = Field(None, description="Год выпуска")
    material: Optional[str] = Field(None, description="Материал")
    
    # Статистика
    total_defects: int = Field(default=0, description="Количество найденных дефектов")
    critical_defects: int = Field(default=0, description="Количество критических дефектов")
    
    # Метаданные
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Pydantic модели для API responses

class DefectDetailsResponse(BaseModel):
    """Детальные параметры дефекта для API"""
    type: DefectType = Field(..., description="Тип дефекта")
    parameters: DefectParameters = Field(..., description="Физические параметры")
    location: Location = Field(..., description="GPS координаты")
    surface_location: SurfaceLocation = Field(..., description="Локация на поверхности")
    distance_to_weld_m: Optional[float] = Field(None, description="Расстояние до шва [м]")
    erf_b31g_code: Optional[float] = Field(None, description="ERF B31G коэффициент")


class DefectResponse(BaseModel):
    """Оптимизированный Response модель для дефекта"""
    defect_id: str = Field(..., description="Уникальный ID дефекта")
    segment_number: int = Field(..., description="Номер сегмента")
    measurement_distance_m: float = Field(..., description="Расстояние измерения [м]")
    pipeline_id: str = Field(..., description="ID трубопровода")
    details: DefectDetailsResponse = Field(..., description="Детальные параметры")


class DefectListResponse(BaseModel):
    """Response для списка дефектов"""
    total: int = Field(..., description="Общее количество дефектов")
    defects: List[DefectResponse] = Field(..., description="Список дефектов")
    filters_applied: Optional[Dict[str, Any]] = None


class StatisticsResponse(BaseModel):
    """Response для статистики"""
    total_defects: int
    defects_by_type: Dict[str, int]
    defects_by_location: Dict[str, int]
    average_depth_percent: float
    critical_defects_count: int

    class Config:
        json_schema_extra = {
            "example": {
                "total_defects": 6,
                "defects_by_type": {
                    "коррозия": 5,
                    "сварной шов": 1
                },
                "defects_by_severity": {
                    "normal": 2,
                    "medium": 3,
                    "high": 1
                },
                "defects_by_location": {
                    "ВНШ": 5,
                    "ВНТ": 1
                },
                "average_depth_percent": 0.51,
                "critical_defects_count": 1
            }
        }
