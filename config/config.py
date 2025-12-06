"""
IntegrityOS Configuration Module
Centralized settings for backend application
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

# MongoDB Connection Settings
MONGODB_URI: Optional[str] = os.getenv("MONGODB_URI", None)
MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "integrity_os")
MONGODB_COLLECTION: str = os.getenv("MONGODB_COLLECTION", "defects")

# Use local storage if MongoDB not available
USE_LOCAL_MODE: bool = os.getenv("USE_LOCAL_MODE", "true").lower() == "true"

# ============================================================================
# API CONFIGURATION
# ============================================================================

API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
API_RELOAD: bool = os.getenv("API_RELOAD", "true").lower() == "true"
API_WORKERS: int = int(os.getenv("API_WORKERS", "1"))

# ============================================================================
# DATA IMPORT CONFIGURATION
# ============================================================================

DATA_DIR: str = os.getenv("DATA_DIR", "data")
CSV_ENCODING: str = os.getenv("CSV_ENCODING", "utf-8-sig")
SUPPORTED_ENCODINGS: list = ["utf-8-sig", "utf-8", "cp1251", "latin-1", "iso-8859-5"]

# ============================================================================
# EXPORT CONFIGURATION
# ============================================================================

EXPORT_DIR: str = os.getenv("EXPORT_DIR", ".")
EXPORT_JSON: bool = os.getenv("EXPORT_JSON", "true").lower() == "true"
JSON_ENSURE_ASCII: bool = os.getenv("JSON_ENSURE_ASCII", "false").lower() == "true"

# ============================================================================
# APPLICATION CONFIGURATION
# ============================================================================

APP_TITLE: str = "IntegrityOS Backend API"
APP_VERSION: str = "1.0.0"
APP_DESCRIPTION: str = "Pipeline inspection data processing and visualization backend"

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = os.getenv("LOG_FILE", "app.log")
LOG_FORMAT: str = "[%(asctime)s] %(levelname)s - %(name)s - %(message)s"

# ============================================================================
# GEOGRAPHIC BOUNDS (Kazakhstan)
# ============================================================================

GPS_LATITUDE_MIN: float = 40.0
GPS_LATITUDE_MAX: float = 50.0
GPS_LONGITUDE_MIN: float = 50.0
GPS_LONGITUDE_MAX: float = 70.0

print(f"""
╔════════════════════════════════════════════════════════════════════════╗
║                    IntegrityOS Configuration Loaded                    ║
╠════════════════════════════════════════════════════════════════════════╣
║ Database Mode: {'MongoDB' if MONGODB_URI else 'Local (In-Memory)':<42} ║
║ API Endpoint: {API_HOST}:{API_PORT:<48} ║
║ Data Directory: {DATA_DIR:<55} ║
║ Export JSON: {'Enabled' if EXPORT_JSON else 'Disabled':<52} ║
╚════════════════════════════════════════════════════════════════════════╝
""")
