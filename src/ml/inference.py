"""
Inference сервис для предсказания критичности дефектов.
"""
import numpy as np
import joblib
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from .config import (
    BEST_MODEL_PATH, METRICS_PATH,
    SEVERITY_REVERSE_MAP, MODELS_DIR
)
from .features import FeatureEngineer, prepare_single_sample

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DefectClassifier:
    """Класс для предсказания критичности дефектов."""
    
    def __init__(self):
        self.model = None
        self.feature_engineer = None
        self.metadata = None
        self.is_loaded = False
        
    def load(self):
        """Загрузить модель и компоненты. Если модель отсутствует, автоматически запустить обучение."""
        if self.is_loaded:
            logger.info("Модель уже загружена")
            return
        
        logger.info("Загрузка ML модели...")
        
        # Проверить наличие файлов
        if not BEST_MODEL_PATH.exists():
            logger.warning(f"Модель не найдена: {BEST_MODEL_PATH}")
            logger.info("Запуск автоматического обучения модели...")
            
            try:
                # Импортировать и запустить обучение
                from .train import train_pipeline
                trainer = train_pipeline()
                logger.info("[SUCCESS] Автоматическое обучение завершено успешно!")
            except Exception as e:
                raise RuntimeError(f"Не удалось автоматически обучить модель: {e}")
        
        # Загрузить модель
        self.model = joblib.load(BEST_MODEL_PATH)
        logger.info(f"[OK] Модель загружена: {BEST_MODEL_PATH}")
        
        # Загрузить feature engineer
        self.feature_engineer = FeatureEngineer.load()
        
        # Загрузить метаданные
        if METRICS_PATH.exists():
            with open(METRICS_PATH, 'r', encoding='utf-8') as f:
                metrics = json.load(f)
                self.metadata = metrics.get('metadata', {})
            logger.info(f"[OK] Метаданные загружены")
            logger.info(f"  Модель: {self.metadata.get('best_model', 'Unknown')}")
            logger.info(f"  F1 Score: {self.metadata.get('best_f1_score', 'Unknown')}")
            logger.info(f"  Дата обучения: {self.metadata.get('training_date', 'Unknown')}")
        
        self.is_loaded = True
        logger.info("[READY] ML модель готова к работе")
    
    def predict(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """
        Предсказать критичность для одного дефекта.
        
        Args:
            sample: Словарь с параметрами дефекта
                Обязательные поля:
                - depth_percent: float
                - erf_b31g: float
                - altitude_m: float
                - latitude: float
                - longitude: float
                - measurement_distance_m: float
                - pipeline_id: str
                - defect_type: str
                - surface_location: str (ВНШ или ВНТ)
        
        Returns:
            Словарь с предсказанием:
            {
                "severity": "medium",
                "probability": 0.73,
                "probabilities": {
                    "normal": 0.15,
                    "medium": 0.73,
                    "high": 0.12
                },
                "model_type": "XGBoost",
                "prediction_timestamp": "2025-12-06T12:30:45"
            }
        """
        if not self.is_loaded:
            raise RuntimeError("Модель не загружена. Вызовите load() сначала.")
        
        # Подготовить признаки
        try:
            X = prepare_single_sample(sample, self.feature_engineer)
        except Exception as e:
            logger.error(f"Ошибка подготовки признаков: {e}")
            raise ValueError(f"Неверный формат входных данных: {e}")
        
        # Предсказание класса
        y_pred = self.model.predict(X)[0]
        severity = SEVERITY_REVERSE_MAP[y_pred]
        
        # Предсказание вероятностей
        y_pred_proba = self.model.predict_proba(X)[0]
        probabilities = {
            "normal": float(y_pred_proba[0]),
            "medium": float(y_pred_proba[1]),
            "high": float(y_pred_proba[2])
        }
        
        # Основная вероятность
        probability = probabilities[severity]
        
        result = {
            "severity": severity,
            "probability": probability,
            "probabilities": probabilities,
            "model_type": self.metadata.get('best_model', 'Unknown') if self.metadata else 'Unknown',
            "prediction_timestamp": datetime.now().isoformat()
        }
        
        return result
    
    def predict_batch(self, samples: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """
        Предсказать критичность для нескольких дефектов.
        
        Args:
            samples: Список словарей с параметрами дефектов
        
        Returns:
            Список предсказаний
        """
        return [self.predict(sample) for sample in samples]
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Получить информацию о загруженной модели.
        
        Returns:
            Словарь с информацией о модели
        """
        if not self.is_loaded:
            return {"status": "not_loaded", "message": "Модель не загружена"}
        
        info = {
            "status": "loaded",
            "model_type": self.metadata.get('best_model', 'Unknown') if self.metadata else 'Unknown',
            "f1_score": self.metadata.get('best_f1_score', None) if self.metadata else None,
            "training_date": self.metadata.get('training_date', None) if self.metadata else None,
            "calibration_method": self.metadata.get('calibration_method', None) if self.metadata else None,
            "model_path": str(BEST_MODEL_PATH),
            "feature_count": len(self.feature_engineer.feature_names) if self.feature_engineer else None
        }
        
        return info


# Singleton instance
_classifier_instance: Optional[DefectClassifier] = None


def get_classifier() -> DefectClassifier:
    """
    Получить singleton instance классификатора.
    Автоматически загружает модель при первом вызове.
    
    Returns:
        DefectClassifier instance
    """
    global _classifier_instance
    
    if _classifier_instance is None:
        _classifier_instance = DefectClassifier()
        try:
            _classifier_instance.load()
        except Exception as e:
            logger.error(f"Не удалось загрузить модель: {e}")
            # Не падаем, возвращаем instance без загруженной модели
            # API endpoint сможет вернуть информативную ошибку
    
    return _classifier_instance


def predict_defect(sample: Dict[str, Any]) -> Dict[str, Any]:
    """
    Удобная функция для предсказания критичности дефекта.
    
    Args:
        sample: Словарь с параметрами дефекта
    
    Returns:
        Предсказание
    """
    classifier = get_classifier()
    return classifier.predict(sample)


if __name__ == "__main__":
    # Тестовый запуск
    classifier = DefectClassifier()
    classifier.load()
    
    # Тестовый пример
    test_sample = {
        "depth_percent": 15.5,
        "erf_b31g": 0.85,
        "altitude_m": 50.0,
        "latitude": 46.5,
        "longitude": 52.0,
        "measurement_distance_m": 100000.0,
        "pipeline_id": "CPC-KZ",
        "defect_type": "коррозия",
        "surface_location": "ВНШ"
    }
    
    result = classifier.predict(test_sample)
    print("\n" + "=" * 60)
    print("ТЕСТОВОЕ ПРЕДСКАЗАНИЕ")
    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))
