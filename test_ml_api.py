"""
Тестирование ML API endpoints
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_predict():
    """Тест предсказания критичности"""
    url = f"{BASE_URL}/ml/predict"
    
    # Тестовый дефект
    data = {
        "pipeline_id": "AKT-KZ",
        "measurement_distance_m": 168543.1,
        "defect_type": "коррозия",
        "depth_percent": 14.5,
        "latitude": 45.818282,
        "longitude": 51.739739,
        "altitude_m": 34.4,
        "surface_location": "ВНШ",
        "erf_b31g": 0.95
    }
    
    print("=" * 80)
    print("ТЕСТ 1: POST /ml/predict")
    print("=" * 80)
    print(f"\nЗапрос: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    response = requests.post(url, json=data)
    
    print(f"\nСтатус: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"\nРезультат:")
        print(f"  Предсказанная критичность: {result.get('severity', 'N/A')}")
        print(f"  Вероятности:")
        for severity, prob in result.get('probabilities', {}).items():
            print(f"    {severity}: {prob:.4f}")
    else:
        print(f"Ошибка: {response.text}")
    
    return response.status_code == 200


def test_model_info():
    """Тест получения информации о модели"""
    url = f"{BASE_URL}/ml/model/info"
    
    print("\n" + "=" * 80)
    print("ТЕСТ 2: GET /ml/model/info")
    print("=" * 80)
    
    response = requests.get(url)
    
    print(f"\nСтатус: {response.status_code}")
    if response.status_code == 200:
        info = response.json()
        print(f"\nИнформация о модели:")
        print(f"  Тип модели: {info.get('model_type', 'N/A')}")
        print(f"  F1 Score: {info.get('f1_score', 'N/A')}")
        print(f"  Дата обучения: {info.get('training_date', 'N/A')}")
    else:
        print(f"Ошибка: {response.text}")
    
    return response.status_code == 200


def test_model_metrics():
    """Тест получения метрик модели"""
    url = f"{BASE_URL}/ml/model/metrics"
    
    print("\n" + "=" * 80)
    print("ТЕСТ 3: GET /ml/model/metrics")
    print("=" * 80)
    
    response = requests.get(url)
    
    print(f"\nСтатус: {response.status_code}")
    if response.status_code == 200:
        metrics = response.json()
        print(f"\nСравнение моделей:")
        for model_name, model_metrics in metrics.get('models_comparison', {}).items():
            print(f"\n  {model_name}:")
            print(f"    Accuracy: {model_metrics['accuracy']:.4f}")
            print(f"    F1 (weighted): {model_metrics['f1_weighted']:.4f}")
    else:
        print(f"Ошибка: {response.text}")
    
    return response.status_code == 200


def main():
    print("\n" + "=" * 80)
    print("ТЕСТИРОВАНИЕ ML API ENDPOINTS")
    print("=" * 80)
    
    try:
        # Проверка доступности сервера
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("\n[ERROR] Сервер недоступен. Запустите: python main.py")
            return
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Сервер недоступен. Запустите: python main.py")
        return
    
    # Запуск тестов
    results = []
    results.append(("Predict", test_predict()))
    results.append(("Model Info", test_model_info()))
    results.append(("Model Metrics", test_model_metrics()))
    
    # Итоги
    print("\n" + "=" * 80)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 80)
    for test_name, passed in results:
        status = "[PASSED]" if passed else "[FAILED]"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    print(f"\nИтого: {passed}/{total} тестов пройдено")


if __name__ == "__main__":
    main()
