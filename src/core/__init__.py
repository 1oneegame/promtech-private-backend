"""
Core module
Database, models, and core business logic
"""

from .models import (
    Defect, DefectType, DefectParameters, Location, SurfaceLocation,
    SeverityLevel, QualityGrade, Pipeline, PipelineObject,
    DefectResponse, DefectDetailsResponse, DefectListResponse,
    StatisticsResponse, LoginRequest, TokenResponse, UserInfo,
    AdminDefectCreateRequest, DefectCreateResponse, DefectCreateDetailsResponse,
    BulkUpdateResponse, AdminUser
)
from .database import MongoDBConnection, DefectsRepository, PipelinesRepository, AdminUsersRepository

__all__ = [
    # Models
    'Defect', 'DefectType', 'DefectParameters', 'Location', 'SurfaceLocation',
    'SeverityLevel', 'QualityGrade', 'Pipeline', 'PipelineObject',
    'DefectResponse', 'DefectDetailsResponse', 'DefectListResponse',
    'StatisticsResponse', 'LoginRequest', 'TokenResponse', 'UserInfo',
    'AdminDefectCreateRequest', 'DefectCreateResponse', 'DefectCreateDetailsResponse',
    'BulkUpdateResponse', 'AdminUser',
    # Database
    'MongoDBConnection', 'DefectsRepository', 'PipelinesRepository', 'AdminUsersRepository'
]
