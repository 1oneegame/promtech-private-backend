"""
Enhanced Synthetic Pipeline Defect Data Generator with Real Kazakhstan Infrastructure
Генератор синтетических данных дефектов на основе реальной инфраструктуры Казахстана
"""

import numpy as np
import pandas as pd
import json
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path
import uuid

from src.models import (
    Defect, DefectType, DefectParameters, Location,
    SurfaceLocation, SeverityLevel
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RealisticKazakhstanPipelineGenerator:
    """
    Генератор синтетических данных дефектов на основе реальной географии 
    казахстанских магистральных трубопроводов
    """

    # Пустой словарь - будет заполнен из CSV файла
    REAL_PIPELINES = {}

    # Распределение типов дефектов в зависимости от сквозной среды
    DEFECT_TYPE_BY_PRODUCT = {
        'crude_oil': {
            DefectType.CORROSION: 0.30,           # Коррозия в сырой нефти очень частая
            DefectType.PITTING_CORROSION: 0.15,   # Питтинг в агрессивной среде
            DefectType.EXTERNAL_CORROSION: 0.10,  # Внешняя коррозия
            DefectType.WELD_SEAM: 0.10,           # Дефекты швов
            DefectType.WELD_CRACK: 0.05,
            DefectType.DENT: 0.08,                # Механические повреждения
            DefectType.CRACK: 0.04,               # Трещины
            DefectType.METAL_OBJECT: 0.05,        # Инородные объекты
            DefectType.OTHER: 0.02,
        },
        'gas_condensate': {
            DefectType.CORROSION: 0.25,
            DefectType.PITTING_CORROSION: 0.10,
            DefectType.WELD_SEAM: 0.15,          # В газе швы более уязвимы
            DefectType.WELD_CRACK: 0.08,
            DefectType.LACK_OF_FUSION: 0.05,
            DefectType.DENT: 0.10,
            DefectType.BUCKLE: 0.05,             # Гофры в газопроводах
            DefectType.CRACK: 0.05,
            DefectType.LAMINATION: 0.04,
            DefectType.METAL_OBJECT: 0.08,
            DefectType.OTHER: 0.04,
        }
    }

    def __init__(self, seed: int = 42, csv_file: str = None):
        """Инициализация генератора"""
        np.random.seed(seed)
        self.defects_generated = 0
        
        # Загружаем реальные данные из CSV если указан файл
        if csv_file:
            self._load_pipelines_from_csv(csv_file)
        else:
            # Используем путь по умолчанию
            default_csv = Path(__file__).parent.parent / 'output' / 'kazakhstan_pipeline_segments.csv'
            if default_csv.exists():
                self._load_pipelines_from_csv(str(default_csv))
            else:
                logger.warning(f"CSV файл не найден: {default_csv}")
    
    def _load_pipelines_from_csv(self, csv_file: str):
        """Загружает реальные трубопроводы из CSV файла"""
        try:
            df = pd.read_csv(csv_file)
            # Удаляем пробелы из названий колонок
            df.columns = df.columns.str.strip()
            
            # Группируем по pipeline_id
            for pipeline_id, group in df.groupby('pipeline_id'):
                pipeline_id = pipeline_id.strip()
                
                if pipeline_id not in self.REAL_PIPELINES:
                    # Определяем тип продукта
                    product = group['product'].iloc[0].strip().lower()
                    if 'gas' in product or 'condensate' in product:
                        pipeline_type = 'gas_condensate'
                    else:
                        pipeline_type = 'crude_oil'
                    
                    self.REAL_PIPELINES[pipeline_id] = {
                        'name': group['pipeline_name'].iloc[0].strip(),
                        'type': pipeline_type,
                        'segments': []
                    }
                
                # Добавляем сегменты
                for _, row in group.iterrows():
                    segment = {
                        'segment_id': row['segment_id'].strip(),
                        'name': row['segment_name'].strip(),
                        'start': {
                            'lat': float(row['start_latitude']),
                            'lon': float(row['start_longitude']),
                            'alt': float(row['start_elevation_m'])
                        },
                        'end': {
                            'lat': float(row['end_latitude']),
                            'lon': float(row['end_longitude']),
                            'alt': float(row['end_elevation_m'])
                        },
                        'length_km': float(row['length_km']),
                        'diameter_mm': float(row['diameter_mm']),
                        'wall_thickness_mm': float(row['wall_thickness_mm']),
                        'h2s_percent': float(row['h2s_content_percent']),
                        'design_pressure': float(row['design_pressure_bar']),
                        'operating_pressure': float(row['operating_pressure_bar']),
                    }
                    self.REAL_PIPELINES[pipeline_id]['segments'].append(segment)
            
            logger.info(f"[OK] Загружены реальные трубопроводы из {csv_file}")
            logger.info(f"  Всего трубопроводов: {len(self.REAL_PIPELINES)}")
            for pid, pdata in self.REAL_PIPELINES.items():
                logger.info(f"  - {pid}: {len(pdata['segments'])} сегментов")
        
        except Exception as e:
            logger.error(f"[ERROR] Ошибка при загрузке CSV: {str(e)}")
            raise

    def _interpolate_coordinates(self, start: Dict, end: Dict, fraction: float) -> Tuple[float, float, float]:
        """
        Линейная интерполяция координат вдоль трубопровода
        
        Args:
            start: {'lat': ..., 'lon': ..., 'alt': ...}
            end: {'lat': ..., 'lon': ..., 'alt': ...}
            fraction: 0.0-1.0 позиция вдоль сегмента
        """
        lat = start['lat'] + (end['lat'] - start['lat']) * fraction
        lon = start['lon'] + (end['lon'] - start['lon']) * fraction
        alt = start['alt'] + (end['alt'] - start['alt']) * fraction
        return lat, lon, alt

    def _generate_depth_percent(self, defect_type: DefectType, h2s_percent: float) -> float:
        """
        Генерирует глубину дефекта с учетом типа и содержания H2S
        H2S ускоряет коррозию -> больше дефектов
        """
        # Коррозия и питтинг
        if defect_type in [DefectType.CORROSION, DefectType.EXTERNAL_CORROSION, DefectType.INTERNAL_CORROSION]:
            h2s_factor = 1.0 + (h2s_percent / 20.0)
            base_depth = np.random.gamma(2.5, 2.5) * h2s_factor
            return np.clip(base_depth, 0.5, 60.0)
        
        elif defect_type == DefectType.PITTING_CORROSION:
            # Питтинг более агрессивен в H2S среде
            h2s_factor = 1.5 + (h2s_percent / 15.0)
            base_depth = np.random.gamma(3.0, 2.0) * h2s_factor
            return np.clip(base_depth, 1.0, 80.0)
        
        # Сварные швы и трещины
        elif defect_type in [DefectType.WELD_SEAM, DefectType.WELD_CRACK, DefectType.LACK_OF_FUSION]:
            return np.clip(np.random.normal(2.5, 1.2), 0.5, 15.0)
        
        elif defect_type == DefectType.WELD_POROSITY:
            return np.clip(np.random.normal(1.5, 0.8), 0.2, 8.0)
        
        # Механические повреждения
        elif defect_type in [DefectType.DENT, DefectType.GOUGE, DefectType.SCRATCH]:
            return np.clip(np.random.normal(1.5, 0.7), 0.1, 10.0)
        
        elif defect_type == DefectType.ABRASION:
            return np.clip(np.random.normal(1.2, 0.6), 0.1, 8.0)
        
        # Деформации
        elif defect_type in [DefectType.BUCKLE, DefectType.OVALITY, DefectType.BEND]:
            return np.clip(np.random.normal(2.0, 1.0), 0.5, 12.0)
        
        # Трещины
        elif defect_type == DefectType.CRACK:
            h2s_factor = 1.2 + (h2s_percent / 25.0)
            base_depth = np.random.gamma(2.0, 2.0) * h2s_factor
            return np.clip(base_depth, 0.5, 40.0)
        
        elif defect_type == DefectType.SCC:  # Stress Corrosion Cracking
            h2s_factor = 2.0 + (h2s_percent / 10.0)
            base_depth = np.random.gamma(2.5, 2.0) * h2s_factor
            return np.clip(base_depth, 2.0, 50.0)
        
        # Расслоение и включения
        elif defect_type in [DefectType.LAMINATION, DefectType.INCLUSION, DefectType.OXIDE]:
            return np.clip(np.random.normal(1.0, 0.5), 0.2, 6.0)
        
        # Эрозия
        elif defect_type == DefectType.EROSION:
            base_depth = np.random.gamma(2.0, 1.5)
            return np.clip(base_depth, 0.5, 25.0)
        
        # Инородные объекты
        elif defect_type in [DefectType.METAL_OBJECT, DefectType.FOREIGN_OBJECT]:
            return np.clip(np.random.normal(0.8, 0.3), 0.1, 3.0)
        
        else:  # OTHER
            return np.clip(np.random.normal(1.5, 1.0), 0.1, 10.0)

    def _generate_erf_b31g(self, depth_percent: float, wall_thickness_mm: float) -> float:
        """
        Генерирует ERF B31G коэффициент используя формулу стандарта
        Основано на ASME B31G: ERF = 1.0 - (depth/wall_thickness) * scaling_factor
        """
        depth_mm = (depth_percent / 100.0) * wall_thickness_mm
        
        # Приблизительная формула B31G
        base_erf = 1.0 - (depth_mm / wall_thickness_mm) * 0.85
        
        # Добавляем реалистичный шум (±5%)
        noise = np.random.normal(0, 0.05)
        erf_value = base_erf + noise
        
        return np.clip(erf_value, 0.1, 1.0)

    def _calculate_severity(self, depth_percent: float) -> Tuple[SeverityLevel, float]:
        """
        Классификация критичности по ASME B31G правилам
        """
        if depth_percent > 80:
            severity = SeverityLevel.CRITICAL
            probability = min(0.99, 0.85 + (depth_percent - 80) / 100)
        elif depth_percent > 30:
            severity = SeverityLevel.HIGH
            probability = 0.65 + (depth_percent - 30) / 50 * 0.25
        elif depth_percent > 10:
            severity = SeverityLevel.MEDIUM
            probability = 0.50 + (depth_percent - 10) / 20 * 0.2
        else:
            severity = SeverityLevel.NORMAL
            probability = 0.25 + depth_percent / 10 * 0.2

        return severity, probability

    def generate_defect_for_location(self, 
                                     pipeline_id: str,
                                     segment: Dict,
                                     position_along_segment: float) -> Defect:
        """
        Генерирует один дефект для реальной локации на трубопроводе
        
        Args:
            pipeline_id: ID трубопровода
            segment: Параметры сегмента
            position_along_segment: 0.0-1.0 позиция вдоль сегмента
        """
        # Интерполируем координаты
        lat, lon, alt = self._interpolate_coordinates(
            segment['start'], 
            segment['end'], 
            position_along_segment
        )

        # Определяем тип трубопровода
        product_type = self.REAL_PIPELINES[pipeline_id]['type']
        
        # Выбираем тип дефекта с учетом типа трубопровода
        defect_types = self.DEFECT_TYPE_BY_PRODUCT[product_type]
        defect_type_list = list(defect_types.keys())
        defect_type_probs = list(defect_types.values())
        rand = np.random.random()
        cumsum = 0
        defect_type = defect_type_list[0]
        for dt, prob in zip(defect_type_list, defect_type_probs):
            cumsum += prob
            if rand < cumsum:
                defect_type = dt
                break

        # Генерируем глубину с учетом H2S
        h2s_percent = segment['h2s_percent']
        depth_percent = self._generate_depth_percent(defect_type, h2s_percent)

        # Генерируем ERF B31G
        wall_thickness = segment['wall_thickness_mm']
        erf_b31g = self._generate_erf_b31g(depth_percent, wall_thickness)

        # Классификация критичности
        severity, severity_prob = self._calculate_severity(depth_percent)

        # Параметры дефекта
        depth_mm = (depth_percent / 100.0) * wall_thickness
        
        if defect_type in [DefectType.CORROSION, DefectType.PITTING_CORROSION, DefectType.EXTERNAL_CORROSION, DefectType.INTERNAL_CORROSION]:
            # Коррозия имеет размер и глубину
            length_mm = max(5.0, np.random.normal(25.0, 8.0))
            width_mm = max(5.0, length_mm * np.random.uniform(0.65, 0.85))
            parameters = DefectParameters(
                length_mm=round(float(length_mm), 1),
                width_mm=round(float(width_mm), 1),
                depth_mm=round(float(depth_mm), 2),
                depth_percent=round(float(depth_percent), 1),
                wall_thickness_nominal_mm=wall_thickness
            )
        
        elif defect_type in [DefectType.DENT, DefectType.GOUGE, DefectType.BUCKLE, DefectType.BEND]:
            # Деформации имеют размеры
            length_mm = max(10.0, np.random.normal(40.0, 12.0))
            width_mm = max(10.0, length_mm * np.random.uniform(0.5, 0.8))
            parameters = DefectParameters(
                length_mm=round(float(length_mm), 1),
                width_mm=round(float(width_mm), 1),
                depth_mm=round(float(depth_mm), 2),
                depth_percent=round(float(depth_percent), 1),
                wall_thickness_nominal_mm=wall_thickness
            )
        
        elif defect_type in [DefectType.WELD_SEAM, DefectType.WELD_CRACK, DefectType.WELD_POROSITY, DefectType.LACK_OF_FUSION, DefectType.LAMINATION]:
            # Дефекты швов/расслоений
            length_mm = max(3.0, np.random.normal(15.0, 5.0))
            parameters = DefectParameters(
                length_mm=round(float(length_mm), 1),
                width_mm=None,
                depth_mm=round(float(depth_mm), 2),
                depth_percent=round(float(depth_percent), 1),
                wall_thickness_nominal_mm=wall_thickness
            )
        
        elif defect_type in [DefectType.CRACK, DefectType.SCC]:
            # Трещины
            length_mm = max(2.0, np.random.normal(12.0, 4.0))
            parameters = DefectParameters(
                length_mm=round(float(length_mm), 1),
                width_mm=None,
                depth_mm=round(float(depth_mm), 2),
                depth_percent=round(float(depth_percent), 1),
                wall_thickness_nominal_mm=wall_thickness
            )
        
        elif defect_type in [DefectType.SCRATCH, DefectType.ABRASION, DefectType.EROSION]:
            # Поверхностные повреждения
            length_mm = max(2.0, np.random.normal(10.0, 3.0))
            width_mm = max(1.0, np.random.normal(3.0, 1.0))
            parameters = DefectParameters(
                length_mm=round(float(length_mm), 1),
                width_mm=round(float(width_mm), 1),
                depth_mm=round(float(depth_mm), 2),
                depth_percent=round(float(depth_percent), 1),
                wall_thickness_nominal_mm=wall_thickness
            )
        
        else:  # METAL_OBJECT, FOREIGN_OBJECT, INCLUSION, OXIDE, OTHER
            # Инородные объекты и включения
            parameters = DefectParameters(
                length_mm=None,
                width_mm=None,
                depth_mm=round(float(depth_mm), 2) if depth_mm > 0 else None,
                depth_percent=round(float(depth_percent), 1),
                wall_thickness_nominal_mm=wall_thickness
            )

        # Локация на поверхности (по умолчанию внешняя нижняя - в этом месте коррозия активнее)
        surface_location = SurfaceLocation.EXTERNAL_BOTTOM if np.random.random() < 0.8 else SurfaceLocation.EXTERNAL_TOP

        # Создаем объект Defect
        self.defects_generated += 1
        defect = Defect(
            defect_id=str(uuid.uuid4()),
            segment_number=int(position_along_segment * 10),  # Условный номер сегмента
            measurement_number=self.defects_generated,
            measurement_distance_m=round(position_along_segment * segment['length_km'] * 1000, 1),
            defect_type=defect_type,
            parameters=parameters,
            location=Location(
                latitude=round(lat, 6),
                longitude=round(lon, 6),
                altitude=round(alt, 1)
            ),
            surface_location=surface_location,
            distance_to_weld_m=round(np.random.uniform(-1.5, 1.5), 2),
            erf_b31g_code=round(float(erf_b31g), 2),
            pipeline_id=pipeline_id,
            inspection_date=datetime(2025, 1, 15),
            inspection_method="MFL",
            source_file="kazakhstan_real_infrastructure.csv",
            severity=severity,
            severity_probability=round(float(severity_prob), 3)
        )

        return defect

    def generate_realistic_dataset(self, defects_per_segment: int = 5) -> List[Defect]:
        """
        Генерирует датасет дефектов на основе реальной инфраструктуры Казахстана
        
        Args:
            defects_per_segment: Количество дефектов на каждый сегмент трубопровода
        """
        all_defects = []
        total_segments = sum(
            len(pipeline['segments']) 
            for pipeline in self.REAL_PIPELINES.values()
        )
        
        logger.info(f"Начинаю генерацию дефектов на реальных казахстанских трубопроводах...")
        logger.info(f"Всего сегментов: {total_segments}, дефектов на сегмент: {defects_per_segment}")

        for pipeline_id, pipeline_data in self.REAL_PIPELINES.items():
            logger.info(f"\nТрубопровод: {pipeline_data['name']}")
            
            for segment in pipeline_data['segments']:
                logger.info(f"  Сегмент: {segment['name']}")
                
                # Генерируем дефекты вдоль сегмента
                for i in range(defects_per_segment):
                    # Случайная позиция вдоль сегмента (0.0-1.0)
                    position = np.random.random()
                    
                    try:
                        defect = self.generate_defect_for_location(
                            pipeline_id, 
                            segment, 
                            position
                        )
                        all_defects.append(defect)
                    except Exception as e:
                        logger.error(f"    Ошибка: {str(e)}")
                        continue

        logger.info(f"\n[OK] Успешно сгенерировано {len(all_defects)} дефектов на реальной инфраструктуре")
        return all_defects

    def export_to_csv(self, defects: List[Defect], output_file: str) -> bool:
        """Экспортирует в CSV"""
        try:
            data = []
            for d in defects:
                data.append({
                    'pipeline_id': d.pipeline_id,
                    'measurement_distance_m': d.measurement_distance_m,
                    'defect_type': d.defect_type.value,
                    'depth_percent': d.parameters.depth_percent,
                    'length_mm': d.parameters.length_mm if d.parameters.length_mm else None,
                    'width_mm': d.parameters.width_mm if d.parameters.width_mm else None,
                    'depth_mm': d.parameters.depth_mm if d.parameters.depth_mm else None,
                    'wall_thickness_mm': d.parameters.wall_thickness_nominal_mm if d.parameters.wall_thickness_nominal_mm else None,
                    'latitude': d.location.latitude,
                    'longitude': d.location.longitude,
                    'altitude_m': d.location.altitude,
                    'surface_location': d.surface_location.value,
                    'distance_to_weld_m': d.distance_to_weld_m if d.distance_to_weld_m else None,
                    'erf_b31g': d.erf_b31g_code,
                    'severity': d.severity.value if d.severity else '',
                    'severity_probability': d.severity_probability or '',
                })
            
            df = pd.DataFrame(data)
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            logger.info(f"[OK] Экспортировано в {output_file}")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Ошибка при экспорте: {str(e)}")
            return False

    def export_to_json(self, defects: List[Defect], output_file: str) -> bool:
        """Экспортирует в JSON"""
        try:
            data = []
            for d in defects:
                defect_dict = d.model_dump()
                defect_dict['defect_type'] = d.defect_type.value
                defect_dict['surface_location'] = d.surface_location.value
                if d.severity:
                    defect_dict['severity'] = d.severity.value
                
                data.append(defect_dict)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"[OK] Экспортировано в {output_file}")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Ошибка при экспорте: {str(e)}")
            return False

    def get_statistics(self, defects: List[Defect]) -> Dict[str, Any]:
        """Получает статистику"""
        if not defects:
            return {}

        depths = [d.parameters.depth_percent for d in defects]
        
        severity_dist = {}
        severity_probs = {}
        for d in defects:
            sev = d.severity.value if d.severity else "unknown"
            severity_dist[sev] = severity_dist.get(sev, 0) + 1
            if sev not in severity_probs:
                severity_probs[sev] = []
            if d.severity_probability:
                severity_probs[sev].append(d.severity_probability)

        pipeline_dist = {}
        for d in defects:
            pipeline_dist[d.pipeline_id] = pipeline_dist.get(d.pipeline_id, 0) + 1

        return {
            'total_defects': len(defects),
            'depth_stats': {
                'min': round(min(depths), 2),
                'max': round(max(depths), 2),
                'mean': round(np.mean(depths), 2),
                'std': round(np.std(depths), 2),
            },
            'severity_distribution': severity_dist,
            'severity_probabilities': {
                k: {
                    'mean': round(np.mean(v), 3) if v else 0,
                    'count': len(v)
                } for k, v in severity_probs.items()
            },
            'pipelines': pipeline_dist,
            'geographic_range': {
                'latitude_range': (
                    round(min(d.location.latitude for d in defects), 2),
                    round(max(d.location.latitude for d in defects), 2)
                ),
                'longitude_range': (
                    round(min(d.location.longitude for d in defects), 2),
                    round(max(d.location.longitude for d in defects), 2)
                ),
            }
        }


if __name__ == '__main__':
    # Генерируем реалистичный датасет
    generator = RealisticKazakhstanPipelineGenerator(seed=42)
    
    # 5 дефектов на каждый сегмент реальных трубопроводов
    defects = generator.generate_realistic_dataset(defects_per_segment=5)
    
    # Статистика
    stats = generator.get_statistics(defects)
    logger.info("\n" + "="*80)
    logger.info("СТАТИСТИКА РЕАЛИСТИЧНОГО ДАТАСЕТА (РЕАЛЬНАЯ ИНФРАСТРУКТУРА КЗ)")
    logger.info("="*80)
    logger.info(json.dumps(stats, indent=2, ensure_ascii=False))
    
    # Экспорт
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    
    generator.export_to_csv(defects, str(output_dir / 'kazakhstan_defects_realistic.csv'))
    generator.export_to_json(defects, str(output_dir / 'kazakhstan_defects_realistic.json'))
    
    logger.info("\n[OK] Реалистичные данные успешно созданы!")
