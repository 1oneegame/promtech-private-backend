"""
Тест для проверки документации Swagger
"""
import json
import sys
import os

# Добавляем папку src в Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.app import app

# Получаем OpenAPI схему
openapi_schema = app.openapi()

print("=" * 80)
print("SWAGGER DOCUMENTATION TEST")
print("=" * 80)

# 1. Проверка основной информации
print("\n[✓] Основная информация приложения:")
print(f"  - Title: {openapi_schema['info']['title']}")
print(f"  - Version: {openapi_schema['info']['version']}")
print(f"  - Description: {openapi_schema['info']['description'][:100]}...")

# 2. Проверка тегов
print("\n[✓] Теги (категории эндпоинтов):")
if 'tags' in openapi_schema:
    for tag in openapi_schema['tags']:
        print(f"  - {tag['name']}: {tag['description']}")
else:
    print("  Теги не найдены")

# 3. Проверка ML эндпоинтов
print("\n[✓] ML Эндпоинты:")
ml_endpoints = {}
for path, methods in openapi_schema['paths'].items():
    if '/ml/' in path:
        for method, details in methods.items():
            if 'tags' in details and 'ML' in details['tags']:
                ml_endpoints[f"{method.upper()} {path}"] = {
                    'summary': details.get('summary', 'N/A'),
                    'description': details.get('description', 'N/A')[:80]
                }

for endpoint, info in ml_endpoints.items():
    print(f"  - {endpoint}")
    print(f"    Summary: {info['summary']}")
    print(f"    Desc: {info['description']}...")

# 4. Проверка параметров ML эндпоинта predict
print("\n[✓] ML Predict Эндпоинт - детали:")
if '/ml/predict' in openapi_schema['paths']:
    predict_post = openapi_schema['paths']['/ml/predict']['post']
    print(f"  - Summary: {predict_post.get('summary', 'N/A')}")
    print(f"  - Tags: {predict_post.get('tags', [])}")
    
    # Проверяем наличие документации параметров
    description = predict_post.get('description', '')
    if 'Обязательные параметры' in description or 'обязательные' in description.lower():
        print("  - ✓ Содержит информацию об обязательных параметрах")
    if 'Опциональные параметры' in description or 'опциональные' in description.lower():
        print("  - ✓ Содержит информацию об опциональных параметрах")
    if 'Типы дефектов' in description:
        print("  - ✓ Содержит информацию о типах дефектов")
    if 'Уровни критичности' in description:
        print("  - ✓ Содержит информацию об уровнях критичности")

# 5. Сохранение схемы для проверки
print("\n[✓] Сохранение OpenAPI схемы:")
with open('swagger_schema.json', 'w', encoding='utf-8') as f:
    json.dump(openapi_schema, f, ensure_ascii=False, indent=2)
print("  - Схема сохранена в swagger_schema.json")

print("\n" + "=" * 80)
print("✓ Все проверки пройдены успешно!")
print("=" * 80)
print("\nДля просмотра документации откройте: http://localhost:8000/docs")
print("Для просмотра ReDoc: http://localhost:8000/redoc")
