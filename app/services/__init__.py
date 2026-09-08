"""
Пакет сервисов АРМ Старосты.
"""
from app.services.geo_service import haversine_distance, validate_checkin_location
from app.services.excel_generator import generate_dean_report_xlsx
from app.services.import_service import (
    export_students_to_xlsx,
    generate_schedule_template_xlsx,
    generate_students_template_xlsx,
    parse_schedule_excel,
    parse_students_csv,
    parse_students_excel,
    parse_students_file,
    parse_students_text,
    parse_students_xlsx,
    save_imported_schedule,
    save_imported_students,
)
from app.services.scheduler_service import (
    start_scheduler,
    stop_scheduler,
    send_saturday_dean_report,
)

__all__ = [
    "haversine_distance",
    "validate_checkin_location",
    "generate_dean_report_xlsx",
    "export_students_to_xlsx",
    "generate_schedule_template_xlsx",
    "generate_students_template_xlsx",
    "parse_schedule_excel",
    "parse_students_csv",
    "parse_students_excel",
    "parse_students_file",
    "parse_students_text",
    "parse_students_xlsx",
    "save_imported_schedule",
    "save_imported_students",
    "start_scheduler",
    "stop_scheduler",
    "send_saturday_dean_report",
]
