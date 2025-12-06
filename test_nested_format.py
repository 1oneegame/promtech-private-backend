"""
Тест API с вложенной структурой данных
"""
import requests
import json

# Базовый URL API
BASE_URL = "http://localhost:8000"

def test_nested_format():
    """Тест предсказания с вложенной структурой"""
    
    # Вложенная структура как в примере пользователя
    nested_data = {
        "measurement_distance_m": 6.201,
        "pipeline_id": "CPC-KZ",  # Используем pipeline_id из обучающей выборки
        "details": {
            "type": "коррозия",
            "parameters": {
                "length_mm": 27.0,
                "width_mm": 19.0,
                "depth_mm": None,
                "depth_percent": 9.0,
                "wall_thickness_nominal_mm": 7.9
            },
            "location": {
                "latitude": 48.480297,
                "longitude": 57.666958,
                "altitude": 265.2
            },
            "surface_location": "ВНШ",
            "distance_to_weld_m": -1.869,
            "erf_b31g_code": 0.52
        }
    }
    
    print("\n" + "="*80)
    print("ТЕСТ 1: Вложенная структура (новый формат)")
    print("="*80)
    print("\nЗапрос (nested format):")
    print(json.dumps(nested_data, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(
            f"{BASE_URL}/ml/predict",
            json=nested_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\n[SUCCESS] Предсказание получено:")
            print(f"  Критичность: {result['severity']}")
            print(f"  Вероятность: {result['probability']:.2%}")
            print(f"  Модель: {result['model_type']}")
            print("\n  Все вероятности:")
            for severity, prob in result['probabilities'].items():
                print(f"    {severity}: {prob:.2%}")
        else:
            print(f"\n[ERROR] Статус: {response.status_code}")
            print(f"Ответ: {response.text}")
            
    except Exception as e:
        print(f"\n[ERROR] Ошибка при запросе: {str(e)}")


def test_flat_format():
    """Тест предсказания со старой плоской структурой"""
    
    # Плоская структура (обратная совместимость)
    flat_data = {
        "depth_percent": 9.0,
        "erf_b31g": 0.52,
        "altitude_m": 265.2,
        "latitude": 48.480297,
        "longitude": 57.666958,
        "measurement_distance_m": 6.201,
        "pipeline_id": "CPC-KZ",  # Используем pipeline_id из обучающей выборки
        "defect_type": "коррозия",
        "surface_location": "ВНШ"
    }
    
    print("\n" + "="*80)
    print("ТЕСТ 2: Плоская структура (старый формат - обратная совместимость)")
    print("="*80)
    print("\nЗапрос (flat format):")
    print(json.dumps(flat_data, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(
            f"{BASE_URL}/ml/predict",
            json=flat_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\n[SUCCESS] Предсказание получено:")
            print(f"  Критичность: {result['severity']}")
            print(f"  Вероятность: {result['probability']:.2%}")
            print(f"  Модель: {result['model_type']}")
            print("\n  Все вероятности:")
            for severity, prob in result['probabilities'].items():
                print(f"    {severity}: {prob:.2%}")
        else:
            print(f"\n[ERROR] Статус: {response.status_code}")
            print(f"Ответ: {response.text}")
            
    except Exception as e:
        print(f"\n[ERROR] Ошибка при запросе: {str(e)}")


def test_high_severity():
    """Тест с высокой критичностью (вложенная структура)"""
    
    nested_data = {
        "measurement_distance_m": 15000.5,
        "pipeline_id": "CPC-KZ",
        "details": {
            "type": "трещина",
            "parameters": {
                "depth_percent": 65.0,
                "wall_thickness_nominal_mm": 10.0
            },
            "location": {
                "latitude": 46.5,
                "longitude": 52.0,
                "altitude": 100.0
            },
            "surface_location": "ВНТ",
            "erf_b31g_code": 0.95
        }
    }
    
    print("\n" + "="*80)
    print("ТЕСТ 3: Высокая критичность (вложенная структура)")
    print("="*80)
    print("\nЗапрос:")
    print(json.dumps(nested_data, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(
            f"{BASE_URL}/ml/predict",
            json=nested_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\n[SUCCESS] Предсказание получено:")
            print(f"  Критичность: {result['severity']}")
            print(f"  Вероятность: {result['probability']:.2%}")
            print(f"  Модель: {result['model_type']}")
            print("\n  Все вероятности:")
            for severity, prob in result['probabilities'].items():
                print(f"    {severity}: {prob:.2%}")
        else:
            print(f"\n[ERROR] Статус: {response.status_code}")
            print(f"Ответ: {response.text}")
            
    except Exception as e:
        print(f"\n[ERROR] Ошибка при запросе: {str(e)}")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("ТЕСТИРОВАНИЕ API С ВЛОЖЕННОЙ И ПЛОСКОЙ СТРУКТУРОЙ")
    print("="*80)
    print("\nПроверка сервера...")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("[OK] Сервер доступен")
        else:
            print("[WARNING] Сервер вернул неожиданный статус")
    except Exception as e:
        print(f"[ERROR] Сервер недоступен: {str(e)}")
        print("Убедитесь, что сервер запущен: python -m uvicorn src.app:app --reload")
        exit(1)
    
    # Запуск тестов
    test_nested_format()
    test_flat_format()
    test_high_severity()
    
    print("\n" + "="*80)
    print("ТЕСТЫ ЗАВЕРШЕНЫ")
    print("="*80)
    print("\nДоступна документация API: http://localhost:8000/docs")
    print()
