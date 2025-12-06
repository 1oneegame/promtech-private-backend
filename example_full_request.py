"""
Примеры использования ML API с полными параметрами
"""
import requests
import json

BASE_URL = "http://localhost:8000"

# ============================================================================
# ПРИМЕР 1: Вложенная структура со ВСЕМИ возможными параметрами
# ============================================================================
full_nested_request = {
    "measurement_distance_m": 6.201,
    "pipeline_id": "MT-03",  # Опционально - не влияет на предсказание
    "details": {
        "type": "коррозия",
        "parameters": {
            "length_mm": 27.0,           # Опционально
            "width_mm": 19.0,            # Опционально
            "depth_mm": 2.5,             # Опционально
            "depth_percent": 9.0,        # Обязательно - влияет на критичность
            "wall_thickness_nominal_mm": 7.9  # Опционально
        },
        "location": {
            "latitude": 48.480297,       # Обязательно
            "longitude": 57.666958,      # Обязательно
            "altitude": 265.2            # Обязательно
        },
        "surface_location": "ВНШ",       # Обязательно (ВНШ или ВНТ)
        "distance_to_weld_m": -1.869,   # Опционально
        "erf_b31g_code": 0.52           # Обязательно - коэффициент ERF B31G
    }
}

# ============================================================================
# ПРИМЕР 2: Минимальная вложенная структура (только обязательные поля)
# ============================================================================
minimal_nested_request = {
    "measurement_distance_m": 6.201,
    "details": {
        "type": "коррозия",
        "parameters": {
            "depth_percent": 9.0
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

# ============================================================================
# ПРИМЕР 3: Плоская структура со всеми параметрами (старый формат)
# ============================================================================
full_flat_request = {
    "depth_percent": 65.0,
    "erf_b31g": 0.95,
    "altitude_m": 100.0,
    "latitude": 46.5,
    "longitude": 52.0,
    "measurement_distance_m": 15000.5,
    "pipeline_id": "CPC-KZ",           # Опционально - не влияет на предсказание
    "defect_type": "трещина",
    "surface_location": "ВНТ"
}

# ============================================================================
# ПРИМЕР 4: Различные типы дефектов
# ============================================================================
defect_types_examples = {
    "corrosion": {
        "measurement_distance_m": 1000.0,
        "details": {
            "type": "коррозия",
            "parameters": {"depth_percent": 15.0},
            "location": {"latitude": 47.0, "longitude": 55.0, "altitude": 200.0},
            "surface_location": "ВНШ",
            "erf_b31g_code": 0.7
        }
    },
    "crack": {
        "measurement_distance_m": 2000.0,
        "details": {
            "type": "трещина",
            "parameters": {"depth_percent": 50.0},
            "location": {"latitude": 47.5, "longitude": 55.5, "altitude": 210.0},
            "surface_location": "ВНТ",
            "erf_b31g_code": 0.9
        }
    },
    "dent": {
        "measurement_distance_m": 3000.0,
        "details": {
            "type": "вмятина",
            "parameters": {"depth_percent": 25.0},
            "location": {"latitude": 48.0, "longitude": 56.0, "altitude": 220.0},
            "surface_location": "ВНШ",
            "erf_b31g_code": 0.6
        }
    },
    "lamination": {
        "measurement_distance_m": 4000.0,
        "details": {
            "type": "расслоение",
            "parameters": {"depth_percent": 30.0},
            "location": {"latitude": 48.5, "longitude": 56.5, "altitude": 230.0},
            "surface_location": "ВНТ",
            "erf_b31g_code": 0.75
        }
    }
}

# ============================================================================
# ПРИМЕР 5: Сценарии с разной критичностью
# ============================================================================
severity_scenarios = {
    "normal_low_risk": {
        "measurement_distance_m": 100.0,
        "details": {
            "type": "царапина",
            "parameters": {"depth_percent": 5.0},
            "location": {"latitude": 46.0, "longitude": 52.0, "altitude": 150.0},
            "surface_location": "ВНШ",
            "erf_b31g_code": 0.3
        }
    },
    "medium_moderate_risk": {
        "measurement_distance_m": 5000.0,
        "details": {
            "type": "коррозия",
            "parameters": {"depth_percent": 25.0},
            "location": {"latitude": 47.0, "longitude": 53.0, "altitude": 180.0},
            "surface_location": "ВНШ",
            "erf_b31g_code": 0.65
        }
    },
    "high_critical_risk": {
        "measurement_distance_m": 10000.0,
        "details": {
            "type": "трещина",
            "parameters": {"depth_percent": 70.0},
            "location": {"latitude": 48.0, "longitude": 54.0, "altitude": 200.0},
            "surface_location": "ВНТ",
            "erf_b31g_code": 0.98
        }
    }
}


def make_prediction(data, description=""):
    """Выполнить предсказание и показать результат"""
    print(f"\n{'='*80}")
    print(f"ЗАПРОС: {description}")
    print(f"{'='*80}")
    print("\nВходные данные:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(
            f"{BASE_URL}/ml/predict",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n[RESULT] РЕЗУЛЬТАТ:")
            print(f"  Критичность: {result['severity'].upper()}")
            print(f"  Уверенность: {result['probability']:.2%}")
            print(f"  Модель: {result['model_type']}")
            print(f"\n  Детальные вероятности:")
            for severity, prob in sorted(result['probabilities'].items()):
                bar = "█" * int(prob * 50)
                print(f"    {severity:8s}: {prob:6.2%} {bar}")
        else:
            print(f"\n[ERROR] ОШИБКА {response.status_code}:")
            print(f"  {response.json()['detail']}")
            
    except Exception as e:
        print(f"\n[ERROR] ОШИБКА: {str(e)}")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("ПОЛНОЕ РУКОВОДСТВО ПО ИСПОЛЬЗОВАНИЮ ML API")
    print("="*80)
    
    # Проверка доступности сервера
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("\n[OK] Сервер доступен")
        else:
            raise Exception("Сервер вернул неожиданный статус")
    except Exception as e:
        print(f"\n[ERROR] Сервер недоступен: {str(e)}")
        print("Запустите: python main.py")
        exit(1)
    
    # ========================================================================
    # ОСНОВНЫЕ ПРИМЕРЫ
    # ========================================================================
    
    make_prediction(
        full_nested_request,
        "Полная вложенная структура (все параметры)"
    )
    
    make_prediction(
        minimal_nested_request,
        "Минимальная вложенная структура (только обязательные поля)"
    )
    
    make_prediction(
        full_flat_request,
        "Плоская структура (старый формат для обратной совместимости)"
    )
    
    # ========================================================================
    # ПРИМЕРЫ РАЗНЫХ ТИПОВ ДЕФЕКТОВ
    # ========================================================================
    
    print("\n" + "="*80)
    print("РАЗЛИЧНЫЕ ТИПЫ ДЕФЕКТОВ")
    print("="*80)
    
    for defect_name, data in defect_types_examples.items():
        make_prediction(data, f"Тип дефекта: {defect_name}")
    
    # ========================================================================
    # СЦЕНАРИИ С РАЗНОЙ КРИТИЧНОСТЬЮ
    # ========================================================================
    
    print("\n" + "="*80)
    print("СЦЕНАРИИ С РАЗНОЙ ОЖИДАЕМОЙ КРИТИЧНОСТЬЮ")
    print("="*80)
    
    for scenario_name, data in severity_scenarios.items():
        make_prediction(data, f"Сценарий: {scenario_name}")
    
    # ========================================================================
    # ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ
    # ========================================================================
    
    print("\n" + "="*80)
    print("ВАЖНАЯ ИНФОРМАЦИЯ О ПАРАМЕТРАХ")
    print("="*80)
    
    print("""
ОБЯЗАТЕЛЬНЫЕ ПАРАМЕТРЫ (влияют на предсказание):
  • depth_percent        - Глубина дефекта (0-100%)
  • erf_b31g_code       - Коэффициент ERF B31G (0-1)
  • latitude            - Широта (-90 до 90)
  • longitude           - Долгота (-180 до 180)
  • altitude            - Высота над уровнем моря (м)
  • measurement_distance_m - Расстояние по трубопроводу (м, ≥0)
  • defect_type         - Тип дефекта
  • surface_location    - Расположение (ВНШ/ВНТ)

ОПЦИОНАЛЬНЫЕ ПАРАМЕТРЫ (не влияют на предсказание):
  • pipeline_id         - ID трубопровода (для идентификации)
  • length_mm           - Длина дефекта
  • width_mm            - Ширина дефекта
  • depth_mm            - Глубина в мм
  • wall_thickness_nominal_mm - Толщина стенки
  • distance_to_weld_m  - Расстояние до сварного шва

ТИПЫ ДЕФЕКТОВ (примеры):
  коррозия, трещина, вмятина, расслоение, царапина, выработка,
  потеря металла, деформация, и другие

УРОВНИ КРИТИЧНОСТИ:
  • normal  - Нормальный (низкий риск)
  • medium  - Средний (требует мониторинга)
  • high    - Высокий (критический, требует немедленных действий)

ДОКУМЕНТАЦИЯ API:
  http://localhost:8000/docs

МЕТРИКИ МОДЕЛИ:
  GET http://localhost:8000/ml/model/metrics
    """)
    
    print("\n" + "="*80)
    print("ПРИМЕРЫ ЗАВЕРШЕНЫ")
    print("="*80)
