"""
Тестирование предсказаний на разных входных данных
"""
import requests
import json

BASE_URL = "http://localhost:8000"

test_cases = [
    {
        "name": "Лёгкая коррозия (должно быть normal)",
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
        "name": "Средняя коррозия (должно быть medium)",
        "data": {
            "pipeline_id": "AKT-KZ",
            "measurement_distance_m": 200000.0,
            "defect_type": "коррозия",
            "depth_percent": 15.0,
            "latitude": 45.5,
            "longitude": 51.5,
            "altitude_m": 35.0,
            "surface_location": "ВНШ",
            "erf_b31g": 0.85
        }
    },
    {
        "name": "Глубокая коррозия (должно быть high)",
        "data": {
            "pipeline_id": "AKT-KZ",
            "measurement_distance_m": 300000.0,
            "defect_type": "коррозия",
            "depth_percent": 30.0,
            "latitude": 45.5,
            "longitude": 51.5,
            "altitude_m": 35.0,
            "surface_location": "ВНШ",
            "erf_b31g": 0.65
        }
    },
    {
        "name": "Трещина средней глубины",
        "data": {
            "pipeline_id": "CPC-KZ",
            "measurement_distance_m": 150000.0,
            "defect_type": "трещина",
            "depth_percent": 12.0,
            "latitude": 46.0,
            "longitude": 52.0,
            "altitude_m": 40.0,
            "surface_location": "ВНТ",
            "erf_b31g": 0.88
        }
    },
    {
        "name": "Вмятина (обычно normal)",
        "data": {
            "pipeline_id": "AKT-KZ",
            "measurement_distance_m": 180000.0,
            "defect_type": "вмятина",
            "depth_percent": 3.0,
            "latitude": 45.8,
            "longitude": 51.7,
            "altitude_m": 33.0,
            "surface_location": "ВНШ",
            "erf_b31g": 0.98
        }
    }
]

print("\n" + "=" * 80)
print("ТЕСТИРОВАНИЕ ПРЕДСКАЗАНИЙ НА РАЗНЫХ ТИПАХ ДЕФЕКТОВ")
print("=" * 80)

for i, test_case in enumerate(test_cases, 1):
    print(f"\n[{i}/{len(test_cases)}] {test_case['name']}")
    print("-" * 80)
    
    response = requests.post(f"{BASE_URL}/ml/predict", json=test_case['data'])
    
    if response.status_code == 200:
        result = response.json()
        severity = result['severity']
        probs = result['probabilities']
        
        print(f"Предсказание: {severity}")
        print(f"Вероятности:")
        for sev, prob in probs.items():
            bar = "█" * int(prob * 40)
            print(f"  {sev:8s}: {prob:.1%} {bar}")
    else:
        print(f"ОШИБКА: {response.status_code}")
        print(response.text)

print("\n" + "=" * 80)
