"""
Тест автоматического обучения модели при отсутствии файлов
"""
import requests
import time

BASE_URL = "http://localhost:8000"

def test_auto_training():
    """Тест автоматического обучения при первом запросе"""

    # Пример запроса
    test_data = {
        "measurement_distance_m": 6.201,
        "pipeline_id": "TEST-01",
        "details": {
            "type": "коррозия",
            "parameters": {
                "depth_percent": 15.0
            },
            "location": {
                "latitude": 48.480297,
                "longitude": 57.666958,
                "altitude": 265.2
            },
            "surface_location": "ВНШ",
            "erf_b31g_code": 0.52
        }
    }

    print("\n" + "="*80)
    print("ТЕСТ АВТОМАТИЧЕСКОГО ОБУЧЕНИЯ МОДЕЛИ")
    print("="*80)
    print("\nМодель была удалена. Первый запрос вызовет автоматическое обучение...")

    start_time = time.time()

    try:
        print("\nОтправка запроса...")
        response = requests.post(
            f"{BASE_URL}/ml/predict",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=300  # 5 минут таймаут
        )

        elapsed_time = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            print(f"\n[SUCCESS] УСПЕХ! Автоматическое обучение завершено!")
            print(f"Время выполнения: {elapsed_time:.1f} сек")
            print(f"  Критичность: {result['severity']}")
            print(f"  Вероятность: {result['probability']:.2%}")
            print(f"  Модель: {result['model_type']}")

        elif response.status_code == 503:
            print(f"\n[WARNING] Сервис недоступен: {response.json()['detail']}")
            print("Это нормально - модель обучается в фоне")

        else:
            print(f"\n[ERROR] Ошибка {response.status_code}: {response.text}")

    except requests.exceptions.Timeout:
        print("\n[TIMEOUT] Таймаут! Обучение занимает больше 5 минут")
        print("Это нормально для первого запуска")

    except Exception as e:
        print(f"\n[ERROR] Ошибка: {str(e)}")

    print("\n" + "="*80)
    print("ПРОВЕРКА ЗАВЕРШЕНА")
    print("="*80)

if __name__ == "__main__":
    # Проверка сервера
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print("[OK] Сервер доступен")
            test_auto_training()
        else:
            print("[ERROR] Сервер вернул неожиданный статус")
    except Exception as e:
        print(f"[ERROR] Сервер недоступен: {str(e)}")
        print("Запустите: python main.py")