"""
Database seeder for Group 240326 «Матинф» БГПУ.
Populates students whitelist, disciplines catalog, and semester schedule slots.
Idempotent: skips seeding if records already exist.
"""

from typing import Dict, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import (
    ScheduleSlot,
    Student,
    StudentStatus,
    Subject,
    SubjectType,
    UserRole,
    WeekType,
)

# ============================================================================
# 1. Official Group 240326 Student Whitelist (29 Students)
# ============================================================================

STUDENTS_WHITELIST: List[Tuple[str, int, str]] = [
    # Subgroup 1 (15 students)
    ("Александров Александр Александрович", 1, UserRole.STUDENT.value),
    ("Алексеев Дмитрий Сергеевич", 1, UserRole.STUDENT.value),
    ("Белов Максим Андреевич", 1, UserRole.STUDENT.value),
    ("Борисов Владислав Игоревич", 1, UserRole.STUDENT.value),
    ("Васильев Артем Денисович", 1, UserRole.STUDENT.value),
    ("Виноградов Кирилл Павлович", 1, UserRole.STUDENT.value),
    ("Воробьев Даниил Романович", 1, UserRole.STUDENT.value),
    ("Григорьев Никита Алексеевич", 1, UserRole.STUDENT.value),
    ("Дмитриев Егор Олегович", 1, UserRole.STUDENT.value),
    ("Егоров Матвей Константинович", 1, UserRole.STUDENT.value),
    ("Жуков Илья Тимофеевич", 1, UserRole.STUDENT.value),
    ("Зайцев Михаил Вадимович", 1, UserRole.STUDENT.value),
    ("Иванов Иван Иванович", 1, UserRole.STAROSTA.value),  # Designated Starosta
    ("Ильин Арсений Русланович", 1, UserRole.STUDENT.value),
    ("Ковалев Ярослав Викторович", 1, UserRole.STUDENT.value),
    # Subgroup 2 (14 students)
    ("Козлов Даниил Сергеевич", 2, UserRole.STUDENT.value),
    ("Кузнецова Екатерина Дмитриевна", 2, UserRole.ZAM.value),  # Designated Zam
    ("Лебедев Роман Николаевич", 2, UserRole.STUDENT.value),
    ("Морозов Артур Павлович", 2, UserRole.STUDENT.value),
    ("Новиков Тимофей Андреевич", 2, UserRole.STUDENT.value),
    ("Павлов Денис Юрьевич", 2, UserRole.STUDENT.value),
    ("Попов Степан Максимович", 2, UserRole.STUDENT.value),
    ("Семенов Глеб Владимирович", 2, UserRole.STUDENT.value),
    ("Смирнова Анна Сергеевна", 2, UserRole.STUDENT.value),
    ("Соколова Дарья Антоновна", 2, UserRole.STUDENT.value),
    ("Тарасов Вадим Евгеньевич", 2, UserRole.STUDENT.value),
    ("Федоров Марк Станиславович", 2, UserRole.STUDENT.value),
    ("Харитонов Богдан Олегович", 2, UserRole.STUDENT.value),
    ("Чернов Давид Маратович", 2, UserRole.STUDENT.value),
]

# ============================================================================
# 2. Subjects Catalog (15 Disciplines)
# ============================================================================

SUBJECTS_CATALOG: List[Tuple[str, str, str]] = [
    ("Высшая математика", "Смирнов А. В.", SubjectType.LECTURE.value),
    ("Высшая математика", "Смирнов А. В.", SubjectType.PRACTICE.value),
    ("Аналитическая геометрия и линейная алгебра", "Петров Н. Н.", SubjectType.LECTURE.value),
    ("Аналитическая геометрия и линейная алгебра", "Петров Н. Н.", SubjectType.PRACTICE.value),
    ("Операционные системы", "Козлов Д. С.", SubjectType.LECTURE.value),
    ("Операционные системы (Лаб)", "Козлов Д. С.", SubjectType.LAB.value),
    ("Программирование и структуры данных", "Сидоров В. М.", SubjectType.LECTURE.value),
    ("Программирование и структуры данных (Лаб)", "Сидоров В. М.", SubjectType.LAB.value),
    ("Дискретная математика и мат. логика", "Васильев К. Е.", SubjectType.LECTURE.value),
    ("Дискретная математика и мат. логика", "Николаев С. А.", SubjectType.PRACTICE.value),
    ("Архитектура вычислительных систем", "Федоров Г. В.", SubjectType.LECTURE.value),
    ("Архитектура вычислительных систем (Лаб)", "Федоров Г. В.", SubjectType.LAB.value),
    ("Иностранный язык", "Мельникова Е. А.", SubjectType.PRACTICE.value),
    ("Педагогика высшей школы", "Белова О. И.", SubjectType.LECTURE.value),
    ("Физическая культура и спорт", "Морозов В. П.", SubjectType.PRACTICE.value),
]

# ============================================================================
# 3. Schedule Grid & Geocoded Buildings (21 Slots)
# ============================================================================

CALL_TIMES: Dict[int, Tuple[str, str]] = {
    1: ("08:30", "10:00"),
    2: ("10:15", "11:45"),
    3: ("12:00", "13:30"),
    4: ("14:00", "15:30"),
    5: ("15:45", "17:15"),
    6: ("17:30", "19:00"),
}

# (day, week_type, pair_num, subgroup, subject_title, subject_type, building_name, room, lat, lon)
SCHEDULE_SLOTS_DATA: List[Tuple[int, str, int, int, str, str, str, str, float, float]] = [
    # Monday (day 1)
    (1, WeekType.ALL.value, 1, 0, "Высшая математика", SubjectType.LECTURE.value, "Главный корпус", "304", 53.894344, 27.545763),
    (1, WeekType.ALL.value, 2, 0, "Аналитическая геометрия и линейная алгебра", SubjectType.LECTURE.value, "Главный корпус", "304", 53.894344, 27.545763),
    (1, WeekType.ALL.value, 3, 1, "Иностранный язык", SubjectType.PRACTICE.value, "Корпус Б", "108-Б", 53.893820, 27.547100),
    (1, WeekType.ALL.value, 3, 2, "Иностранный язык", SubjectType.PRACTICE.value, "Корпус Б", "110-Б", 53.893820, 27.547100),

    # Tuesday (day 2)
    (2, WeekType.ALL.value, 1, 0, "Высшая математика", SubjectType.LECTURE.value, "Главный корпус", "304", 53.894344, 27.545763),
    (2, WeekType.ALL.value, 2, 1, "Операционные системы (Лаб)", SubjectType.LAB.value, "Корпус Б", "212-Б", 53.893820, 27.547100),
    (2, WeekType.ALL.value, 2, 2, "Операционные системы (Лаб)", SubjectType.LAB.value, "Корпус Б", "214-Б", 53.893820, 27.547100),
    (2, WeekType.ALL.value, 3, 0, "Операционные системы", SubjectType.LECTURE.value, "Главный корпус", "304", 53.894344, 27.545763),

    # Wednesday (day 3)
    (3, WeekType.ALL.value, 1, 0, "Программирование и структуры данных", SubjectType.LECTURE.value, "Главный корпус", "304", 53.894344, 27.545763),
    (3, WeekType.ALL.value, 2, 1, "Программирование и структуры данных (Лаб)", SubjectType.LAB.value, "Корпус Б", "212-Б", 53.893820, 27.547100),
    (3, WeekType.ALL.value, 2, 2, "Программирование и структуры данных (Лаб)", SubjectType.LAB.value, "Корпус Б", "214-Б", 53.893820, 27.547100),
    (3, WeekType.ALL.value, 3, 0, "Высшая математика", SubjectType.PRACTICE.value, "Главный корпус", "310", 53.894344, 27.545763),

    # Thursday (day 4)
    (4, WeekType.ALL.value, 1, 0, "Аналитическая геометрия и линейная алгебра", SubjectType.PRACTICE.value, "Главный корпус", "310", 53.894344, 27.545763),
    (4, WeekType.ALL.value, 2, 0, "Архитектура вычислительных систем", SubjectType.LECTURE.value, "Главный корпус", "401", 53.894344, 27.545763),
    (4, WeekType.ODD.value, 3, 1, "Архитектура вычислительных систем (Лаб)", SubjectType.LAB.value, "Корпус Б", "212-Б", 53.893820, 27.547100),
    (4, WeekType.EVEN.value, 3, 2, "Архитектура вычислительных систем (Лаб)", SubjectType.LAB.value, "Корпус Б", "214-Б", 53.893820, 27.547100),

    # Friday (day 5)
    (5, WeekType.ALL.value, 1, 0, "Дискретная математика и мат. логика", SubjectType.LECTURE.value, "Главный корпус", "401", 53.894344, 27.545763),
    (5, WeekType.ALL.value, 2, 0, "Педагогика высшей школы", SubjectType.LECTURE.value, "Главный корпус", "401", 53.894344, 27.545763),
    (5, WeekType.ALL.value, 3, 0, "Физическая культура и спорт", SubjectType.PRACTICE.value, "Корпус №3", "Спортзал №1", 53.892900, 27.548200),

    # Saturday (day 6)
    (6, WeekType.ALL.value, 1, 0, "Дискретная математика и мат. логика", SubjectType.PRACTICE.value, "Главный корпус", "310", 53.894344, 27.545763),
    (6, WeekType.ALL.value, 2, 0, "Программирование и структуры данных", SubjectType.LECTURE.value, "Главный корпус", "304", 53.894344, 27.545763),
]


async def seed_database(session: AsyncSession) -> None:
    """
    Seed initial data into the database if not already present.
    Executes in an idempotent transaction.
    """
    # 1. Seed Students
    existing_students = await session.execute(select(Student.id).limit(1))
    if not existing_students.scalars().first():
        starosta_tg_id = getattr(settings, "STAROSTA_TELEGRAM_ID", None)
        for full_name, subgroup, role in STUDENTS_WHITELIST:
            is_starosta = (role == UserRole.STAROSTA.value)
            st = Student(
                full_name=full_name,
                subgroup=subgroup,
                role=role,
                status=StudentStatus.ACTIVE.value if is_starosta else StudentStatus.PENDING.value,
                telegram_id=starosta_tg_id if is_starosta else None,
            )
            session.add(st)
        await session.flush()

    # 2. Seed Subjects
    existing_subjects = await session.execute(select(Subject.id).limit(1))
    subject_map: Dict[Tuple[str, str], int] = {}

    if not existing_subjects.scalars().first():
        for title, teacher, stype in SUBJECTS_CATALOG:
            sub = Subject(title=title, teacher_name=teacher, subject_type=stype)
            session.add(sub)
            await session.flush()
            subject_map[(title, stype)] = sub.id
    else:
        all_subs = await session.execute(select(Subject))
        for sub in all_subs.scalars().all():
            subject_map[(sub.title, sub.subject_type)] = sub.id

    # 3. Seed Schedule Slots
    existing_slots = await session.execute(select(ScheduleSlot.id).limit(1))
    if not existing_slots.scalars().first():
        for (
            day,
            wtype,
            pnum,
            sg,
            title,
            stype,
            bname,
            rnum,
            lat,
            lon,
        ) in SCHEDULE_SLOTS_DATA:
            tstart, tend = CALL_TIMES[pnum]
            slot = ScheduleSlot(
                day_of_week=day,
                week_type=wtype,
                pair_number=pnum,
                time_start=tstart,
                time_end=tend,
                subject_id=subject_map.get((title, stype), 1),
                subgroup=sg,
                building_name=bname,
                room_number=rnum,
                building_lat=lat,
                building_lon=lon,
                radius_meters=150,
            )
            session.add(slot)
        await session.flush()

    await session.commit()


# Alias for compatibility with main lifespan
seed_all_data = seed_database
