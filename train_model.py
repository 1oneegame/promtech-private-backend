"""
Скрипт для обучения ML модели классификации критичности дефектов.
Запустите: python train_model.py
"""

import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ml.train import train_pipeline

if __name__ == "__main__":
    print("\n" + "="*80)
    print("ОБУЧЕНИЕ ML МОДЕЛИ ДЛЯ КЛАССИФИКАЦИИ КРИТИЧНОСТИ ДЕФЕКТОВ")
    print("="*80 + "\n")
    
    try:
        trainer = train_pipeline()
        print("\n" + "="*80)
        print("[SUCCESS] УСПЕШНО! Модель обучена и сохранена.")
        print("="*80)
        print("\nТеперь вы можете:")
        print("  1. Запустить API: python main.py")
        print("  2. Использовать endpoint: POST /ml/predict")
        print("  3. Посмотреть метрики: GET /ml/model/metrics")
        print("  4. График важности признаков: models/feature_importance.png")
        
    except Exception as e:
        print(f"\n[ERROR] ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
