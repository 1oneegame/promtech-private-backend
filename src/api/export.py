"""
Export endpoints
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import tempfile
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/json")
async def export_to_json(defects_repository=None):
    """Экспортировать дефекты в JSON файл для скачивания"""
    try:
        from .defects import defect_to_response
        
        defects = defects_repository.get_all_defects()
        if not defects:
            raise HTTPException(status_code=404, detail="No defects found")
        
        response_defects = [defect_to_response(d) for d in defects]
        defects_dict = [defect.model_dump() for defect in response_defects]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(defects_dict, temp_file, ensure_ascii=False, indent=2)
            temp_filename = temp_file.name
        
        return FileResponse(
            path=temp_filename,
            filename="defects_export.json",
            media_type='application/json',
            background=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting to JSON: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
