import datetime
import io
import openpyxl
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from models import ScheduleSlot, Subject, PairsRegistry, Attendance, SubjectTypeEnum, WeekTypeEnum
from data.seed_data import BSPU_BUILDING_2

DAY_NAMES_MAP = {
    "понедельник": 1, "пн": 1, "mon": 1, "1": 1,
    "вторник": 2, "вт": 2, "tue": 2, "2": 2,
    "среда": 3, "ср": 3, "wed": 3, "3": 3,
    "четверг": 4, "чт": 4, "thu": 4, "4": 4,
    "пятница": 5, "пт": 5, "fri": 5, "5": 5,
    "суббота": 6, "сб": 6, "sat": 6, "6": 6,
}

PAIR_TIMES = {
    1: ("08:30", "10:00"),
    2: ("10:15", "11:45"),
    3: ("12:00", "13:30"),
    4: ("14:00", "15:30"),
    5: ("15:45", "17:15"),
    6: ("17:30", "19:00"),
}

def generate_schedule_template() -> io.BytesIO:
    """Generates a sample XLSX template for weekly schedule."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Расписание"

    headers = [
        "День недели", "№ Пары", "Время начала", "Время конца",
        "Предмет", "Преподаватель", "Тип (LECTURE/PRACTICE/LAB)",
        "Корпус", "Аудитория", "Подгруппа (0-все, 1, 2)"
    ]
    ws.append(headers)

    sample_rows = [
        ["Понедельник", 1, "08:30", "10:00", "Высшая математика", "Смирнов А. В.", "LECTURE", "Корпус 2", "315", 0],
        ["Понедельник", 2, "10:15", "11:45", "Информатика и программирование", "Кузнецов Д. И.", "LAB", "Корпус 2", "402", 1],
        ["Понедельник", 2, "10:15", "11:45", "Аналитическая геометрия", "Иванова О. Н.", "PRACTICE", "Корпус 2", "310", 2],
        ["Вторник", 1, "08:30", "10:00", "Математический анализ", "Федорова Е. С.", "LECTURE", "Корпус 2", "204", 0],
        ["Вторник", 2, "10:15", "11:45", "Педагогика школы", "Васильева Т. П.", "LECTURE", "Корпус 2", "208", 0],
        ["Среда", 1, "08:30", "10:00", "Методика преподавания информатики", "Павлов Н. Г.", "PRACTICE", "Корпус 2", "405", 0],
        ["Четверг", 2, "10:15", "11:45", "Дискретная математика", "Смирнов А. В.", "LECTURE", "Корпус 2", "315", 0],
        ["Пятница", 1, "08:30", "10:00", "Физическая культура", "Кафедра физвоспитания", "PRACTICE", "Корпус 2", "Спортзал", 0],
    ]
    for row in sample_rows:
        ws.append(row)

    for cell in ws[1]:
        cell.font = openpyxl.styles.Font(bold=True, color="FFFFFF")
        cell.fill = openpyxl.styles.PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out

async def import_schedule_from_excel(file_bytes: bytes, session: AsyncSession) -> tuple[bool, str, int]:
    """
    Parses uploaded Excel workbook, cleanly updates schedule_slots and creates pairs_registry
    for the current week (Monday-Saturday) respecting foreign keys.
    """
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        ws = wb.active
    except Exception as e:
        return False, f"Ошибка чтения Excel файла: {e}", 0

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return False, "Файл пуст или содержит только заголовки", 0

    slots_to_create = []
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    sunday = monday + datetime.timedelta(days=6)

    for row_idx, r in enumerate(rows[1:], start=2):
        if not r or not any(r):
            continue
        day_raw = str(r[0]).strip().lower() if r[0] else ""
        day_of_week = DAY_NAMES_MAP.get(day_raw)
        if not day_of_week:
            continue

        try:
            pair_num = int(r[1]) if r[1] else 1
        except Exception:
            pair_num = 1

        time_start = str(r[2]).strip() if r[2] else PAIR_TIMES.get(pair_num, ("08:30", "10:00"))[0]
        time_end = str(r[3]).strip() if r[3] else PAIR_TIMES.get(pair_num, ("08:30", "10:00"))[1]
        subj_title = str(r[4]).strip() if r[4] else "Занятие"
        teacher = str(r[5]).strip() if len(r) > 5 and r[5] else None
        subj_type = str(r[6]).strip().upper() if len(r) > 6 and r[6] else "LECTURE"
        if subj_type not in ("LECTURE", "PRACTICE", "LAB"):
            subj_type = "LECTURE"

        building = str(r[7]).strip() if len(r) > 7 and r[7] else BSPU_BUILDING_2["name"]
        room = str(r[8]).strip() if len(r) > 8 and r[8] else "Ауд."
        try:
            subgroup = int(r[9]) if len(r) > 9 and r[9] is not None else 0
        except Exception:
            subgroup = 0

        slots_to_create.append({
            "day_of_week": day_of_week,
            "pair_number": pair_num,
            "time_start": time_start,
            "time_end": time_end,
            "title": subj_title,
            "teacher": teacher,
            "subj_type": subj_type,
            "building": building,
            "room": room,
            "subgroup": subgroup,
        })

    if not slots_to_create:
        return False, "Не удалось распознать ни одной пары. Проверьте формат файла.", 0

    # 1. Clean PairsRegistry & Attendance for the target week to prevent Foreign Key constraints
    pairs_in_week_res = await session.execute(
        select(PairsRegistry.id).where(
            PairsRegistry.calendar_date >= monday,
            PairsRegistry.calendar_date <= sunday
        )
    )
    pair_ids = pairs_in_week_res.scalars().all()
    if pair_ids:
        await session.execute(delete(Attendance).where(Attendance.pair_id.in_(pair_ids)))
        await session.execute(delete(PairsRegistry).where(PairsRegistry.id.in_(pair_ids)))
        await session.flush()

    # 2. Also remove any orphaned PairsRegistry before clearing schedule_slots
    all_pairs_res = await session.execute(select(PairsRegistry.id))
    all_pair_ids = all_pairs_res.scalars().all()
    if all_pair_ids:
        await session.execute(delete(Attendance).where(Attendance.pair_id.in_(all_pair_ids)))
        await session.execute(delete(PairsRegistry).where(PairsRegistry.id.in_(all_pair_ids)))
        await session.flush()

    # 3. Clean existing slots safely
    await session.execute(delete(ScheduleSlot))
    await session.flush()

    total_created = 0
    created_slots = []
    for s_data in slots_to_create:
        sub_res = await session.execute(select(Subject).where(Subject.title == s_data["title"]))
        subject = sub_res.scalar_one_or_none()
        if not subject:
            subject = Subject(
                title=s_data["title"],
                teacher_name=s_data["teacher"],
                subject_type=s_data["subj_type"]
            )
            session.add(subject)
            await session.flush()

        slot = ScheduleSlot(
            day_of_week=s_data["day_of_week"],
            week_type=WeekTypeEnum.ALL.value,
            pair_number=s_data["pair_number"],
            time_start=s_data["time_start"],
            time_end=s_data["time_end"],
            subject_id=subject.id,
            subgroup=s_data["subgroup"],
            building_name=s_data["building"],
            room_number=s_data["room"],
            building_lat=BSPU_BUILDING_2["lat"],
            building_lon=BSPU_BUILDING_2["lon"],
            radius_meters=150,
        )
        session.add(slot)
        created_slots.append(slot)
        total_created += 1

    await session.flush()

    # 4. Generate pairs registry for current week (Mon-Sat)
    for slot in created_slots:
        target_date = monday + datetime.timedelta(days=slot.day_of_week - 1)
        pair = PairsRegistry(
            slot_id=slot.id,
            calendar_date=target_date,
            is_locked=False
        )
        session.add(pair)

    await session.commit()
    return True, f"Успешно загружено пар: {total_created}", total_created
