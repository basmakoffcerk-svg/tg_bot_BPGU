"""
Тесты модуля импорта и экспорта списков студентов (app/services/import_service.py).
"""
import pytest
from app.services.import_service import (
    export_students_to_xlsx,
    generate_students_template_xlsx,
    parse_students_csv,
    parse_students_text,
    parse_students_xlsx,
)
from app.models import Student


def test_parse_students_text_valid():
    text_data = """
    Иванов Иван Иванович 1
    Петров Петр 2
    Сидорова Анна Сергеевна 1
    """
    students, errors = parse_students_text(text_data)
    assert len(errors) == 0
    assert len(students) == 3
    assert students[0]["full_name"] == "Иванов Иван Иванович"
    assert students[0]["subgroup"] == 1
    assert students[1]["full_name"] == "Петров Петр"
    assert students[1]["subgroup"] == 2
    assert students[2]["subgroup"] == 1


def test_parse_students_text_with_commas():
    text_data = """
    Иванов Иван, 1 подгруппа
    Петров Петр, 2
    """
    students, errors = parse_students_text(text_data)
    assert len(students) == 2
    assert students[0]["subgroup"] == 1
    assert students[1]["subgroup"] == 2


def test_parse_students_csv():
    csv_content = """ФИО,Подгруппа,Роль
Иванов Иван Иванович,1,Староста
Петров Петр Петрович,2,Студент
Сидоров Сидор,1,Зам
""".encode("utf-8")

    students, errors = parse_students_csv(csv_content)
    assert len(errors) == 0
    assert len(students) == 3
    assert students[0]["role"] == "STAROSTA"
    assert students[1]["role"] == "STUDENT"
    assert students[2]["role"] == "ZAM"


def test_generate_and_parse_template_xlsx():
    # Генерируем шаблон
    template_bytes = generate_students_template_xlsx()
    assert len(template_bytes) > 0

    # Пробуем распарсить обратно
    students, errors = parse_students_xlsx(template_bytes)
    assert len(errors) == 0
    assert len(students) >= 4
    assert any("Иванов" in s["full_name"] for s in students)


def test_export_students_to_xlsx():
    mock_students = [
        Student(id=1, full_name="Иванов И.И.", subgroup=1, role="STAROSTA", telegram_id=12345),
        Student(id=2, full_name="Петров П.П.", subgroup=2, role="STUDENT", telegram_id=None),
    ]
    xlsx_bytes = export_students_to_xlsx(mock_students)
    assert len(xlsx_bytes) > 0
    assert xlsx_bytes[:4] == b"PK\x03\x04"  # Сигнатура ZIP / XLSX
