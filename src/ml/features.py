"""
Feature engineering pipeline для подготовки данных.
"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder, OneHotEncoder
from sklearn.model_selection import train_test_split
import joblib
from typing import Tuple, Dict, Any
import logging

from .config import (
    NUMERICAL_FEATURES, CATEGORICAL_FEATURES, TARGET_COLUMN,
    SEVERITY_MAP, TRAIN_TEST_SPLIT, RANDOM_STATE,
    SCALER_PATH, LABEL_ENCODER_PATH, ONEHOT_ENCODER_PATH, FEATURE_NAMES_PATH,
    MODELS_DIR
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Класс для обработки признаков."""
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.defect_type_encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
        self.feature_names = []
        self.medians = {}  # Словарь медиан для опциональных признаков
        
    def fit(self, df: pd.DataFrame) -> 'FeatureEngineer':
        """
        Обучить все энкодеры и скейлеры на тренировочных данных.
        Также вычисляет медианы для опциональных параметров.
        
        Args:
            df: DataFrame с данными
            
        Returns:
            self
        """
        logger.info("Обучение feature engineering pipeline...")
        
        # Убрать пробелы из текстовых колонок
        df['defect_type'] = df['defect_type'].str.strip()
        df['surface_location'] = df['surface_location'].str.strip()
        
        # Вычислить медианы для опциональных признаков
        optional_features = ['length_mm', 'width_mm', 'wall_thickness_mm', 'depth_mm', 'distance_to_weld_m']
        for feature in optional_features:
            if feature in df.columns:
                # Вычислить медиану только по непустым значениям
                median_value = df[feature].dropna().median()
                self.medians[feature] = median_value if not pd.isna(median_value) else 0.0
                logger.info(f"  Медиана для {feature}: {self.medians[feature]:.2f}")
        
        # Обучить OneHotEncoder для defect_type
        self.defect_type_encoder.fit(df[['defect_type']])
        
        # Подготовить данные для обучения скейлера
        X_temp = self._transform_features(df, fit_scaler=True)
        
        logger.info(f"Feature engineering обучен. Размерность признаков: {X_temp.shape[1]}")
        return self
    
    def _transform_features(self, df: pd.DataFrame, fit_scaler: bool = False) -> np.ndarray:
        """
        Трансформировать признаки.
        
        Args:
            df: DataFrame с данными
            fit_scaler: Обучать ли скейлер (только для train данных)
            
        Returns:
            Матрица признаков
        """
        features = []
        feature_names = []
        
        # 1. Числовые признаки
        numerical_data = df[NUMERICAL_FEATURES].values
        if fit_scaler:
            numerical_scaled = self.scaler.fit_transform(numerical_data)
        else:
            numerical_scaled = self.scaler.transform(numerical_data)
        features.append(numerical_scaled)
        feature_names.extend(NUMERICAL_FEATURES)
        
        # 2. defect_type (OneHotEncoder)
        defect_type_encoded = self.defect_type_encoder.transform(df[['defect_type']])
        features.append(defect_type_encoded)
        defect_type_names = [f"defect_type_{cat}" for cat in self.defect_type_encoder.get_feature_names_out(['defect_type'])]
        feature_names.extend(defect_type_names)
        
        # 3. surface_location (binary: ВНШ=1, ВНТ=0)
        surface_binary = (df['surface_location'] == 'ВНШ').astype(int).values.reshape(-1, 1)
        features.append(surface_binary)
        feature_names.append('surface_location_VNSh')
        
        # Сохранить имена признаков
        if fit_scaler:
            self.feature_names = feature_names
        
        # Объединить все признаки
        X = np.hstack(features)
        return X
    
    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """
        Трансформировать данные используя обученные энкодеры.
        
        Автоматически обрабатывает NaN/None значения в опциональных параметрах,
        заполняя их медианами из обучающей выборки.
        
        Args:
            df: DataFrame с данными
            
        Returns:
            Матрица признаков
        """
        # Убрать пробелы из текстовых колонок
        df = df.copy()
        df['defect_type'] = df['defect_type'].str.strip()
        df['surface_location'] = df['surface_location'].str.strip()
        
        # Заполнить NaN в опциональных числовых колонках медианами
        optional_features = ['length_mm', 'width_mm', 'wall_thickness_mm', 'depth_mm', 'distance_to_weld_m']
        for col in optional_features:
            if col in df.columns:
                # Использовать медиану из обучающей выборки, или 0 если медианы нет
                fill_value = self.medians.get(col, 0.0)
                df[col] = df[col].fillna(fill_value)
        
        return self._transform_features(df, fit_scaler=False)
    
    def prepare_target(self, df: pd.DataFrame) -> np.ndarray:
        """
        Подготовить целевую переменную.
        
        Args:
            df: DataFrame с данными
            
        Returns:
            Массив целевых значений (0, 1, 2)
        """
        # Убрать пробелы из severity
        severity_clean = df[TARGET_COLUMN].str.strip()
        return severity_clean.map(SEVERITY_MAP).values
    
    def save(self):
        """Сохранить все энкодеры, скейлеры и медианы."""
        logger.info("Сохранение feature engineering компонентов...")
        joblib.dump(self.scaler, SCALER_PATH)
        joblib.dump(self.defect_type_encoder, ONEHOT_ENCODER_PATH)
        joblib.dump(self.feature_names, FEATURE_NAMES_PATH)
        joblib.dump(self.medians, MODELS_DIR / 'medians.joblib')
        logger.info(f"Компоненты сохранены (медианы: {self.medians})")
    
    @classmethod
    def load(cls) -> 'FeatureEngineer':
        """Загрузить сохраненные энкодеры, скейлеры и медианы."""
        logger.info("Загрузка feature engineering компонентов...")
        engineer = cls()
        engineer.scaler = joblib.load(SCALER_PATH)
        engineer.defect_type_encoder = joblib.load(ONEHOT_ENCODER_PATH)
        engineer.feature_names = joblib.load(FEATURE_NAMES_PATH)
        
        # Загрузить медианы (с обратной совместимостью)
        medians_path = MODELS_DIR / 'medians.joblib'
        if medians_path.exists():
            engineer.medians = joblib.load(medians_path)
            logger.info(f"Медианы загружены: {engineer.medians}")
        else:
            logger.warning("Файл медиан не найден, используются нули")
            engineer.medians = {}
        
        logger.info("Компоненты загружены")
        return engineer


def load_and_prepare_data(csv_path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, FeatureEngineer]:
    """
    Загрузить CSV и подготовить данные для обучения.
    
    Args:
        csv_path: Путь к CSV файлу
        
    Returns:
        X_train, X_test, y_train, y_test, feature_engineer
    """
    logger.info(f"Загрузка данных из {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # Убираем пробелы из названий колонок
    df.columns = df.columns.str.strip()
    
    logger.info(f"Загружено {len(df)} записей")
    
    # Опциональные признаки (геометрические параметры дефектов)
    optional_features = ['length_mm', 'width_mm', 'wall_thickness_mm', 'depth_mm', 'distance_to_weld_m']
    
    # Проверить наличие обязательных колонок (без опциональных)
    mandatory_features = [f for f in NUMERICAL_FEATURES if f not in optional_features]
    required_columns = mandatory_features + CATEGORICAL_FEATURES + [TARGET_COLUMN]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Отсутствуют обязательные колонки: {missing_columns}")
    
    # Добавить опциональные колонки с NaN, если их нет (будут заполнены медианами позже)
    for col in optional_features:
        if col not in df.columns:
            logger.info(f"Колонка {col} отсутствует в CSV, будет заполнена медианой")
            df[col] = np.nan
    
    # Удалить строки с пропущенными значениями в обязательных колонках
    df_clean = df.dropna(subset=required_columns)
    if len(df_clean) < len(df):
        logger.warning(f"Удалено {len(df) - len(df_clean)} строк с пропущенными значениями")
    
    # NaN в опциональных колонках оставляем - engineer.fit() вычислит медианы
    # и engineer.transform() заполнит их автоматически
    
    # Убрать пробелы из severity для корректной стратификации
    df_clean[TARGET_COLUMN] = df_clean[TARGET_COLUMN].str.strip()
    
    # Разделить на train/test стратифицированно
    train_df, test_df = train_test_split(
        df_clean, 
        test_size=(1 - TRAIN_TEST_SPLIT),
        stratify=df_clean[TARGET_COLUMN],
        random_state=RANDOM_STATE
    )
    
    logger.info(f"Train set: {len(train_df)} записей")
    logger.info(f"Test set: {len(test_df)} записей")
    logger.info(f"Распределение классов в train: {train_df[TARGET_COLUMN].value_counts().to_dict()}")
    logger.info(f"Распределение классов в test: {test_df[TARGET_COLUMN].value_counts().to_dict()}")
    
    # Создать и обучить feature engineer на train данных
    engineer = FeatureEngineer()
    engineer.fit(train_df)
    
    # Трансформировать train и test данные
    X_train = engineer.transform(train_df)
    X_test = engineer.transform(test_df)
    y_train = engineer.prepare_target(train_df)
    y_test = engineer.prepare_target(test_df)
    
    logger.info(f"X_train shape: {X_train.shape}")
    logger.info(f"X_test shape: {X_test.shape}")
    
    return X_train, X_test, y_train, y_test, engineer


def add_noise_to_data(X: np.ndarray, y: np.ndarray, noise_level: float = 0.05, 
                      augmentation_factor: int = 2, feature_dropout: float = 0.0) -> Tuple[np.ndarray, np.ndarray]:
    """
    Добавляет шум в числовые признаки для аугментации данных.
    
    Args:
        X: Матрица признаков
        y: Целевая переменная
        noise_level: Уровень шума (стандартное отклонение относительно значения)
        augmentation_factor: Сколько раз увеличить датасет (1 = не увеличивать, 2 = удвоить)
        feature_dropout: Вероятность обнулить признак (0.0-1.0)
        
    Returns:
        X_augmented, y_augmented: Расширенный датасет с шумом
    """
    if augmentation_factor <= 1:
        return X, y
    
    logger.info(f"Добавление шума в данные (уровень={noise_level}, фактор={augmentation_factor}, dropout={feature_dropout})...")
    
    X_augmented = [X]
    y_augmented = [y]
    
    # Определяем диапазон числовых признаков (первые признаки - числовые)
    num_numerical_features = len(NUMERICAL_FEATURES)
    
    for i in range(augmentation_factor - 1):
        X_noisy = X.copy()
        
        # Добавляем гауссовский шум только к числовым признакам
        for j in range(num_numerical_features):
            std = np.std(X[:, j])
            
            # Пропускаем если std = 0 или NaN (все значения одинаковые или отсутствуют)
            if std == 0 or np.isnan(std):
                continue
                
            std = std * noise_level
            noise = np.random.normal(0, std, size=X.shape[0])
            X_noisy[:, j] += noise
            
            # Feature dropout - случайно обнуляем некоторые значения
            if feature_dropout > 0:
                dropout_mask = np.random.random(X.shape[0]) < feature_dropout
                X_noisy[dropout_mask, j] = 0
        
        X_augmented.append(X_noisy)
        y_augmented.append(y)
    
    X_result = np.vstack(X_augmented)
    y_result = np.hstack(y_augmented)
    
    # Заменить любые оставшиеся NaN на 0
    X_result = np.nan_to_num(X_result, nan=0.0, posinf=0.0, neginf=0.0)
    
    logger.info(f"Размер данных после аугментации: {X_result.shape[0]} записей (было {X.shape[0]})")
    
    return X_result, y_result


def prepare_single_sample(sample_dict: Dict[str, Any], engineer: FeatureEngineer) -> np.ndarray:
    """
    Подготовить одиночный пример для предсказания.
    
    Обрабатывает None/null значения для опциональных параметров,
    заполняя их медианами из обучающей выборки.
    
    Args:
        sample_dict: Словарь с признаками (может содержать None)
        engineer: Обученный FeatureEngineer (с медианами)
        
    Returns:
        Массив признаков для предсказания
    """
    # Создать копию чтобы не изменять оригинал
    sample = sample_dict.copy()
    
    # Список опциональных параметров которые могут быть None/null
    optional_features = ['length_mm', 'width_mm', 'wall_thickness_mm', 'depth_mm', 'distance_to_weld_m']
    
    # Заполнить None/null медианами для опциональных параметров
    for feature in optional_features:
        if feature in sample and (sample[feature] is None or pd.isna(sample[feature])):
            # Использовать медиану из обучающей выборки
            fill_value = engineer.medians.get(feature, 0.0)
            sample[feature] = fill_value
    
    # Создать DataFrame из одной строки
    df = pd.DataFrame([sample])
    
    # Трансформировать (transform тоже использует медианы, но на всякий случай)
    X = engineer.transform(df)
    
    return X
