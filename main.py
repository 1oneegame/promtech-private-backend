"""
IntegrityOS - Main Entry Point
Запуск приложения из корневой директории
"""

import sys
import os

# Добавляем папку src в Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Импортируем и запускаем приложение
if __name__ == "__main__":
    import uvicorn
    from app import app
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
