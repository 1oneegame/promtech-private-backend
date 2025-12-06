#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate 120+ realistic Kazakhstan pipeline defects using REAL coordinates"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.realistic_kazakhstan_generator import RealisticKazakhstanPipelineGenerator
from pathlib import Path

# Загружаем реальные координаты из CSV
csv_file = str(Path('output') / 'kazakhstan_pipeline_segments.csv')
gen = RealisticKazakhstanPipelineGenerator(seed=42, csv_file=csv_file)
defects = gen.generate_realistic_dataset(defects_per_segment=20)  # 20 на сегмент = много дефектов

stats = gen.get_statistics(defects)
print('\n' + '='*80)
print('ГЕНЕРАТОР УСПЕШНО СОЗДАЛ', len(defects), 'ДЕФЕКТОВ НА РЕАЛЬНЫХ КАЗАХСТАНСКИХ ТРУБОПРОВОДАХ')
print('='*80)
print('\nДистрибуция по трубопроводам:')
for pid, count in stats['pipelines'].items():
    print(f'- {pid}:', count, 'дефектов')

print('\nГеографический диапазон:')
lat_range = stats['geographic_range']['latitude_range']
lon_range = stats['geographic_range']['longitude_range']
print(f'- Широта: {lat_range[0]}° - {lat_range[1]}° (Казахстан)')
print(f'- Долгота: {lon_range[0]}° - {lon_range[1]}° (от Каспия до Китая)')

print('\nКритичность дефектов:')
sev_dist = stats['severity_distribution']
for severity, count in sev_dist.items():
    print(f'- {severity}: {count} дефектов')

print('\nГлубина коррозии:')
depth = stats['depth_stats']
print(f'- Минимум: {depth["min"]}%')
print(f'- Максимум: {depth["max"]}%')
print(f'- Среднее: {depth["mean"]}%')
print(f'- Стандартное отклонение: {depth["std"]}%')

output_dir = Path('output')
output_dir.mkdir(exist_ok=True)

csv_file_out = str(output_dir / 'kazakhstan_defects_real_coordinates.csv')
json_file = str(output_dir / 'kazakhstan_defects_real_coordinates.json')

gen.export_to_csv(defects, csv_file_out)
gen.export_to_json(defects, json_file)

print('\n[OK] Готовые файлы для обучения ML моделей:')
print(f'  - CSV: {csv_file_out}')
print(f'  - JSON: {json_file}')
print(f'\nВсе данные на базе РЕАЛЬНОЙ географии казахстанских магистралей!')
