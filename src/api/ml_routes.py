"""
Machine Learning endpoints
"""

from fastapi import APIRouter, HTTPException
from typing import Union, Dict, Optional
from pydantic import BaseModel, Field
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["ML"])


class DefectParameters(BaseModel):
    """Параметры дефекта"""
    length_mm: Optional[float] = Field(None, description="Длина дефекта (мм)")
    width_mm: Optional[float] = Field(None, description="Ширина дефекта (мм)")
    depth_mm: Optional[float] = Field(None, description="Глубина дефекта (мм)")
    depth_percent: float = Field(..., description="Глубина дефекта в %", ge=0, le=100)
    wall_thickness_mm: Optional[float] = Field(None, description="Толщина стенки (мм)", alias="wall_thickness_nominal_mm")
    
    class Config:
        populate_by_name = True  # Позволяет использовать оба имени поля


class DefectLocation(BaseModel):
    """Местоположение дефекта"""
    latitude: float = Field(..., description="Широта", ge=-90, le=90)
    longitude: float = Field(..., description="Долгота", ge=-180, le=180)
    altitude: float = Field(..., description="Высота (м)")


class DefectDetails(BaseModel):
    """Детальная информация о дефекте"""
    type: str = Field(..., description="Тип дефекта")
    parameters: DefectParameters
    location: DefectLocation
    surface_location: str = Field(..., description="Расположение (ВНШ/ВНТ)")
    distance_to_weld_m: Optional[float] = Field(None, description="Расстояние до сварного шва (м)")
    erf_b31g_code: float = Field(..., description="Коэффициент ERF B31G", ge=0, le=1)


class MLPredictionRequestNested(BaseModel):
    """Запрос для предсказания (вложенная структура)"""
    defect_id: Optional[str] = None
    segment_number: Optional[int] = None
    measurement_distance_m: float = Field(..., ge=0)
    pipeline_id: Optional[str] = None
    details: DefectDetails


class MLPredictionRequest(BaseModel):
    """Запрос для предсказания (плоская структура)"""
    defect_id: Optional[str] = None
    segment_number: Optional[int] = None
    depth_percent: float = Field(..., ge=0, le=100)
    depth_mm: Optional[float] = None
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    wall_thickness_mm: Optional[float] = None
    distance_to_weld_m: Optional[float] = None
    erf_b31g: float = Field(..., ge=0, le=1)
    altitude_m: float
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    measurement_distance_m: float = Field(..., ge=0)
    pipeline_id: Optional[str] = None
    defect_type: str
    surface_location: str


class MLPredictionResponse(BaseModel):
    """Ответ с предсказанием критичности"""
    severity: str
    probability: float
    probabilities: Dict[str, float]
    model_type: str
    prediction_timestamp: str


def convert_nested_to_flat(nested_request: MLPredictionRequestNested) -> dict:
    """Конвертация вложенной структуры в плоскую"""
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


@router.post("/predict", response_model=MLPredictionResponse,
             summary="Предсказание критичности дефекта")
async def predict_defect_criticality(
    request: Union[MLPredictionRequest, MLPredictionRequestNested],
    ml_classifier=None,
    ml_available=False
):
    """Предсказать критичность дефекта используя ML модель"""
    if not ml_available:
        raise HTTPException(
            status_code=503,
            detail="ML модуль недоступен"
        )
    
    if ml_classifier is None or not ml_classifier.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="ML модель не загружена"
        )
    
    try:
        if isinstance(request, MLPredictionRequestNested):
            sample = convert_nested_to_flat(request)
        else:
            sample = request.dict()
        
        result = ml_classifier.predict(sample)
        
        return MLPredictionResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Ошибка в данных: {str(e)}")
    except Exception as e:
        logger.error(f"ML prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка предсказания: {str(e)}")


@router.get("/model/metrics",
            summary="Метрики обученной ML модели")
async def get_model_metrics(metrics_path=None, ml_available=False):
    """Получить метрики обученной модели"""
    if not ml_available:
        raise HTTPException(status_code=503, detail="ML модуль недоступен")
    
    try:
        if not metrics_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Метрики не найдены. Запустите: python -m src.ml.train"
            )
        
        with open(metrics_path, 'r', encoding='utf-8') as f:
            metrics = json.load(f)
        
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model/info",
            summary="Информация о ML модели")
async def get_model_info(ml_classifier=None, ml_available=False):
    """Получить информацию о загруженной ML модели"""
    if not ml_available:
        return {"status": "unavailable", "message": "ML модуль не установлен"}
    
    if ml_classifier is None:
        return {"status": "not_initialized", "message": "ML классификатор не инициализирован"}
    
    try:
        info = ml_classifier.get_model_info()
        return info
    except Exception as e:
        logger.error(f"Error getting model info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
