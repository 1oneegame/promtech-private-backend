"""
Admin endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime
import logging

from core import (
    AdminDefectCreateRequest, DefectCreateResponse, DefectCreateDetailsResponse,
    BulkUpdateResponse, Defect, DefectType, SurfaceLocation, SeverityLevel
)
from auth import require_admin
from parsers import CSVParser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin"])


@router.post("/reload", dependencies=[Depends(require_admin)])
async def reload_data(
    current_user: dict = Depends(require_admin),
    defects_repository=None
):
    """Перезагрузить данные из CSV (только для админов)"""
    try:
        defects_repository.clear_all()
        
        parser = CSVParser(data_dir='data')
        defects, errors = parser.parse_all_csv_files()
        
        result = defects_repository.insert_defects(defects)
        
        logger.info(f"[ADMIN] User {current_user['username']} reloaded data")
        
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


@router.delete("/clear", dependencies=[Depends(require_admin)])
async def clear_data(
    current_user: dict = Depends(require_admin),
    defects_repository=None
):
    """Очистить все дефекты из БД (только для админов)"""
    try:
        success = defects_repository.clear_all()
        
        logger.info(f"[ADMIN] User {current_user['username']} cleared all data")
        
        if success:
            return {"status": "success", "message": "All defects cleared"}
        else:
            raise HTTPException(status_code=500, detail="Clear failed")
    except Exception as e:
        logger.error(f"Error creating defect: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/defects/update-all-severities", response_model=BulkUpdateResponse,
             dependencies=[Depends(require_admin)],
             summary="Обновить критичность всех дефектов через ML")
async def update_all_defect_severities(
    current_user: dict = Depends(require_admin),
    defects_repository=None,
    ml_classifier=None,
    ml_available=False
):
    """Обновить severity для всех дефектов без него через ML предсказания"""
    if not ml_available or ml_classifier is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML module is not available"
        )
    
    if not ml_classifier.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML model is not loaded"
        )
    
    try:
        # Получить все дефекты
        all_defects = defects_repository.get_all_defects()
        total_defects = len(all_defects)
        
        updated = 0
        failed = 0
        errors = []
        
        for defect in all_defects:
            try:
                # Пропустить если severity уже есть
                if defect.severity is not None:
                    continue
                
                # Подготовить данные для ML
                ml_input = {
                    "depth_percent": defect.parameters.depth_percent,
                    "depth_mm": defect.parameters.depth_mm,
                    "erf_b31g": defect.erf_b31g_code,
                    "altitude_m": defect.location.altitude if defect.location.altitude else 0.0,
                    "latitude": defect.location.latitude,
                    "longitude": defect.location.longitude,
                    "measurement_distance_m": defect.measurement_distance_m,
                    "length_mm": defect.parameters.length_mm,
                    "width_mm": defect.parameters.width_mm,
                    "wall_thickness_mm": defect.parameters.wall_thickness_nominal_mm,
                    "distance_to_weld_m": defect.distance_to_weld_m,
                    "defect_type": defect.defect_type.value,
                    "surface_location": defect.surface_location.value,
                    "pipeline_id": defect.pipeline_id,
                    "defect_id": defect.defect_id
                }
                
                # Получить предсказание
                prediction = ml_classifier.predict(ml_input)
                predicted_severity = prediction["severity"]
                probability = prediction["probability"]
                
                # Обновить дефект в БД
                success = defects_repository.update_defect_severity(
                    defect.defect_id, 
                    SeverityLevel(predicted_severity), 
                    probability
                )
                
                if success:
                    updated += 1
                    logger.info(f"Updated defect {defect.defect_id} severity to {predicted_severity}")
                else:
                    failed += 1
                    errors.append(f"Failed to update defect {defect.defect_id}")
                    
            except Exception as e:
                failed += 1
                errors.append(f"Defect {defect.defect_id}: {str(e)}")
                logger.error(f"Error updating defect {defect.defect_id}: {str(e)}")
        
        logger.info(f"[ADMIN] User {current_user['username']} updated {updated}/{total_defects} defect severities")
        
        return BulkUpdateResponse(
            total_defects=total_defects,
            updated=updated,
            failed=failed,
            errors=errors[:10]  # Ограничить количество ошибок
        )
        
    except Exception as e:
        logger.error(f"Error in bulk severity update: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/defects", response_model=DefectCreateResponse,
             dependencies=[Depends(require_admin)],
             summary="Создать новый дефект с ML-предсказанием severity",
             status_code=status.HTTP_201_CREATED)
async def create_defect_with_ml_prediction(
    request: AdminDefectCreateRequest,
    current_user: dict = Depends(require_admin),
    defects_repository=None,
    ml_classifier=None,
    ml_available=False
):
    """Создать новый дефект с автоматическим определением критичности через ML"""
    if not ml_available or ml_classifier is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML module is not available"
        )
    
    if not ml_classifier.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML model is not loaded"
        )
    
    # Генерируем UUID если defect_id не передан
    if not request.defect_id:
        import uuid
        request.defect_id = str(uuid.uuid4())
    
    if defects_repository.check_defect_exists(request.defect_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Defect with ID '{request.defect_id}' already exists"
        )
    
    try:
        ml_input = {
            "depth_percent": request.details.parameters.depth_percent,
            "depth_mm": request.details.parameters.depth_mm,
            "erf_b31g": request.details.erf_b31g_code,
            "altitude_m": request.details.location.altitude if request.details.location.altitude else 0.0,
            "latitude": request.details.location.latitude,
            "longitude": request.details.location.longitude,
            "measurement_distance_m": request.measurement_distance_m,
            "length_mm": request.details.parameters.length_mm,
            "width_mm": request.details.parameters.width_mm,
            "wall_thickness_mm": request.details.parameters.wall_thickness_nominal_mm,
            "distance_to_weld_m": request.details.distance_to_weld_m,
            "defect_type": request.details.type,
            "surface_location": request.details.surface_location,
            "pipeline_id": request.pipeline_id,
            "defect_id": request.defect_id
        }
        
        prediction = ml_classifier.predict(ml_input)
        predicted_severity = prediction["severity"]
        probability = prediction["probability"]
        
        defect = Defect(
            defect_id=request.defect_id,
            segment_number=request.segment_number,
            measurement_number=0,
            measurement_distance_m=request.measurement_distance_m,
            defect_type=DefectType(request.details.type),
            parameters=request.details.parameters,
            location=request.details.location,
            surface_location=SurfaceLocation(request.details.surface_location),
            distance_to_weld_m=request.details.distance_to_weld_m,
            erf_b31g_code=request.details.erf_b31g_code,
            pipeline_id=request.pipeline_id,
            severity=SeverityLevel(predicted_severity),
            probability=probability,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        result = defects_repository.insert_single_defect(defect)
        
        if not result["inserted"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to insert defect")
            )
        
        logger.info(f"[ADMIN] User {current_user['username']} created defect {request.defect_id} with severity={predicted_severity} (prob={probability:.2f})")
        
        response = DefectCreateResponse(
            defect_id=defect.defect_id,
            segment_number=defect.segment_number,
            measurement_distance_m=defect.measurement_distance_m,
            pipeline_id=defect.pipeline_id,
            details=DefectCreateDetailsResponse(
                type=request.details.type,
                parameters=request.details.parameters,
                location=request.details.location,
                surface_location=request.details.surface_location,
                distance_to_weld_m=request.details.distance_to_weld_m,
                severity=predicted_severity,
                probability=probability,
                erf_b31g_code=request.details.erf_b31g_code
            )
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid defect data: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error creating defect: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create defect: {str(e)}"
        )



