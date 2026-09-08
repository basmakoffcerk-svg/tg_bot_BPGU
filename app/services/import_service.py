"""
Модуль импорта и экспорта списков студентов и расписания.
Поддерживает форматы Excel (.xlsx), CSV (.csv) и сырой текст (копипаст).
"""
import csv
from io import BytesIO, StringIO
from typing import Any, Dict, List, Optional, Tuple
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Student, Subject, ScheduleSlot, ROLE_STUDENT, ROLE_ZAM, ROLE_STAROSTA


def parse_students_text(text_content: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Парсит список студентов из обычного текста.
    Примеры строк:
    - Иванов Иван Иванович 1
    - Петров Петр 2
    - Сидорова Анна Сергеевна, 1 подгруппа
    """
    students = []
    errors = []
    lines = [line.strip() for line in text_content.strip().split("\n") if line.strip()]

    for idx, line in enumerate(lines, start=1):
        cleaned = line.replace(",", " ").replace(";", " ")
        parts = [p.strip() for p in cleaned.split() if p.strip()]

        if len(parts) < 2:
            errors.append(f"Строка {idx}: '{line}' — слишком короткая (нужно ФИО и подгруппа).")
            continue

        subgroup = 1
        if parts[-1] in ("1", "2"):
            subgroup = int(parts.pop())
        elif "1" in parts[-1]:
            subgroup = 1
            parts.pop()
        elif "2" in parts[-1]:
            subgroup = 2
            parts.pop()

        full_name = " ".join(parts)
        if len(full_name) < 3:
            errors.append(f"Строка {idx}: '{line}' — неверное имя студента.")
            continue

        students.append({
            "full_name": full_name,
            "subgroup": subgroup,
            "role": ROLE_STUDENT,
        })

    return students, errors


def parse_students_csv(csv_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Парсит список студентов из файла CSV."""
    students = []
    errors = []
    try:
        text_data = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text_data = csv_bytes.decode("cp1251")
        except Exception as e:
            return [], [f"Ошибка кодировки файла: {e}. Используйте UTF-8."]

    reader = csv.reader(StringIO(text_data), delimiter="," if "," in text_data else ";")
    header = None

    for idx, row in enumerate(reader, start=1):
        if not row or not any(cell.strip() for cell in row):
            continue

        clean_row = [c.strip() for c in row]
        if header is None:
            first_col = clean_row[0].lower()
            if "фио" in first_col or "имя" in first_col or "студент" in first_col or "name" in first_col:
                header = clean_row
                continue
            else:
                header = ["фио", "подгруппа"]

        full_name = clean_row[0]
        if not full_name:
            continue

        subgroup = 1
        if len(clean_row) > 1 and clean_row[1]:
            try:
                subgroup = int(clean_row[1].replace("п/г", "").strip())
                if subgroup not in (1, 2):
                    subgroup = 1
            except ValueError:
                subgroup = 1

        role = ROLE_STUDENT
        if len(clean_row) > 2 and clean_row[2]:
            role_raw = clean_row[2].upper()
            if "СТАРОСТА" in role_raw or "STAROSTA" in role_raw:
                role = ROLE_STAROSTA
            elif "ЗАМ" in role_raw or "ZAM" in role_raw:
                role = ROLE_ZAM

        students.append({
            "full_name": full_name,
            "subgroup": subgroup,
            "role": role,
        })

    return students, errors


def parse_students_xlsx(xlsx_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Парсит список студентов из файла Excel (.xlsx)."""
    students = []
    errors = []

    try:
        wb = openpyxl.load_workbook(BytesIO(xlsx_bytes), data_only=True)
        ws = wb.active
    except Exception as e:
        return [], [f"Ошибка чтения Excel: {e}"]

    fio_col = 2
    subgroup_col = 3
    role_col = 4
    start_row = 2
    header_found = False

    for row in range(1, min(5, ws.max_row + 1)):
        for col in range(1, min(10, ws.max_column + 1)):
            val = str(ws.cell(row=row, column=col).value or "").lower().strip()
            if "фио" in val or "fio" in val or val == "имя":
                fio_col = col
                header_found = True
            elif "подгруппа" in val or "п/г" in val:
                subgroup_col = col
            elif "роль" in val or "должность" in val:
                role_col = col
        if header_found:
            start_row = row + 1
            break

    for row in range(start_row, ws.max_row + 1):
        fio_val = ws.cell(row=row, column=fio_col).value
        if not fio_val:
            continue

        full_name = str(fio_val).strip()
        if len(full_name) < 3 or full_name.lower() in ("фио", "студент", "имя"):
            continue

        subgroup = 1
        subg_val = ws.cell(row=row, column=subgroup_col).value
        if subg_val:
            try:
                subgroup = int(str(subg_val).strip())
                if subgroup not in (1, 2):
                    subgroup = 1
            except ValueError:
                subgroup = 1

        role = ROLE_STUDENT
        role_val = ws.cell(row=row, column=role_col).value
        if role_val:
            r_str = str(role_val).upper()
            if "СТАРОСТА" in r_str:
                role = ROLE_STAROSTA
            elif "ЗАМ" in r_str:
                role = ROLE_ZAM

        students.append({
            "full_name": full_name,
            "subgroup": subgroup,
            "role": role,
        })

    return students, errors


# Алиасы для обратной совместимости
parse_students_excel = parse_students_xlsx


def parse_students_file(file_bytes: bytes, filename: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Универсальный парсер файла со списком студентов (.xlsx или .csv)."""
    fn = filename.lower()
    if fn.endswith(".xlsx"):
        return parse_students_xlsx(file_bytes)
    elif fn.endswith(".csv"):
        return parse_students_csv(file_bytes)
    return [], [f"Неподдерживаемый формат: {filename}. Требуется .xlsx или .csv"]


def generate_students_template_xlsx() -> bytes:
    """Генерирует пустой шаблон Excel для заполнения списка студентов старостой."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Студенты"

    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fill_header = PatternFill(start_color="2481CC", end_color="2481CC", fill_type="solid")
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="D0D0D0"),
        right=Side(style="thin", color="D0D0D0"),
        top=Side(style="thin", color="D0D0D0"),
        bottom=Side(style="thin", color="D0D0D0"),
    )

    headers = ["№", "ФИО Студента", "Подгруппа (1 или 2)", "Роль (Студент / Зам / Староста)"]
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_center
        cell.border = thin_border

    samples = [
        (1, "Иванов Иван Иванович", 1, "Староста"),
        (2, "Константинов Константин Константинович", 2, "Зам"),
        (3, "Алексеев Алексей Алексеевич", 1, "Студент"),
        (4, "Богданова Анна Сергеевна", 2, "Студент"),
    ]

    for row_idx, sample in enumerate(samples, start=2):
        for col_idx, val in enumerate(sample, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = thin_border
            cell.alignment = align_left if col_idx == 2 else align_center

    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 24
    ws.column_dimensions["D"].width = 30

    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def generate_schedule_template_xlsx() -> bytes:
    """Генерирует шаблон Excel для заполнения расписания."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Расписание"

    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fill_header = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="D0D0D0"),
        right=Side(style="thin", color="D0D0D0"),
        top=Side(style="thin", color="D0D0D0"),
        bottom=Side(style="thin", color="D0D0D0"),
    )

    headers = [
        "День недели (1..6)",
        "Четность (ALL/ODD/EVEN)",
        "Пара (1..6)",
        "Начало (HH:MM)",
        "Конец (HH:MM)",
        "Предмет",
        "Преподаватель",
        "Тип (LECTURE/PRACTICE/LAB)",
        "Подгруппа (0/1/2)",
        "Корпус",
        "Аудитория",
        "Широта корпуса",
        "Долгота корпуса",
        "Радиус (м)",
    ]

    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_center
        cell.border = thin_border

    sample = [
        1, "ALL", 1, "08:30", "10:00",
        "Математический анализ", "проф. Сидоров В.П.", "LECTURE",
        0, "Корпус 1 БГПУ", "304", 53.894510, 27.544720, 150
    ]

    for col_idx, val in enumerate(sample, start=1):
        cell = ws.cell(row=2, column=col_idx, value=val)
        cell.border = thin_border
        cell.alignment = align_center

    for col in range(1, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 18

    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def parse_schedule_excel(xlsx_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Парсит расписание занятий из файла Excel."""
    items = []
    errors = []

    try:
        wb = openpyxl.load_workbook(BytesIO(xlsx_bytes), data_only=True)
        ws = wb.active
    except Exception as e:
        return [], [f"Ошибка чтения Excel расписания: {e}"]

    for row in range(2, ws.max_row + 1):
        dow_val = ws.cell(row=row, column=1).value
        if not dow_val:
            continue

        try:
            dow = int(dow_val)
            week_type = str(ws.cell(row=row, column=2).value or "ALL").upper()
            pair_num = int(ws.cell(row=row, column=3).value or 1)
            t_start = str(ws.cell(row=row, column=4).value or "08:30").strip()
            t_end = str(ws.cell(row=row, column=5).value or "10:00").strip()
            subject_title = str(ws.cell(row=row, column=6).value or "").strip()
            teacher = str(ws.cell(row=row, column=7).value or "").strip()
            stype = str(ws.cell(row=row, column=8).value or "LECTURE").upper()
            subg = int(ws.cell(row=row, column=9).value or 0)
            building = str(ws.cell(row=row, column=10).value or "Корпус 1 БГПУ").strip()
            room = str(ws.cell(row=row, column=11).value or "").strip()
            lat = float(ws.cell(row=row, column=12).value or 53.894510)
            lon = float(ws.cell(row=row, column=13).value or 27.544720)
            radius = int(ws.cell(row=row, column=14).value or 150)

            items.append({
                "day_of_week": dow,
                "week_type": week_type,
                "pair_number": pair_num,
                "time_start": t_start,
                "time_end": t_end,
                "subject_title": subject_title,
                "teacher_name": teacher,
                "subject_type": stype,
                "subgroup": subg,
                "building_name": building,
                "room_number": room,
                "building_lat": lat,
                "building_lon": lon,
                "radius_meters": radius,
            })
        except Exception as e:
            errors.append(f"Строка {row}: ошибка разбора ({e})")

    return items, errors


parse_schedule_xlsx = parse_schedule_excel


def export_students_to_xlsx(students: List[Student]) -> bytes:
    """Выгружает текущий список группы 240326 в Excel."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Группа 240326"

    font_title = Font(name="Calibri", size=13, bold=True)
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fill_header = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="D0D0D0"),
        right=Side(style="thin", color="D0D0D0"),
        top=Side(style="thin", color="D0D0D0"),
        bottom=Side(style="thin", color="D0D0D0"),
    )

    ws.merge_cells("A1:F1")
    ws["A1"] = "БГПУ им. М. Танка — Список группы 240326 «Матинф»"
    ws["A1"].font = font_title
    ws["A1"].alignment = align_center

    headers = ["№", "ФИО Студента", "Подгруппа", "Роль", "Статус в боте", "Telegram ID"]
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=3, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_center
        cell.border = thin_border

    sorted_students = sorted(students, key=lambda s: (s.subgroup, s.full_name))
    for row_idx, s in enumerate(sorted_students, start=4):
        ws.cell(row=row_idx, column=1, value=row_idx - 3).alignment = align_center
        ws.cell(row=row_idx, column=2, value=s.full_name).alignment = align_left
        ws.cell(row=row_idx, column=3, value=s.subgroup).alignment = align_center
        ws.cell(row=row_idx, column=4, value=s.role).alignment = align_center
        ws.cell(row=row_idx, column=5, value="Привязан" if s.telegram_id else "Не привязан").alignment = align_center
        ws.cell(row=row_idx, column=6, value=str(s.telegram_id or "")).alignment = align_center

        for col_idx in range(1, 7):
            ws.cell(row=row_idx, column=col_idx).border = thin_border

    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 38
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 14
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 18

    output = BytesIO()
    wb.save(output)
    return output.getvalue()


async def save_imported_students(
    session: AsyncSession,
    students_data: List[Dict[str, Any]],
    overwrite: bool = False,
) -> Dict[str, int]:
    """Сохраняет распарсенный список студентов в базу данных SQLite."""
    stats = {"added": 0, "updated": 0, "skipped": 0}

    res = await session.execute(select(Student))
    existing_students = {s.full_name.lower().strip(): s for s in res.scalars().all()}

    for item in students_data:
        key = item["full_name"].lower().strip()
        if key in existing_students:
            student = existing_students[key]
            student.subgroup = item["subgroup"]
            if item.get("role") and item["role"] != ROLE_STUDENT:
                student.role = item["role"]
            stats["updated"] += 1
        else:
            new_student = Student(
                full_name=item["full_name"],
                subgroup=item["subgroup"],
                role=item.get("role", ROLE_STUDENT),
                status="PENDING",
            )
            session.add(new_student)
            existing_students[key] = new_student
            stats["added"] += 1

    await session.commit()
    return stats


async def save_imported_schedule(
    session: AsyncSession,
    schedule_data: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Сохраняет расписание в базу данных SQLite."""
    stats = {"added_slots": 0, "added_subjects": 0}

    for item in schedule_data:
        # Проверяем или создаем предмет
        res = await session.execute(select(Subject).where(Subject.title == item["subject_title"]))
        subject = res.scalar_one_or_none()
        if not subject:
            subject = Subject(
                title=item["subject_title"],
                teacher_name=item["teacher_name"],
                subject_type=item["subject_type"],
            )
            session.add(subject)
            await session.flush()
            stats["added_subjects"] += 1

        slot = ScheduleSlot(
            day_of_week=item["day_of_week"],
            week_type=item["week_type"],
            pair_number=item["pair_number"],
            time_start=item["time_start"],
            time_end=item["time_end"],
            subject_id=subject.id,
            subgroup=item["subgroup"],
            building_name=item["building_name"],
            room_number=item["room_number"],
            building_lat=item["building_lat"],
            building_lon=item["building_lon"],
            radius_meters=item["radius_meters"],
        )
        session.add(slot)
        stats["added_slots"] += 1

    await session.commit()
    return stats
