# 🚀 Быстрый старт IntegrityOS ML

## Запуск

```powershell
# 1. Активировать окружение
& .\venv\Scripts\Activate.ps1

# 2. Запустить сервер
python main.py

# Сервер: http://localhost:8000
# Документация: http://localhost:8000/docs
```

## Основные команды

```powershell
# Демонстрация
python demo.py

# Тесты API
python test_ml_api.py

# Переобучить модель
python train_model.py
```

## Пример использования

```python
import requests

# Предсказать критичность
response = requests.post("http://localhost:8000/ml/predict", json={
    "pipeline_id": "AKT-KZ",
    "measurement_distance_m": 168543.1,
    "defect_type": "коррозия",
    "depth_percent": 14.5,
    "latitude": 45.818282,
    "longitude": 51.739739,
    "altitude_m": 34.4,
    "surface_location": "ВНШ",
    "erf_b31g": 0.95
})

result = response.json()
print(f"Критичность: {result['severity']}")
print(f"Вероятность: {result['probability']}")
```

## Ключевые endpoint'ы

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/ml/predict` | Предсказать критичность |
| GET | `/ml/model/info` | Информация о модели |
| GET | `/ml/model/metrics` | Метрики модели |
| GET | `/defects` | Список дефектов |
| GET | `/docs` | Swagger UI |

## Текущие метрики

- **Модель**: RandomForest (калиброванная)
- **Точность**: 97.81%
- **F1 Score**: 96-98%
- **Классы**: normal, medium, high

## Подробная документация

См. **USAGE.md** для полной инструкции
