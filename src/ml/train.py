"""
Обучение моделей классификации критичности дефектов.
"""
import numpy as np
import json
import logging
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    classification_report, confusion_matrix, 
    accuracy_score, f1_score
)
import xgboost as xgb
import joblib
import matplotlib
matplotlib.use('Agg')  # Для работы без GUI
import matplotlib.pyplot as plt

from .config import (
    DATA_PATH, BEST_MODEL_PATH, METRICS_PATH, FEATURE_IMPORTANCE_PLOT,
    RF_PARAMS, XGB_PARAMS, LR_PARAMS, CALIBRATION_METHOD, CV_FOLDS,
    SEVERITY_REVERSE_MAP
)
from .features import load_and_prepare_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelTrainer:
    """Класс для обучения и оценки моделей."""
    
    def __init__(self):
        self.models = {}
        self.best_model = None
        self.best_model_name = None
        self.best_score = 0.0
        self.feature_engineer = None
        self.metrics = {}
        
    def train_all_models(self, X_train, y_train):
        """
        Обучить все модели.
        
        Args:
            X_train: Матрица признаков для обучения
            y_train: Целевые значения
        """
        logger.info("=" * 60)
        logger.info("Начало обучения моделей")
        logger.info("=" * 60)
        
        # 1. Random Forest
        logger.info("\n[1/3] Обучение Random Forest...")
        rf_model = RandomForestClassifier(**RF_PARAMS)
        rf_model.fit(X_train, y_train)
        self.models['RandomForest'] = rf_model
        logger.info("[OK] Random Forest обучен")
        
        # 2. XGBoost
        logger.info("\n[2/3] Обучение XGBoost...")
        xgb_model = xgb.XGBClassifier(**XGB_PARAMS)
        xgb_model.fit(X_train, y_train)
        self.models['XGBoost'] = xgb_model
        logger.info("[OK] XGBoost обучен")
        
        # 3. Logistic Regression
        logger.info("\n[3/3] Обучение Logistic Regression...")
        lr_model = LogisticRegression(**LR_PARAMS)
        lr_model.fit(X_train, y_train)
        self.models['LogisticRegression'] = lr_model
        logger.info("[OK] Logistic Regression обучен")
        
        logger.info("\n" + "=" * 60)
        logger.info("Все модели успешно обучены")
        logger.info("=" * 60)
    
    def calibrate_models(self, X_train, y_train):
        """
        Калибровать вероятности моделей используя isotonic калибровку.
        
        Args:
            X_train: Матрица признаков для калибровки
            y_train: Целевые значения
        """
        logger.info("\n" + "=" * 60)
        logger.info("Начало калибровки моделей (isotonic)")
        logger.info("=" * 60)
        
        calibrated_models = {}
        
        for name, model in self.models.items():
            logger.info(f"\nКалибровка {name}...")
            
            # Для XGBoost калибровка опциональна (уже хорошо калиброван)
            if name == 'XGBoost':
                logger.info(f"  Пропуск калибровки для XGBoost (уже хорошо калиброван)")
                calibrated_models[name] = model
            else:
                calibrated = CalibratedClassifierCV(
                    model,
                    method=CALIBRATION_METHOD,
                    cv=CV_FOLDS
                )
                calibrated.fit(X_train, y_train)
                calibrated_models[name] = calibrated
                logger.info(f"[OK] {name} откалиброван")
        
        self.models = calibrated_models
        logger.info("\n" + "=" * 60)
        logger.info("Калибровка завершена")
        logger.info("=" * 60)
    
    def evaluate_models(self, X_test, y_test):
        """
        Оценить все модели на тестовой выборке.
        
        Args:
            X_test: Матрица признаков для тестирования
            y_test: Истинные значения
        """
        logger.info("\n" + "=" * 60)
        logger.info("Оценка моделей на тестовой выборке")
        logger.info("=" * 60)
        
        results = {}
        
        for name, model in self.models.items():
            logger.info(f"\n{'=' * 40}")
            logger.info(f"Модель: {name}")
            logger.info(f"{'=' * 40}")
            
            # Предсказания
            y_pred = model.predict(X_test)
            y_pred_proba = model.predict_proba(X_test)
            
            # Метрики
            accuracy = accuracy_score(y_test, y_pred)
            f1_weighted = f1_score(y_test, y_pred, average='weighted')
            f1_macro = f1_score(y_test, y_pred, average='macro')
            
            logger.info(f"\nОсновные метрики:")
            logger.info(f"  Accuracy: {accuracy:.4f}")
            logger.info(f"  F1 (weighted): {f1_weighted:.4f}")
            logger.info(f"  F1 (macro): {f1_macro:.4f}")
            
            # Classification report
            target_names = ['normal', 'medium', 'high']
            report = classification_report(
                y_test, y_pred,
                target_names=target_names,
                output_dict=True,
                zero_division=0
            )
            
            logger.info(f"\nClassification Report:")
            logger.info(classification_report(
                y_test, y_pred,
                target_names=target_names,
                zero_division=0
            ))
            
            # Confusion matrix
            cm = confusion_matrix(y_test, y_pred)
            logger.info(f"\nConfusion Matrix:")
            logger.info(f"{cm}")
            
            # Сохранить результаты
            results[name] = {
                'accuracy': float(accuracy),
                'f1_weighted': float(f1_weighted),
                'f1_macro': float(f1_macro),
                'classification_report': report,
                'confusion_matrix': cm.tolist()
            }
            
            # Выбрать лучшую модель по weighted F1
            if f1_weighted > self.best_score:
                self.best_score = f1_weighted
                self.best_model = model
                self.best_model_name = name
        
        self.metrics['models_comparison'] = results
        
        logger.info("\n" + "=" * 60)
        logger.info(f"[BEST] Лучшая модель: {self.best_model_name}")
        logger.info(f"   F1 Score (weighted): {self.best_score:.4f}")
        logger.info("=" * 60)
    
    def plot_feature_importance(self, feature_names):
        """
        Построить график важности признаков для лучшей модели.
        
        Args:
            feature_names: Список имен признаков
        """
        logger.info("\nСоздание графика важности признаков...")
        
        # Получить базовую модель (если откалибрована, достаём из CalibratedClassifierCV)
        model = self.best_model
        if isinstance(model, CalibratedClassifierCV):
            # Берём базовую модель из первого калибратора
            model = model.estimator
        
        # Получить важность признаков
        if self.best_model_name == 'XGBoost' or self.best_model_name == 'RandomForest':
            importances = model.feature_importances_
        else:
            # Для LogisticRegression используем коэффициенты
            if hasattr(model, 'coef_'):
                importances = np.abs(model.coef_).mean(axis=0)
            else:
                logger.warning("Модель не поддерживает feature importance")
                return
        
        # Топ-10 признаков
        indices = np.argsort(importances)[::-1][:10]
        top_features = [feature_names[i] for i in indices]
        top_importances = importances[indices]
        
        # График
        plt.figure(figsize=(10, 6))
        plt.barh(range(len(top_features)), top_importances)
        plt.yticks(range(len(top_features)), top_features)
        plt.xlabel('Важность признака')
        plt.title(f'Топ-10 важных признаков ({self.best_model_name})')
        plt.gca().invert_yaxis()
        plt.tight_layout()
        
        # Сохранить
        plt.savefig(FEATURE_IMPORTANCE_PLOT, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"[OK] График сохранен: {FEATURE_IMPORTANCE_PLOT}")
        
        # Добавить в метрики
        self.metrics['feature_importance'] = {
            'top_10_features': top_features,
            'importances': top_importances.tolist()
        }
    
    def save_best_model(self):
        """Сохранить лучшую модель."""
        logger.info(f"\nСохранение лучшей модели ({self.best_model_name})...")
        joblib.dump(self.best_model, BEST_MODEL_PATH)
        logger.info(f"[OK] Модель сохранена: {BEST_MODEL_PATH}")
    
    def save_metrics(self):
        """Сохранить метрики обучения."""
        logger.info("\nСохранение метрик...")
        
        self.metrics['metadata'] = {
            'best_model': self.best_model_name,
            'best_f1_score': float(self.best_score),
            'training_date': datetime.now().isoformat(),
            'calibration_method': CALIBRATION_METHOD,
            'cv_folds': CV_FOLDS
        }
        
        with open(METRICS_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.metrics, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[OK] Метрики сохранены: {METRICS_PATH}")


def train_pipeline():
    """Полный pipeline обучения."""
    logger.info("\n" + "=" * 60)
    logger.info("НАЧАЛО ОБУЧЕНИЯ ML МОДЕЛИ")
    logger.info("=" * 60)
    
    # 1. Загрузить и подготовить данные
    X_train, X_test, y_train, y_test, feature_engineer = load_and_prepare_data(str(DATA_PATH))
    
    # Проверка и очистка NaN в исходных данных
    logger.info(f"Проверка X_train на NaN: {np.isnan(X_train).sum()} значений")
    logger.info(f"Проверка X_test на NaN: {np.isnan(X_test).sum()} значений")
    X_train = np.nan_to_num(X_train, nan=0.0, posinf=0.0, neginf=0.0)
    X_test = np.nan_to_num(X_test, nan=0.0, posinf=0.0, neginf=0.0)
    logger.info(f"После очистки X_train NaN: {np.isnan(X_train).sum()}")
    
    # 1.1 Добавить шум для борьбы с переобучением
    from .features import add_noise_to_data
    X_train_aug, y_train_aug = add_noise_to_data(
        X_train, y_train, 
        noise_level=0.25,  # 25% шум
        augmentation_factor=5,  # Увеличить в 5 раз
        feature_dropout=0.15  # 15% вероятность обнулить признак
    )
    
    logger.info(f"После аугментации X_train_aug NaN: {np.isnan(X_train_aug).sum()}")
    
    # Сохранить feature engineer
    feature_engineer.save()
    
    # 2. Обучить модели
    trainer = ModelTrainer()
    trainer.train_all_models(X_train_aug, y_train_aug)
    
    # 3. Калибровать модели (на оригинальных данных без шума)
    trainer.calibrate_models(X_train, y_train)
    
    # 4. Оценить модели
    trainer.evaluate_models(X_test, y_test)
    
    # 5. График важности признаков
    trainer.plot_feature_importance(feature_engineer.feature_names)
    
    # 6. Сохранить лучшую модель и метрики
    trainer.save_best_model()
    trainer.save_metrics()
    
    logger.info("\n" + "=" * 60)
    logger.info("[SUCCESS] ОБУЧЕНИЕ УСПЕШНО ЗАВЕРШЕНО")
    logger.info("=" * 60)
    logger.info(f"\nЛучшая модель: {trainer.best_model_name}")
    logger.info(f"F1 Score: {trainer.best_score:.4f}")
    logger.info(f"\nФайлы:")
    logger.info(f"  Модель: {BEST_MODEL_PATH}")
    logger.info(f"  Метрики: {METRICS_PATH}")
    logger.info(f"  График: {FEATURE_IMPORTANCE_PLOT}")
    
    return trainer


if __name__ == "__main__":
    train_pipeline()
