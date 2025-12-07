from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse
import tempfile
import json
import logging
from datetime import datetime
from typing import List, Optional
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Reports"])

REPORTS_HISTORY = []
REPORTS_DIR = "/tmp/reports"

os.makedirs(REPORTS_DIR, exist_ok=True)


def save_report_metadata(filename: str, report_type: str, format: str):
    metadata = {
        "name": filename,
        "type": report_type,
        "format": format,
        "date": datetime.now().isoformat(),
        "filepath": os.path.join(REPORTS_DIR, filename)
    }
    REPORTS_HISTORY.append(metadata)
    if len(REPORTS_HISTORY) > 10:
        old_report = REPORTS_HISTORY.pop(0)
        try:
            if os.path.exists(old_report["filepath"]):
                os.remove(old_report["filepath"])
        except Exception as e:
            logger.warning(f"Could not delete old report: {str(e)}")


def get_defect_value(d, field, default=None):
    try:
        if field == 'latitude':
            if hasattr(d, 'location') and d.location:
                return getattr(d.location, 'latitude', default)
            return default
        elif field == 'longitude':
            if hasattr(d, 'location') and d.location:
                return getattr(d.location, 'longitude', default)
            return default
        elif field == 'severity':
            val = getattr(d, 'severity', default)
            if val is None:
                return default
            if hasattr(val, 'value'):
                return val.value
            return str(val)
        elif field == 'defect_type':
            val = getattr(d, 'defect_type', default)
            if val is None:
                return default
            if hasattr(val, 'value'):
                return val.value
            return str(val)
        elif field == 'erf_b31g_code':
            val = getattr(d, 'erf_b31g_code', None)
            if val is not None:
                return val
            if hasattr(d, 'parameters') and d.parameters:
                return getattr(d.parameters, 'erf_b31g_code', default)
            return default
        else:
            return getattr(d, field, default)
    except Exception:
        return default


def generate_html_report(report_type: str, defects: list = None, stats: dict = None) -> str:
    
    defects = defects or []
    stats = stats or {}
    
    title_map = {
        "summary": "Общая статистика",
        "defects": "Таблица дефектов",
        "excavations": "Рекомендуемые раскопки",
        "map": "Карта участка"
    }
    
    title = title_map.get(report_type, "Отчет")
    
    total_defects = len(defects)
    high_severity = len([d for d in defects if get_defect_value(d, 'severity') == 'high'])
    medium_severity = len([d for d in defects if get_defect_value(d, 'severity') == 'medium'])
    normal_severity = len([d for d in defects if get_defect_value(d, 'severity') == 'normal'])
    
    pipelines = set()
    for d in defects:
        pid = get_defect_value(d, 'pipeline_id')
        if pid:
            pipelines.add(pid)
    
    defect_types = {}
    for d in defects:
        dtype = get_defect_value(d, 'defect_type', 'Неизвестно')
        defect_types[dtype] = defect_types.get(dtype, 0) + 1
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f5f5f5;
                padding: 20px;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                padding: 40px;
            }}
            .header {{
                text-align: center;
                border-bottom: 3px solid #1e3a8a;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }}
            .header h1 {{
                color: #1e3a8a;
                font-size: 32px;
                margin-bottom: 10px;
            }}
            .header p {{
                color: #666;
                font-size: 14px;
            }}
            .report-date {{
                margin-top: 10px;
                font-size: 12px;
                color: #999;
            }}
            .section {{
                margin-bottom: 30px;
            }}
            .section h2 {{
                color: #1e3a8a;
                font-size: 20px;
                margin-bottom: 15px;
                border-left: 4px solid #3b82f6;
                padding-left: 10px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
            }}
            th {{
                background-color: #e0e7ff;
                color: #1e3a8a;
                padding: 12px;
                text-align: left;
                font-weight: 600;
                border-bottom: 2px solid #3b82f6;
            }}
            td {{
                padding: 10px 12px;
                border-bottom: 1px solid #e5e7eb;
            }}
            tr:hover {{
                background-color: #f9fafb;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }}
            .stat-card {{
                background: linear-gradient(135deg, #e0e7ff 0%, #f3f4f6 100%);
                padding: 20px;
                border-radius: 8px;
                border-left: 4px solid #3b82f6;
            }}
            .stat-card.high {{
                border-left-color: #ef4444;
            }}
            .stat-card.medium {{
                border-left-color: #f59e0b;
            }}
            .stat-card.normal {{
                border-left-color: #22c55e;
            }}
            .stat-value {{
                font-size: 28px;
                font-weight: bold;
                color: #1e3a8a;
            }}
            .stat-label {{
                font-size: 12px;
                color: #666;
                margin-top: 5px;
            }}
            .footer {{
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #e5e7eb;
                text-align: center;
                color: #999;
                font-size: 12px;
            }}
            .defect-item {{
                background-color: #f9fafb;
                padding: 15px;
                margin-bottom: 10px;
                border-radius: 6px;
                border-left: 4px solid #ef4444;
            }}
            .defect-item.medium {{
                border-left-color: #f59e0b;
            }}
            .defect-item.normal {{
                border-left-color: #22c55e;
            }}
            .defect-item h3 {{
                color: #1e3a8a;
                margin-bottom: 5px;
            }}
            .defect-item p {{
                color: #666;
                font-size: 13px;
                line-height: 1.5;
            }}
            .severity-high {{ color: #ef4444; font-weight: bold; }}
            .severity-medium {{ color: #f59e0b; font-weight: bold; }}
            .severity-normal {{ color: #22c55e; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{title}</h1>
                <p>Автоматически сгенерированный отчет системы IntegrityOS</p>
                <div class="report-date">Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</div>
            </div>
    """
    
    if report_type == "summary":
        html_content += f"""
            <div class="section">
                <h2>Статистика по объектам</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{len(pipelines)}</div>
                        <div class="stat-label">Всего трубопроводов</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{total_defects}</div>
                        <div class="stat-label">Дефектов обнаружено</div>
                    </div>
                    <div class="stat-card high">
                        <div class="stat-value">{high_severity}</div>
                        <div class="stat-label">Критических дефектов</div>
                    </div>
                    <div class="stat-card medium">
                        <div class="stat-value">{medium_severity}</div>
                        <div class="stat-label">Средней критичности</div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2>Распределение по типам дефектов</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Тип дефекта</th>
                            <th>Количество</th>
                            <th>Процент</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        for dtype, count in sorted(defect_types.items(), key=lambda x: -x[1]):
            percent = (count / total_defects * 100) if total_defects > 0 else 0
            html_content += f"""
                        <tr>
                            <td>{dtype}</td>
                            <td>{count}</td>
                            <td>{percent:.1f}%</td>
                        </tr>
            """
        if not defect_types:
            html_content += """
                        <tr>
                            <td colspan="3" style="text-align: center; color: #999;">Нет данных</td>
                        </tr>
            """
        html_content += """
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <h2>Распределение по критичности</h2>
                <div class="stats-grid">
                    <div class="stat-card high">
                        <div class="stat-value">{high}</div>
                        <div class="stat-label">Высокая (требует немедленного вмешательства)</div>
                    </div>
                    <div class="stat-card medium">
                        <div class="stat-value">{medium}</div>
                        <div class="stat-label">Средняя (требует мониторинга)</div>
                    </div>
                    <div class="stat-card normal">
                        <div class="stat-value">{normal}</div>
                        <div class="stat-label">Нормальная (низкий риск)</div>
                    </div>
                </div>
            </div>
        """.format(high=high_severity, medium=medium_severity, normal=normal_severity)
        
    elif report_type == "defects":
        html_content += f"""
            <div class="section">
                <h2>Таблица всех дефектов ({total_defects} записей)</h2>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Трубопровод</th>
                            <th>Тип дефекта</th>
                            <th>Критичность</th>
                            <th>Дистанция (м)</th>
                            <th>Координаты</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        for d in defects[:100]:  
            defect_id = get_defect_value(d, 'defect_id', '-')
            defect_id = defect_id[:8] if defect_id and defect_id != '-' else '-'
            pipeline = get_defect_value(d, 'pipeline_id', '-')
            dtype = get_defect_value(d, 'defect_type', '-')
            severity = get_defect_value(d, 'severity', '-')
            distance = get_defect_value(d, 'measurement_distance_m', '-')
            lat = get_defect_value(d, 'latitude')
            lon = get_defect_value(d, 'longitude')
            coords = f"{lat:.4f}, {lon:.4f}" if lat and lon else '-'
            
            severity_class = f"severity-{severity}" if severity in ['high', 'medium', 'normal'] else ''
            severity_text = {'high': 'Высокая', 'medium': 'Средняя', 'normal': 'Нормальная'}.get(severity, severity)
            
            html_content += f"""
                        <tr>
                            <td>{defect_id}...</td>
                            <td>{pipeline}</td>
                            <td>{dtype}</td>
                            <td class="{severity_class}">{severity_text}</td>
                            <td>{distance}</td>
                            <td>{coords}</td>
                        </tr>
            """
        if not defects:
            html_content += """
                        <tr>
                            <td colspan="6" style="text-align: center; color: #999;">Нет данных о дефектах</td>
                        </tr>
            """
        if len(defects) > 100:
            html_content += f"""
                        <tr>
                            <td colspan="6" style="text-align: center; color: #666; font-style: italic;">
                                ... и еще {len(defects) - 100} записей. Для полного списка используйте экспорт в JSON.
                            </td>
                        </tr>
            """
        html_content += """
                    </tbody>
                </table>
            </div>
        """
        
    elif report_type == "excavations":
        excavation_defects = [d for d in defects if get_defect_value(d, 'severity') == 'high']
        
        html_content += f"""
            <div class="section">
                <h2>Рекомендуемые раскопки</h2>
                <p>Список участков, рекомендованных для раскопок на основе анализа ML модели. 
                   Всего рекомендаций: <strong>{len(excavation_defects)}</strong></p>
                <div style="margin-top: 15px;">
        """
        for i, d in enumerate(excavation_defects[:20], 1):
            pipeline = get_defect_value(d, 'pipeline_id', 'Неизвестно')
            dtype = get_defect_value(d, 'defect_type', 'Неизвестно')
            distance = get_defect_value(d, 'measurement_distance_m', '-')
            lat = get_defect_value(d, 'latitude')
            lon = get_defect_value(d, 'longitude')
            coords = f"{lat:.4f}, {lon:.4f}" if lat and lon else 'Неизвестно'
            erf = get_defect_value(d, 'erf_b31g_code')
            erf_text = f"{erf:.2f}" if erf else '-'
            
            html_content += f"""
                    <div class="defect-item">
                        <h3>#{i}. Участок {pipeline} - {dtype}</h3>
                        <p><strong>Приоритет:</strong> Высокий | <strong>ERF код:</strong> {erf_text}</p>
                        <p><strong>Дистанция:</strong> {distance} м | <strong>Координаты:</strong> {coords}</p>
                    </div>
            """
        if not excavation_defects:
            html_content += """
                    <div style="text-align: center; padding: 40px; color: #666;">
                        <p>Нет участков, требующих немедленного вмешательства.</p>
                        <p>Все дефекты имеют нормальный или средний уровень критичности.</p>
                    </div>
            """
        if len(excavation_defects) > 20:
            html_content += f"""
                    <p style="text-align: center; color: #666; margin-top: 20px;">
                        ... и еще {len(excavation_defects) - 20} рекомендаций
                    </p>
            """
        html_content += """
                </div>
            </div>
        """
        
    elif report_type == "map":
        lats = [get_defect_value(d, 'latitude') for d in defects]
        lats = [lat for lat in lats if lat is not None]
        lons = [get_defect_value(d, 'longitude') for d in defects]
        lons = [lon for lon in lons if lon is not None]
        
        if lats and lons:
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)
        else:
            center_lat, center_lon = 48.0, 68.0
            min_lat, max_lat = 0, 0
            min_lon, max_lon = 0, 0
        
        html_content += f"""
            <div class="section">
                <h2>Информация о карте</h2>
                <p>Географическое распределение дефектов на трубопроводах Казахстана:</p>
                <table>
                    <thead>
                        <tr>
                            <th>Параметр</th>
                            <th>Значение</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Всего точек на карте</td>
                            <td>{len(lats)}</td>
                        </tr>
                        <tr>
                            <td>Центр координат</td>
                            <td>{center_lat:.4f}°N, {center_lon:.4f}°E</td>
                        </tr>
                        <tr>
                            <td>Широта (мин - макс)</td>
                            <td>{min_lat:.4f}° - {max_lat:.4f}°</td>
                        </tr>
                        <tr>
                            <td>Долгота (мин - макс)</td>
                            <td>{min_lon:.4f}° - {max_lon:.4f}°</td>
                        </tr>
                        <tr>
                            <td>Количество трубопроводов</td>
                            <td>{len(pipelines)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <h2>Трубопроводы в системе</h2>
                <table>
                    <thead>
                        <tr>
                            <th>ID трубопровода</th>
                            <th>Количество дефектов</th>
                            <th>Критических</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        for pipeline in sorted(pipelines):
            pipeline_defects = [d for d in defects if get_defect_value(d, 'pipeline_id') == pipeline]
            pipeline_high = len([d for d in pipeline_defects if get_defect_value(d, 'severity') == 'high'])
            html_content += f"""
                        <tr>
                            <td>{pipeline}</td>
                            <td>{len(pipeline_defects)}</td>
                            <td class="severity-high">{pipeline_high}</td>
                        </tr>
            """
        if not pipelines:
            html_content += """
                        <tr>
                            <td colspan="3" style="text-align: center; color: #999;">Нет данных</td>
                        </tr>
            """
        html_content += """
                    </tbody>
                </table>
            </div>
        """
    
    html_content += """
            <div class="footer">
                <p>Этот отчет был автоматически сгенерирован системой IntegrityOS</p>
                <p>IntegrityOS</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content


def generate_pdf_report(report_type: str, defects: list = None, stats: dict = None, filepath: str = None):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    
    defects = defects or []
    
    font_name = 'Helvetica' 
    font_name_bold = 'Helvetica-Bold'
    
    font_paths = [
        '/System/Library/Fonts/Supplemental/Arial.ttf',  
        '/System/Library/Fonts/Helvetica.ttc', 
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', 
        'C:/Windows/Fonts/arial.ttf', 
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('CustomFont', font_path))
                font_name = 'CustomFont'
                font_name_bold = 'CustomFont'
                logger.info(f"Registered font from {font_path}")
                break
            except Exception as e:
                logger.warning(f"Could not register font {font_path}: {e}")
    
    doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=font_name_bold,
        fontSize=20,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=12,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontName=font_name_bold,
        fontSize=14,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=6
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10
    )
    
    story = []
    
    title_map = {
        "summary": "Общая статистика",
        "defects": "Таблица дефектов", 
        "excavations": "Рекомендуемые раскопки",
        "map": "Карта участка"
    }
    
    title = title_map.get(report_type, "Отчет")
    
    total_defects = len(defects)
    high_severity = len([d for d in defects if get_defect_value(d, 'severity') == 'high'])
    medium_severity = len([d for d in defects if get_defect_value(d, 'severity') == 'medium'])
    normal_severity = len([d for d in defects if get_defect_value(d, 'severity') == 'normal'])
    
    pipelines = set()
    for d in defects:
        pid = get_defect_value(d, 'pipeline_id')
        if pid:
            pipelines.add(pid)
    
    story.append(Paragraph("IntegrityOS - Система мониторинга трубопроводов", title_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(title, heading_style))
    story.append(Paragraph(
        f"Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        normal_style
    ))
    story.append(Spacer(1, 0.3*inch))
    
    if report_type == "summary":
        story.append(Paragraph("Общая информация", heading_style))
        data = [
            ['Параметр', 'Значение'],
            ['Всего трубопроводов', str(len(pipelines))],
            ['Всего дефектов', str(total_defects)],
            ['Критических (high)', str(high_severity)],
            ['Средних (medium)', str(medium_severity)],
            ['Нормальных (normal)', str(normal_severity)]
        ]
        
        table = Table(data, colWidths=[200, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e7ff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTNAME', (0, 0), (-1, 0), font_name_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9fafb')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb'))
        ]))
        story.append(table)
        story.append(Spacer(1, 0.3*inch))
        
        defect_types = {}
        for d in defects:
            dtype = get_defect_value(d, 'defect_type', 'Неизвестно')
            defect_types[dtype] = defect_types.get(dtype, 0) + 1
        
        if defect_types:
            story.append(Paragraph("Распределение по типам дефектов", heading_style))
            type_data = [['Тип дефекта', 'Количество', 'Процент']]
            for dtype, count in sorted(defect_types.items(), key=lambda x: -x[1]):
                percent = (count / total_defects * 100) if total_defects > 0 else 0
                type_data.append([str(dtype), str(count), f"{percent:.1f}%"])
            
            type_table = Table(type_data, colWidths=[200, 80, 80])
            type_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e7ff')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), font_name),
                ('FONTNAME', (0, 0), (-1, 0), font_name_bold),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9fafb')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb'))
            ]))
            story.append(type_table)
    
    elif report_type == "defects":
        story.append(Paragraph(f"Список дефектов ({total_defects} записей)", heading_style))
        
        data = [['ID', 'Трубопровод', 'Тип', 'Критичность', 'Дистанция']]
        
        for d in defects[:50]: 
            defect_id = get_defect_value(d, 'defect_id', '-')
            defect_id = defect_id[:8] if defect_id and defect_id != '-' else '-'
            pipeline = get_defect_value(d, 'pipeline_id', '-')
            dtype = get_defect_value(d, 'defect_type', '-')
            dtype_str = str(dtype)[:15] if dtype else '-'
            severity = get_defect_value(d, 'severity', '-')
            severity_text = {'high': 'Высокая', 'medium': 'Средняя', 'normal': 'Норм.'}.get(severity, str(severity))
            distance = get_defect_value(d, 'measurement_distance_m', '-')
            if isinstance(distance, (int, float)):
                distance = f"{distance:.1f} м"
            
            data.append([defect_id, str(pipeline), dtype_str, severity_text, str(distance)])
        
        if not defects:
            data.append(['', 'Нет данных', '', '', ''])
        
        table = Table(data, colWidths=[60, 80, 100, 70, 70])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e7ff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTNAME', (0, 0), (-1, 0), font_name_bold),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9fafb')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb'))
        ]))
        story.append(table)
        
        if len(defects) > 50:
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph(
                f"... и еще {len(defects) - 50} записей. Для полного списка используйте экспорт в JSON.",
                normal_style
            ))
    
    elif report_type == "excavations":
        excavation_defects = [d for d in defects if get_defect_value(d, 'severity') == 'high']
        
        story.append(Paragraph(f"Рекомендуемые раскопки ({len(excavation_defects)} участков)", heading_style))
        story.append(Paragraph(
            "Участки с критическим уровнем дефектов, требующие немедленного вмешательства:",
            normal_style
        ))
        story.append(Spacer(1, 0.2*inch))
        
        data = [['#', 'Трубопровод', 'Тип дефекта', 'Дистанция', 'Координаты']]
        
        for i, d in enumerate(excavation_defects[:30], 1):
            pipeline = get_defect_value(d, 'pipeline_id', '-')
            dtype = get_defect_value(d, 'defect_type', '-')
            dtype_str = str(dtype)[:15] if dtype else '-'
            distance = get_defect_value(d, 'measurement_distance_m', '-')
            if isinstance(distance, (int, float)):
                distance = f"{distance:.1f} м"
            lat = get_defect_value(d, 'latitude')
            lon = get_defect_value(d, 'longitude')
            coords = f"{lat:.2f}, {lon:.2f}" if lat and lon else '-'
            
            data.append([str(i), str(pipeline), dtype_str, str(distance), coords])
        
        if not excavation_defects:
            data.append(['', 'Нет критических дефектов', '', '', ''])
        
        table = Table(data, colWidths=[30, 80, 120, 70, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#fee2e2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#991b1b')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTNAME', (0, 0), (-1, 0), font_name_bold),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fef2f2')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#fecaca'))
        ]))
        story.append(table)
    
    elif report_type == "map":
        lats = [get_defect_value(d, 'latitude') for d in defects]
        lats = [lat for lat in lats if lat is not None]
        lons = [get_defect_value(d, 'longitude') for d in defects]
        lons = [lon for lon in lons if lon is not None]
        
        if lats and lons:
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)
        else:
            center_lat, center_lon = 48.0, 68.0
            min_lat, max_lat, min_lon, max_lon = 0, 0, 0, 0
        
        story.append(Paragraph("Географическое распределение", heading_style))
        
        data = [
            ['Параметр', 'Значение'],
            ['Всего точек', str(len(lats))],
            ['Центр (широта)', f"{center_lat:.4f}"],
            ['Центр (долгота)', f"{center_lon:.4f}"],
            ['Диапазон широты', f"{min_lat:.4f} - {max_lat:.4f}"],
            ['Диапазон долготы', f"{min_lon:.4f} - {max_lon:.4f}"],
            ['Трубопроводов', str(len(pipelines))]
        ]
        
        table = Table(data, colWidths=[150, 200])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e7ff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTNAME', (0, 0), (-1, 0), font_name_bold),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9fafb')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb'))
        ]))
        story.append(table)
        
        if pipelines:
            story.append(Spacer(1, 0.3*inch))
            story.append(Paragraph("Статистика по трубопроводам", heading_style))
            
            pipe_data = [['Трубопровод', 'Дефектов', 'Критических']]
            for pipeline in sorted(pipelines):
                pipeline_defects = [d for d in defects if get_defect_value(d, 'pipeline_id') == pipeline]
                pipeline_high = len([d for d in pipeline_defects if get_defect_value(d, 'severity') == 'high'])
                pipe_data.append([pipeline, str(len(pipeline_defects)), str(pipeline_high)])
            
            pipe_table = Table(pipe_data, colWidths=[150, 100, 100])
            pipe_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e7ff')),
                ('FONTNAME', (0, 0), (-1, -1), font_name),
                ('FONTNAME', (0, 0), (-1, 0), font_name_bold),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9fafb')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb'))
            ]))
            story.append(pipe_table)
    
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(
        "Отчет сгенерирован системой IntegrityOS. PromTech Hackathon",
        ParagraphStyle('Footer', parent=normal_style, fontSize=8, textColor=colors.gray)
    ))
    
    doc.build(story)


@router.get("/generate")
async def generate_report(
    report_type: str = Query("summary", description="Type of report: summary, defects, excavations, map"),
    format: str = Query("html", description="Output format: html or pdf"),
    defects_repository=None
):    
    try:
        if report_type not in ["summary", "defects", "excavations", "map"]:
            raise HTTPException(status_code=400, detail="Invalid report type")
        
        if format not in ["html", "pdf"]:
            raise HTTPException(status_code=400, detail="Invalid format. Use 'html' or 'pdf'")
        
        defects = []
        if defects_repository:
            try:
                defects = defects_repository.get_all_defects() or []
                logger.info(f"Loaded {len(defects)} defects for report")
            except Exception as e:
                logger.warning(f"Could not load defects: {e}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Report_{report_type}_{timestamp}.{format}"
        filepath = os.path.join(REPORTS_DIR, filename)
        
        if format == "html":
            html_content = generate_html_report(report_type, defects)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            save_report_metadata(filename, report_type, "HTML")
            
            return FileResponse(
                path=filepath,
                filename=filename,
                media_type='text/html',
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        
        elif format == "pdf":
            try:
                generate_pdf_report(report_type, defects, filepath=filepath)
                save_report_metadata(filename, report_type, "PDF")
                
                return FileResponse(
                    path=filepath,
                    filename=filename,
                    media_type='application/pdf',
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            except ImportError as e:
                logger.error(f"reportlab not available: {e}")
                raise HTTPException(status_code=500, detail="PDF generation not available. Install reportlab.")
            except Exception as e:
                logger.error(f"PDF generation error: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@router.get("/history")
async def get_reports_history():
    try:
        history_with_urls = []
        for report in REPORTS_HISTORY:
            report_copy = report.copy()
            report_copy["url"] = f"/api/reports/download?filename={os.path.basename(report['filepath'])}"
            report_copy["displayDate"] = datetime.fromisoformat(report["date"]).strftime('%d.%m.%Y %H:%M')
            history_with_urls.append(report_copy)
        
        return {"reports": history_with_urls}
    except Exception as e:
        logger.error(f"Error fetching reports history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download")
async def download_report(filename: str = Query(..., description="Report filename")):
    try:
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        filepath = os.path.join(REPORTS_DIR, filename)
        
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="Report not found")
        
        if filename.endswith('.pdf'):
            media_type = 'application/pdf'
        elif filename.endswith('.html'):
            media_type = 'text/html'
        else:
            media_type = 'application/octet-stream'
        
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
