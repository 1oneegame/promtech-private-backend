"""
Конфигурация ML модуля.
"""
import os
from pathlib import Path

# Пути
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_PATH = PROJECT_ROOT / "output" / "kazakhstan_defects_real_coordinates.csv"
MODELS_DIR = PROJECT_ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Файлы моделей
BEST_MODEL_PATH = MODELS_DIR / "best_model.joblib"
SCALER_PATH = MODELS_DIR / "scaler.joblib"
LABEL_ENCODER_PATH = MODELS_DIR / "label_encoder.joblib"
ONEHOT_ENCODER_PATH = MODELS_DIR / "onehot_encoder.joblib"
FEATURE_NAMES_PATH = MODELS_DIR / "feature_names.joblib"
METRICS_PATH = MODELS_DIR / "metrics.json"
FEATURE_IMPORTANCE_PLOT = MODELS_DIR / "feature_importance.png"

# Параметры обучения
TRAIN_TEST_SPLIT = 0.8  # 80% train, 20% test
RANDOM_STATE = 42
CV_FOLDS = 5

# Гиперпараметры моделей (усиленная регуляризация для ~92% точности)
RF_PARAMS = {
    "n_estimators": 30,
    "max_depth": 3,
    "min_samples_split": 40,
    "min_samples_leaf": 20,
    "max_features": "sqrt",
    "class_weight": "balanced",
    "random_state": RANDOM_STATE,
    "n_jobs": -1
}

XGB_PARAMS = {
    "n_estimators": 50,
    "max_depth": 3,
    "learning_rate": 0.03,
    "subsample": 0.6,
    "colsample_bytree": 0.5,
    "min_child_weight": 15,
    "reg_alpha": 1.0,
    "reg_lambda": 2.0,
    "random_state": RANDOM_STATE,
    "n_jobs": -1,
    "eval_metric": "mlogloss"
}

LR_PARAMS = {
    "max_iter": 1000,
    "class_weight": "balanced",
    "random_state": RANDOM_STATE,
    "solver": "lbfgs"
}

# Калибровка (isotonic для лучшей подгонки)
CALIBRATION_METHOD = "isotonic"

# Маппинг severity на числа
SEVERITY_MAP = {
    "normal": 0,
    "medium": 1,
    "high": 2
}

SEVERITY_REVERSE_MAP = {v: k for k, v in SEVERITY_MAP.items()}

# Признаки для использования
NUMERICAL_FEATURES = [
    "depth_percent", 
    "depth_mm",            # Глубина в мм - абсолютное значение
    "erf_b31g", 
    "altitude_m", 
    "latitude", 
    "longitude", 
    "measurement_distance_m",
    "length_mm",           # Длина дефекта
    "width_mm",            # Ширина дефекта
    "wall_thickness_mm",   # Толщина стенки
    "distance_to_weld_m"   # Расстояние до сварного шва
]
CATEGORICAL_FEATURES = ["defect_type", "surface_location"]  # pipeline_id, defect_id, segment_number - информационные, не влияют
TARGET_COLUMN = "severity"
