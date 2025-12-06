"""
CSV Parser for IntegrityOS
Парсинг данных из CSV-файлов в объекты модели
"""

import logging
from typing import List, Optional, Tuple
from pathlib import Path
import pandas as pd
from datetime import datetime
import uuid

from models import (
    Defect, DefectType, DefectParameters, Location, 
    SurfaceLocation
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('parser.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CSVParser:
    """Парсер CSV-файлов с данными диагностик трубопроводов"""
    
    # Маппинг типов дефектов
    DEFECT_TYPE_MAPPING = {
        'коррозия': DefectType.CORROSION,
        'сварной шов': DefectType.WELD_SEAM,
        'металлический объект': DefectType.METAL_OBJECT,
    }
    
    # Маппинг локаций
    LOCATION_MAPPING = {
        'ВНШ': SurfaceLocation.EXTERNAL_BOTTOM,
        'ВНТ': SurfaceLocation.EXTERNAL_TOP,
    }

    def __init__(self, data_dir: str = 'data'):
        """Инициализация парсера
        
        Args:
            data_dir: Директория с CSV-файлами
        """
        self.data_dir = Path(data_dir)
        self.errors = []
        self.warnings = []

    def parse_csv_file(self, csv_path: str) -> Tuple[List[Defect], List[str]]:
        """Парсит один CSV-файл
        
        Args:
            csv_path: Путь к CSV-файлу
            
        Returns:
            Tuple[List[Defect], List[str]]: Список дефектов и ошибок
        """
        defects = []
        errors = []
        
        try:
            logger.info(f"Начинаю парсинг файла: {csv_path}")
            
            # Попытка чтения с разными кодировками
            df = None
            for encoding in ['utf-8-sig', 'cp1251', 'utf-8', 'latin-1', 'iso-8859-1']:
                try:
                    df = pd.read_csv(csv_path, delimiter=';', encoding=encoding, header=None)
                    logger.info(f"Файл прочитан с кодировкой: {encoding}")
                    break
                except Exception as e:
                    continue
            
            if df is None:
                error_msg = f"Не удалось прочитать файл {csv_path} ни с одной кодировкой"
                logger.error(error_msg)
                errors.append(error_msg)
                return defects, errors
            
            logger.info(f"Размер датасета: {df.shape}")
            
            # Первая строка - заголовок (пропускаем)
            # Начинаем со второй строки (индекс 1)
            for idx in range(1, len(df)):
                try:
                    row = df.iloc[idx]
                    defect = self._parse_row(row, idx, csv_path)
                    if defect:
                        defects.append(defect)
                except Exception as e:
                    error_msg = f"Строка {idx + 1}: {str(e)}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
            
            logger.info(f"Успешно распарсено {len(defects)} дефектов из файла {csv_path}")
            
        except Exception as e:
            error_msg = f"Ошибка при парсинге файла {csv_path}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        return defects, errors

    def _parse_row(self, row: pd.Series, row_idx: int, source_file: str) -> Optional[Defect]:
        """Парсит одну строку CSV по реальным позициям (очищенный CSV)
        
        Структура CSV (позиции с 0):
        0: № сегмента
        1: № замера
        2: расстояние измер. [м]
        3-5: пусто / резерв
        6: расст. до шва против теч. [м]
        7-8: пусто / резерв
        9: идентификация (тип дефекта)
        10: прив.ТС [мм] (толщина стенки)
        11: длина [мм]
        12: ширина [мм]
        13: макс. глубина [%]
        14: локация на поверхн. (ВНШ / ВНТ)
        15: ERF B31G (коэффициент)
        16: пусто
        17: Широта [°]
        18: Долгота [°]
        19: высота [м]
        20+: пусто
        
        Args:
            row: Pandas Series с данными строки
            row_idx: Индекс строки в DataFrame
            source_file: Исходный файл
            
        Returns:
            Defect или None если строка невалидна
        """
        # Пропускаем пустые строки
        if row.isna().all():
            return None
        
        try:
            # Базовые параметры (позиции 0-1)
            segment_number = self._parse_int(row.iloc[0])
            measurement_number = self._parse_int(row.iloc[1])
            
            if not segment_number or not measurement_number:
                return None
            
            # Расстояние (позиция 2)
            measurement_distance_m = self._parse_float(row.iloc[2])
            if not measurement_distance_m:
                return None
            
            # Тип дефекта (позиция 9)
            defect_type_str = str(row.iloc[9]).strip().lower() if pd.notna(row.iloc[9]) else ''
            if not defect_type_str:
                return None
            
            defect_type = self.DEFECT_TYPE_MAPPING.get(defect_type_str, DefectType.OTHER)
            
            # Толщина стенки (позиция 10)
            wall_thickness_mm = self._parse_float(row.iloc[10])
            
            # Длина и ширина (позиции 11-12)
            length_mm = self._parse_float(row.iloc[11])
            width_mm = self._parse_float(row.iloc[12])
            
            # Глубина (позиция 13)
            depth_percent = self._parse_float(row.iloc[13]) if len(row) > 13 else None
            
            # Для дефектов без измеренных параметров (металл. объекты и сварные швы) используем 0 как глубину
            if depth_percent is None:
                if defect_type in [DefectType.METAL_OBJECT, DefectType.WELD_SEAM]:
                    depth_percent = 0.0
                else:
                    return None
            
            if depth_percent < 0 or depth_percent > 100:
                return None
            
            # Локация на поверхн. (позиция 14)
            surface_location_str = str(row.iloc[14]).strip() if len(row) > 14 and pd.notna(row.iloc[14]) else 'ВНШ'
            surface_location = self.LOCATION_MAPPING.get(
                surface_location_str,
                SurfaceLocation.EXTERNAL_BOTTOM
            )
            
            # GPS координаты (позиции 17-19)
            latitude = self._parse_float(row.iloc[17]) if len(row) > 17 else None
            longitude = self._parse_float(row.iloc[18]) if len(row) > 18 else None
            altitude = self._parse_float(row.iloc[19]) if len(row) > 19 else None
            
            if not (latitude and longitude):
                return None
            
            # Проверяем разумность координат (примерно Казахстан)
            if not (40 < latitude < 50 and 50 < longitude < 70):
                return None
            
            location = Location(
                latitude=latitude,
                longitude=longitude,
                altitude=altitude
            )
            
            # Параметры дефекта
            parameters = DefectParameters(
                length_mm=length_mm,
                width_mm=width_mm,
                depth_mm=None,
                depth_percent=depth_percent,
                wall_thickness_nominal_mm=wall_thickness_mm
            )
            
            # Классифицируем критичность
            # severity = self._classify_severity(depth_percent, wall_thickness_mm)
            
            # Расстояние до шва (позиция 6)
            distance_to_weld_m = self._parse_float(row.iloc[6]) if len(row) > 6 else None
            
            # ERF B31G (позиция 15)
            erf_b31g_code = self._parse_float(row.iloc[15]) if len(row) > 15 else None
            
            # Создаем объект дефекта
            defect = Defect(
                defect_id=str(uuid.uuid4()),  # Генерируем уникальный ID
                segment_number=segment_number,
                measurement_number=measurement_number,
                measurement_distance_m=measurement_distance_m,
                defect_type=defect_type,
                # severity=severity,
                parameters=parameters,
                location=location,
                surface_location=surface_location,
                distance_to_weld_m=distance_to_weld_m,
                erf_b31g_code=erf_b31g_code,
                source_file=source_file,
                pipeline_id=f"MT-{segment_number:02d}"
            )
            
            return defect
            
        except Exception as e:
            logger.warning(f"Ошибка при парсинге строки {row_idx}: {str(e)}")
            return None

    def _parse_float(self, value) -> Optional[float]:
        """Парсит значение в float, обрабатывая запятые как десятичные разделители"""
        if pd.isna(value):
            return None
        try:
            if isinstance(value, str):
                # Заменяем запятую на точку (русский формат)
                value = value.replace(',', '.')
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_int(self, value) -> Optional[int]:
        """Парсит значение в int"""
        if pd.isna(value):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def parse_all_csv_files(self) -> Tuple[List[Defect], List[str]]:
        """Парсит все CSV-файлы в директории data/
        
        Returns:
            Tuple[List[Defect], List[str]]: Все дефекты и ошибки
        """
        all_defects = []
        all_errors = []
        
        # Ищем CSV-файлы в корне data/ и в data/CSV/
        csv_patterns = [
            self.data_dir / '*.csv',
            self.data_dir / 'CSV' / '*.csv'
        ]
        
        csv_files = []
        for pattern in csv_patterns:
            csv_files.extend(pattern.parent.glob(pattern.name))
        
        if not csv_files:
            logger.warning(f"CSV-файлы не найдены в {self.data_dir}")
            return all_defects, ["CSV-файлы не найдены"]
        
        logger.info(f"Найдено {len(csv_files)} CSV-файлов для парсинга")
        
        for csv_file in csv_files:
            defects, errors = self.parse_csv_file(str(csv_file))
            all_defects.extend(defects)
            all_errors.extend(errors)
        
        logger.info(f"Всего распарсено {len(all_defects)} дефектов")
        if all_errors:
            logger.info(f"Зафиксировано {len(all_errors)} ошибок/предупреждений")
        
        return all_defects, all_errors

    def export_to_json(self, defects: List[Defect], output_file: str = 'defects.json') -> bool:
        """Экспортирует дефекты в JSON
        
        Args:
            defects: Список дефектов
            output_file: Файл для сохранения
            
        Returns:
            bool: Успешность операции
        """
        try:
            import json
            
            defects_data = [json.loads(defect.model_dump_json()) for defect in defects]
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(defects_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Экспортировано {len(defects)} дефектов в {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при экспорте в JSON: {str(e)}")
            return False

    def save_errors_log(self, errors: List[str], log_file: str = 'parse_errors.log') -> bool:
        """Сохраняет лог ошибок парсинга
        
        Args:
            errors: Список ошибок
            log_file: Файл для сохранения
            
        Returns:
            bool: Успешность операции
        """
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"Лог ошибок парсинга от {datetime.utcnow().isoformat()}\n")
                f.write("=" * 80 + "\n\n")
                for error in errors:
                    f.write(f"• {error}\n")
            
            logger.info(f"Лог ошибок сохранен в {log_file}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении лога ошибок: {str(e)}")
            return False


if __name__ == '__main__':
    # Тестирование парсера
    parser = CSVParser(data_dir='data')
    defects, errors = parser.parse_all_csv_files()
    
    print(f"\n[OK] Распарсено {len(defects)} дефектов")
    if errors:
        print(f"⚠ Зафиксировано {len(errors)} ошибок/предупреждений")
    
    # Экспортируем в JSON
    if defects:
        parser.export_to_json(defects)
    
    # Сохраняем лог ошибок
    if errors:
        parser.save_errors_log(errors)
