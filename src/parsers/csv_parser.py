"""
CSV/XLSX Parser for IntegrityOS
Парсинг данных из CSV и XLSX файлов в объекты модели
"""

import logging
from typing import List, Optional, Tuple
from pathlib import Path
import pandas as pd
from datetime import datetime
import uuid

from core.models import (
    Defect, DefectType, DefectParameters, Location, 
    SurfaceLocation
)

logger = logging.getLogger(__name__)


class CSVParser:
    """Парсер CSV и XLSX файлов с данными диагностик трубопроводов"""
    
    # Маппинг типов дефектов
    DEFECT_TYPE_MAPPING = {
        'коррозия': DefectType.CORROSION,
        'сварной шов': DefectType.WELD_SEAM,
        'металлический объект': DefectType.METAL_OBJECT,
        # Новые типы для журнала раскладки труб
        'коррозионный кластер': DefectType.CORROSION,
        'продольношовная': DefectType.WELD_SEAM,
        'поперечный шов': DefectType.WELD_SEAM,
        'рядом мет. объект': DefectType.METAL_OBJECT,
        'наземный маркер': DefectType.OTHER,
    }
    
    # Маппинг типов особенностей
    FEATURE_TYPE_MAPPING = {
        'потеря металла': DefectType.CORROSION,
        'сварной шов': DefectType.WELD_SEAM,
        'рядом мет. объект': DefectType.METAL_OBJECT,
        'наземный маркер': DefectType.OTHER,
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

    def parse_xlsx_file(self, xlsx_path: str) -> Tuple[List[Defect], List[str]]:
        """Парсит один XLSX-файл (поддерживает формат 'Заключительный Excel' с несколькими листами)
        
        Args:
            xlsx_path: Путь к XLSX-файлу
            
        Returns:
            Tuple[List[Defect], List[str]]: Список дефектов и ошибок
        """
        defects = []
        errors = []
        
        try:
            logger.info(f"Начинаю парсинг XLSX файла: {xlsx_path}")
            
            # Читаем XLSX с помощью pandas (использует openpyxl)
            try:
                xl = pd.ExcelFile(xlsx_path, engine='openpyxl')
                sheet_names = xl.sheet_names
                logger.info(f"XLSX файл прочитан успешно. Листов: {len(sheet_names)}")
            except ImportError:
                error_msg = "openpyxl не установлен. Установите: pip install openpyxl"
                logger.error(error_msg)
                errors.append(error_msg)
                return defects, errors
            except Exception as e:
                error_msg = f"Не удалось прочитать XLSX файл {xlsx_path}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                return defects, errors
            
            # Приоритетные листы для парсинга аномалий/дефектов
            priority_sheets = [
                'Аномалии',
                'Список наиб. опасн. аномалий',
                'Аномалии подлежащие ремонту',
                'Аномалии первоочередн. ремонта',
            ]
            
            # Выбираем листы для парсинга
            sheets_to_parse = []
            for sheet in priority_sheets:
                if sheet in sheet_names:
                    sheets_to_parse.append(sheet)
                    break  # Берём только первый найденный приоритетный лист
            
            # Если приоритетные листы не найдены, парсим первый лист
            if not sheets_to_parse:
                sheets_to_parse = [sheet_names[0]]
            
            for sheet_name in sheets_to_parse:
                logger.info(f"Парсинг листа: {sheet_name}")
                df = pd.read_excel(xl, sheet_name=sheet_name, header=None)
                logger.info(f"Размер листа '{sheet_name}': {df.shape}")
                
                # Определяем формат файла по заголовкам
                header_row = self._find_header_row(df)
                if header_row is None:
                    logger.warning(f"Не удалось найти строку заголовков в листе {sheet_name}")
                    continue
                
                logger.info(f"Заголовки найдены в строке {header_row}")
                
                # Определяем структуру колонок
                column_map = self._detect_column_mapping(df.iloc[header_row])
                logger.info(f"Маппинг колонок: {column_map}")
                
                # Парсим строки данных
                for idx in range(header_row + 1, len(df)):
                    try:
                        row = df.iloc[idx]
                        defect = self._parse_anomaly_row(row, idx, xlsx_path, column_map, sheet_name)
                        if defect:
                            defects.append(defect)
                    except Exception as e:
                        error_msg = f"Лист '{sheet_name}', строка {idx + 1}: {str(e)}"
                        logger.warning(error_msg)
                        errors.append(error_msg)
                
                logger.info(f"Из листа '{sheet_name}' распарсено {len(defects)} дефектов")
            
        except Exception as e:
            error_msg = f"Ошибка при парсинге XLSX файла {xlsx_path}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        return defects, errors

    def _find_header_row(self, df: pd.DataFrame) -> Optional[int]:
        """Находит строку с заголовками в DataFrame
        
        Ищет строку где есть ключевые слова типа 'измер. расст.', 'длина', 'ширина' и т.д.
        """
        keywords = ['измер', 'длина', 'ширина', 'глубина', 'широта', 'долгота', 'секции']
        
        for idx in range(min(15, len(df))):
            row = df.iloc[idx]
            row_text = ' '.join(str(v).lower() for v in row if pd.notna(v))
            matches = sum(1 for kw in keywords if kw in row_text)
            if matches >= 3:
                return idx
        return None

    def _detect_column_mapping(self, header_row: pd.Series) -> dict:
        """Определяет маппинг колонок по заголовкам
        
        Returns:
            dict с индексами колонок для каждого поля
        """
        mapping = {}
        
        column_patterns = {
            'measurement_distance': ['измер. расст', 'измер расст'],
            'section_number': ['№ секции', 'секции'],
            'section_length': ['длина секции'],
            'wall_thickness': ['прив.тс', 'толщ'],
            'distance_to_weld': ['расст. до шва', 'до шва'],
            'anomaly_type': ['тип аномалии', 'тип особенн'],
            'identification': ['идентификация'],
            'length_mm': ['длина [мм]'],
            'width_mm': ['ширина [мм]', 'ширина'],
            'depth_percent': ['макс. глубина', 'глубина [%]'],
            'depth_mm': ['глубина [мм]'],
            'erf_b31g': ['erf b31g', 'erf'],
            'surface_location': ['локация на поверхн', 'локация'],
            'latitude': ['широта'],
            'longitude': ['долгота'],
            'altitude': ['высота'],
            'weld_at': ['шов на'],
        }
        
        for idx, val in enumerate(header_row):
            if pd.isna(val):
                continue
            val_lower = str(val).lower().strip()
            
            for field, patterns in column_patterns.items():
                if field not in mapping:
                    for pattern in patterns:
                        if pattern in val_lower:
                            mapping[field] = idx
                            break
        
        return mapping

    def _parse_anomaly_row(self, row: pd.Series, row_idx: int, source_file: str, 
                           column_map: dict, sheet_name: str) -> Optional[Defect]:
        """Парсит строку из листа аномалий Excel
        
        Args:
            row: Pandas Series с данными строки
            row_idx: Индекс строки в DataFrame
            source_file: Исходный файл
            column_map: Маппинг колонок
            sheet_name: Имя листа
            
        Returns:
            Defect или None если строка невалидна
        """
        # Пропускаем пустые строки
        if row.isna().all():
            return None
        
        try:
            # Расстояние измерения (обязательно)
            meas_dist_col = column_map.get('measurement_distance')
            if meas_dist_col is None:
                return None
            measurement_distance_m = self._parse_float(row.iloc[meas_dist_col])
            if measurement_distance_m is None:
                return None
            
            # Номер секции
            section_col = column_map.get('section_number')
            segment_number = self._parse_int(row.iloc[section_col]) if section_col is not None else 1
            if segment_number is None:
                segment_number = 1
            
            # Тип аномалии / идентификация
            anomaly_type_col = column_map.get('anomaly_type')
            identification_col = column_map.get('identification')
            
            defect_type_str = ''
            if identification_col is not None and pd.notna(row.iloc[identification_col]):
                defect_type_str = str(row.iloc[identification_col]).strip().lower()
            elif anomaly_type_col is not None and pd.notna(row.iloc[anomaly_type_col]):
                defect_type_str = str(row.iloc[anomaly_type_col]).strip().lower()
            
            if not defect_type_str:
                return None
            
            defect_type = self.DEFECT_TYPE_MAPPING.get(defect_type_str, DefectType.OTHER)
            
            # Толщина стенки
            wall_col = column_map.get('wall_thickness')
            wall_thickness_mm = self._parse_float(row.iloc[wall_col]) if wall_col is not None else None
            
            # Длина и ширина
            length_col = column_map.get('length_mm')
            width_col = column_map.get('width_mm')
            length_mm = self._parse_float(row.iloc[length_col]) if length_col is not None else None
            width_mm = self._parse_float(row.iloc[width_col]) if width_col is not None else None
            
            # Глубина
            depth_col = column_map.get('depth_percent')
            depth_percent = self._parse_float(row.iloc[depth_col]) if depth_col is not None else None
            
            # Для не-коррозионных дефектов глубина может быть 0
            if depth_percent is None:
                if defect_type in [DefectType.WELD_SEAM, DefectType.METAL_OBJECT, DefectType.OTHER]:
                    depth_percent = 0.0
                else:
                    return None
            
            # Координаты
            lat_col = column_map.get('latitude')
            lon_col = column_map.get('longitude')
            alt_col = column_map.get('altitude')
            
            latitude = self._parse_float(row.iloc[lat_col]) if lat_col is not None else None
            longitude = self._parse_float(row.iloc[lon_col]) if lon_col is not None else None
            altitude = self._parse_float(row.iloc[alt_col]) if alt_col is not None else None
            
            # Координаты обязательны
            if latitude is None or longitude is None:
                return None
            
            # Проверяем разумность координат (Казахстан)
            if not (40 < latitude < 56 and 46 < longitude < 88):
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
            
            # Локация на поверхности
            surface_col = column_map.get('surface_location')
            surface_location_str = str(row.iloc[surface_col]).strip() if surface_col is not None and pd.notna(row.iloc[surface_col]) else 'ВНШ'
            surface_location = self.LOCATION_MAPPING.get(surface_location_str, SurfaceLocation.EXTERNAL_BOTTOM)
            
            # Расстояние до шва
            weld_col = column_map.get('distance_to_weld')
            distance_to_weld_m = self._parse_float(row.iloc[weld_col]) if weld_col is not None else None
            
            # ERF B31G
            erf_col = column_map.get('erf_b31g')
            erf_b31g_code = self._parse_float(row.iloc[erf_col]) if erf_col is not None else None
            
            # Создаем дефект
            defect = Defect(
                defect_id=str(uuid.uuid4()),
                segment_number=segment_number,
                measurement_number=row_idx,
                measurement_distance_m=measurement_distance_m,
                defect_type=defect_type,
                parameters=parameters,
                location=location,
                surface_location=surface_location,
                distance_to_weld_m=distance_to_weld_m,
                erf_b31g_code=erf_b31g_code,
                pipeline_id=f"MT-{segment_number:02d}",
                source_file=f"{Path(source_file).name} [{sheet_name}]"
            )
            
            return defect
            
        except Exception as e:
            logger.warning(f"Ошибка при парсинге строки {row_idx}: {str(e)}")
            return None

    def parse_file(self, file_path: str) -> Tuple[List[Defect], List[str]]:
        """Парсит файл (автоматически определяет формат по расширению)
        
        Args:
            file_path: Путь к файлу (CSV или XLSX)
            
        Returns:
            Tuple[List[Defect], List[str]]: Список дефектов и ошибок
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        if extension == '.csv':
            return self.parse_csv_file(file_path)
        elif extension in ['.xlsx', '.xls']:
            return self.parse_xlsx_file(file_path)
        else:
            error_msg = f"Неподдерживаемый формат файла: {extension}. Используйте CSV или XLSX."
            logger.error(error_msg)
            return [], [error_msg]

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
                parameters=parameters,
                location=location,
                surface_location=surface_location,
                distance_to_weld_m=distance_to_weld_m,
                erf_b31g_code=erf_b31g_code,
                pipeline_id=f"MT-{segment_number:02d}",
                source_file=Path(source_file).name  # Сохраняем имя исходного файла
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
        """Парсит все CSV и XLSX файлы в директории data/
        
        Returns:
            Tuple[List[Defect], List[str]]: Все дефекты и ошибки
        """
        all_defects = []
        all_errors = []
        
        # Ищем CSV и XLSX файлы в корне data/ и в data/CSV/
        file_patterns = [
            (self.data_dir, '*.csv'),
            (self.data_dir, '*.xlsx'),
            (self.data_dir, '*.xls'),
            (self.data_dir / 'CSV', '*.csv'),
            (self.data_dir / 'CSV', '*.xlsx'),
            (self.data_dir / 'CSV', '*.xls'),
        ]
        
        data_files = []
        for directory, pattern in file_patterns:
            if directory.exists():
                data_files.extend(directory.glob(pattern))
        
        if not data_files:
            logger.warning(f"Файлы данных не найдены в {self.data_dir}")
            return all_defects, ["Файлы данных (CSV/XLSX) не найдены"]
        
        logger.info(f"Найдено {len(data_files)} файлов для парсинга")
        
        for data_file in data_files:
            defects, errors = self.parse_file(str(data_file))
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
