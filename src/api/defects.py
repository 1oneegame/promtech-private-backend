"""
Defects CRUD endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging

from core import DefectType, DefectListResponse, DefectResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/defects", tags=["Defects"])


def defect_to_response(defect):
    """Преобразует Defect в DefectResponse"""
    from core import DefectDetailsResponse, DefectResponse
    
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


@router.get("", response_model=DefectListResponse)
async def get_defects(
    defect_type: Optional[str] = Query(None, description="Тип дефекта"),
    segment: Optional[int] = Query(None, description="Номер сегмента"),
    defects_repository=None
):
    """
    Получить дефекты с опциональной фильтрацией
    
    Параметры:
    - defect_type: коррозия, сварной шов, металлический объект
    - segment: номер сегмента трубопровода
    """
    try:
        if defect_type:
            defects = defects_repository.get_defects_by_type(defect_type)
        elif segment:
            defects = defects_repository.get_defects_by_segment(segment)
        else:
            defects = defects_repository.get_all_defects()
        
        if defect_type and segment:
            defects = [d for d in defects if d.segment_number == segment]
        
        total = len(defects)
        response_defects = [defect_to_response(d) for d in defects]
        
        return DefectListResponse(
            total=total,
            defects=response_defects,
            filters_applied={"defect_type": defect_type, "segment": segment}
        )
    
    except Exception as e:
        logger.error(f"Error getting defects: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=DefectListResponse)
async def search_defects(
    defect_type: Optional[str] = None,
    segment: Optional[int] = None,
    defects_repository=None
):
    """Получить дефекты с применением множественных фильтров"""
    try:
        all_defects = defects_repository.get_all_defects()
        filtered_defects = all_defects
        
        if defect_type:
            filtered_defects = [d for d in filtered_defects if d.defect_type.value == defect_type]
        
        if segment is not None:
            filtered_defects = [d for d in filtered_defects if d.segment_number == segment]
        
        response_defects = [defect_to_response(d) for d in filtered_defects]
        return DefectListResponse(
            total=len(filtered_defects),
            defects=response_defects,
            filters_applied={"defect_type": defect_type, "segment": segment}
        )
    except Exception as e:
        logger.error(f"Error searching defects: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{defect_id}", response_model=DefectResponse)
async def get_defect(defect_id: str, defects_repository=None):
    """Получить дефект по ID"""
    try:
        defects = defects_repository.get_all_defects()
        for defect in defects:
            if str(defect.defect_id or "") == defect_id:
                return defect_to_response(defect)
        raise HTTPException(status_code=404, detail="Defect not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting defect: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/type/{defect_type}", response_model=DefectListResponse)
async def get_defects_by_type(defect_type: str, defects_repository=None):
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


@router.get("/segment/{segment_id}", response_model=DefectListResponse)
async def get_defects_by_segment(segment_id: int, defects_repository=None):
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
