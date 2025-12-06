"""
Простой пример использования ML API
"""
import requests
import json

# URL сервера
BASE_URL = "http://localhost:8000"

def check_server():
    """Проверка доступности сервера"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            print("[OK] Сервер работает")
            return True
    except:
        pass
    print("[ERROR] Сервер недоступен. Запустите: python main.py")
    return False


def predict_defect(defect_data):
    """Предсказание критичности дефекта"""
    print("\n" + "=" * 60)
    print("ПРЕДСКАЗАНИЕ КРИТИЧНОСТИ ДЕФЕКТА")
    print("=" * 60)
    
    print("\nВходные данные:")
    for key, value in defect_data.items():
        print(f"  {key}: {value}")
    
    response = requests.post(f"{BASE_URL}/ml/predict", json=defect_data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n{'=' * 60}")
        print(f"РЕЗУЛЬТАТ:")
        print(f"{'=' * 60}")
        print(f"  Критичность: {result['severity'].upper()}")
        print(f"  Уверенность: {result['probability']:.1%}")
        print(f"\n  Вероятности всех классов:")
        for severity, prob in result['probabilities'].items():
            bar = "█" * int(prob * 40)
            print(f"    {severity:8s}: {prob:6.1%} {bar}")
        print(f"\n  Модель: {result['model_type']}")
        return result
    else:
        print(f"\n[ERROR] Ошибка: {response.status_code}")
        print(response.text)
        return None


def get_model_info():
    """Информация о модели"""
    print("\n" + "=" * 60)
    print("ИНФОРМАЦИЯ О МОДЕЛИ")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/ml/model/info")
    
    if response.status_code == 200:
        info = response.json()
        print(f"\n  Тип модели: {info['model_type']}")
        print(f"  F1 Score: {info['f1_score']:.2%}")
        print(f"  Дата обучения: {info['training_date']}")
        print(f"  Метод калибровки: {info['calibration_method']}")
        print(f"  Количество признаков: {info['feature_count']}")
        return info
    else:
        print(f"\n[ERROR] Ошибка: {response.status_code}")
        return None


def main():
    print("\n" + "=" * 60)
    print("ДЕМОНСТРАЦИЯ IntegrityOS ML API")
    print("=" * 60)
    
    # Проверка сервера
    if not check_server():
        return
    
    # Информация о модели
    get_model_info()
    
    # Примеры дефектов
    examples = [
        {
            "name": "Легкая коррозия",
            "data": {
                "pipeline_id": "AKT-KZ",
                "measurement_distance_m": 100000.0,
                "defect_type": "коррозия",
                "depth_percent": 5.0,
                "latitude": 45.5,
                "longitude": 51.5,
                "altitude_m": 35.0,
                "surface_location": "ВНШ",
                "erf_b31g": 0.95
            }
        },
        {
            "name": "Средняя трещина",
            "data": {
                "pipeline_id": "CPC-KZ",
                "measurement_distance_m": 200000.0,
                "defect_type": "трещина",
                "depth_percent": 15.0,
                "latitude": 46.0,
                "longitude": 52.0,
                "altitude_m": 40.0,
                "surface_location": "ВНТ",
                "erf_b31g": 0.85
            }
        },
        {
            "name": "Глубокая коррозия",
            "data": {
                "pipeline_id": "AKT-KZ",
                "measurement_distance_m": 300000.0,
                "defect_type": "коррозия",
                "depth_percent": 28.0,
                "latitude": 45.2,
                "longitude": 51.3,
                "altitude_m": 33.0,
                "surface_location": "ВНШ",
                "erf_b31g": 0.68
            }
        }
    ]
    
    # Предсказания
    for i, example in enumerate(examples, 1):
        print(f"\n\n{'#' * 60}")
        print(f"ПРИМЕР {i}: {example['name']}")
        print(f"{'#' * 60}")
        predict_defect(example['data'])
    
    print("\n" + "=" * 60)
    print("Для полной документации см. USAGE.md")
    print("Swagger UI: http://localhost:8000/docs")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
