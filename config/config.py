"""
IntegrityOS Configuration Module
Centralized settings for backend application
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# MongoDB Connection Settings
MONGODB_URI: Optional[str] = os.getenv("MONGODB_URI", None)
MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "integrity_os")
MONGODB_COLLECTION: str = os.getenv("MONGODB_COLLECTION", "defects")

# Use local storage if MongoDB not available
USE_LOCAL_MODE: bool = os.getenv("USE_LOCAL_MODE", "true").lower() == "true"


API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))


JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

DATA_DIR: str = os.getenv("DATA_DIR", "data")

EXPORT_JSON: bool = os.getenv("EXPORT_JSON", "true").lower() == "true"


APP_TITLE: str = "IntegrityOS Backend API"
APP_VERSION: str = "1.0.0"
APP_DESCRIPTION: str = "Pipeline inspection data processing and visualization backend"

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
