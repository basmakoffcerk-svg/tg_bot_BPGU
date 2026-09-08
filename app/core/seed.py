"""
Скрипт начального наполнения (Seeding) базы данных для группы 240326 «Матинф» БГПУ.
"""
import asyncio
from datetime import date
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory, engine
from app.models import (
    Base,
    PairRegistry,
    ROLE_STAROSTA,
    ROLE_STUDENT,
    ROLE_ZAM,
    ScheduleSlot,
    Student,
    Subject,
)

# Корпус 1 БГПУ им. М. Танка (г. Минск, пл. Независимости / ул. Советская 18)
BGPU_BUILDING_1_LAT = 53.894510
BGPU_BUILDING_1_LON = 27.544720

# Корпус 2 БГПУ (физмат)
BGPU_BUILDING_2_LAT = 53.895100
BGPU_BUILDING_2_LON = 27.546200

STUDENTS_DATA = [
    # Староста и Зам
    ("Иванов Иван Иванович", 1, ROLE_STAROSTA, "ACTIVE", settings.STAROSTA_TELEGRAM_ID),
    ("Константинов Константин Константинович", 2, ROLE_ZAM, "ACTIVE", 987654322),
    # Студенты 1 подгруппы
    ("Алексеев Алексей Алексеевич", 1, ROLE_STUDENT, "PENDING", None),
    ("Богданова Анна Сергеевна", 1, ROLE_STUDENT, "PENDING", None),
    ("Васильев Дмитрий Олегович", 1, ROLE_STUDENT, "PENDING", None),
    ("Григорьев Максим Игоревич", 1, ROLE_STUDENT, "PENDING", None),
    ("Дмитриев Артем Павлович", 1, ROLE_STUDENT, "PENDING", None),
    ("Егорова Екатерина Денисовна", 1, ROLE_STUDENT, "PENDING", None),
    ("Жуков Владислав Андреевич", 1, ROLE_STUDENT, "PENDING", None),
    ("Зуева Полина Михайловна", 1, ROLE_STUDENT, "PENDING", None),
    ("Ильин Роман Викторович", 1, ROLE_STUDENT, "PENDING", None),
    ("Ковалева София Александровна", 1, ROLE_STUDENT, "PENDING", None),
    ("Лебедев Илья Сергеевич", 1, ROLE_STUDENT, "PENDING", None),
    ("Морозов Никита Владимирович", 1, ROLE_STUDENT, "PENDING", None),
    # Студенты 2 подгруппы
    ("Новикова Дарья Андреевна", 2, ROLE_STUDENT, "PENDING", None),
    ("Орлов Даниил Русланович", 2, ROLE_STUDENT, "PENDING", None),
    ("Павлова Ксения Сергеевна", 2, ROLE_STUDENT, "PENDING", None),
    ("Романов Глеб Дмитриевич", 2, ROLE_STUDENT, "PENDING", None),
    ("Семенов Арсений Максимович", 2, ROLE_STUDENT, "PENDING", None),
    ("Тарасова Алина Евгеньевна", 2, ROLE_STUDENT, "PENDING", None),
    ("Ульянов Богдан Олегович", 2, ROLE_STUDENT, "PENDING", None),
    ("Федоров Михаил Андреевич", 2, ROLE_STUDENT, "PENDING", None),
    ("Харитонова Елизавета Сергеевна", 2, ROLE_STUDENT, "PENDING", None),
    ("Цветков Матвей Денисович", 2, ROLE_STUDENT, "PENDING", None),
    ("Чернов Тимофей Романович", 2, ROLE_STUDENT, "PENDING", None),
    ("Щербакова Виктория Ивановна", 2, ROLE_STUDENT, "PENDING", None),
]

SUBJECTS_DATA = [
    ("Математический анализ", "проф. Сидоров В. П.", "LECTURE"),
    ("Дискретная математика и матлогика", "доц. Петрова О. Н.", "PRACTICE"),
    ("Программирование на Python", "ст. преп. Кузнецов А. М.", "LAB"),
    ("Архитектура ЭВМ и операционные системы", "доц. Николаев С. Д.", "LECTURE"),
    ("Базы данных и SQL", "ст. преп. Мельников Е. В.", "LAB"),
    ("Педагогика и психология образования", "доц. Григорьева М. А.", "LECTURE"),
]


async def seed_database():
    """Создает таблицы и наполняет начальными данными."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Проверяем, есть ли уже данные
        res = await session.execute(select(Student))
        if res.scalars().first():
            return

        # Добавляем студентов
        students_objs = []
        for name, subg, role, st, tg_id in STUDENTS_DATA:
            students_objs.append(
                Student(
                    full_name=name,
                    subgroup=subg,
                    role=role,
                    status=st,
                    telegram_id=tg_id,
                )
            )
        session.add_all(students_objs)

        # Добавляем дисциплины
        subj_objs = []
        for title, teacher, stype in SUBJECTS_DATA:
            subj_objs.append(Subject(title=title, teacher_name=teacher, subject_type=stype))
        session.add_all(subj_objs)
        await session.flush()

        # Создаем сетку расписания (Пн - Пт)
        slots = [
            # Понедельник (day 1)
            ScheduleSlot(
                day_of_week=1, week_type="ALL", pair_number=1, time_start="08:30", time_end="10:00",
                subject_id=subj_objs[0].id, subgroup=0, building_name="Корпус 1 БГПУ", room_number="304",
                building_lat=BGPU_BUILDING_1_LAT, building_lon=BGPU_BUILDING_1_LON, radius_meters=150,
            ),
            ScheduleSlot(
                day_of_week=1, week_type="ALL", pair_number=2, time_start="10:15", time_end="11:45",
                subject_id=subj_objs[1].id, subgroup=0, building_name="Корпус 1 БГПУ", room_number="308",
                building_lat=BGPU_BUILDING_1_LAT, building_lon=BGPU_BUILDING_1_LON, radius_meters=150,
            ),
            # Вторник (day 2)
            ScheduleSlot(
                day_of_week=2, week_type="ALL", pair_number=1, time_start="08:30", time_end="10:00",
                subject_id=subj_objs[2].id, subgroup=1, building_name="Корпус 2 БГПУ (Физмат)", room_number="212-Б",
                building_lat=BGPU_BUILDING_2_LAT, building_lon=BGPU_BUILDING_2_LON, radius_meters=150,
            ),
            ScheduleSlot(
                day_of_week=2, week_type="ALL", pair_number=1, time_start="08:30", time_end="10:00",
                subject_id=subj_objs[4].id, subgroup=2, building_name="Корпус 2 БГПУ (Физмат)", room_number="214-Б",
                building_lat=BGPU_BUILDING_2_LAT, building_lon=BGPU_BUILDING_2_LON, radius_meters=150,
            ),
            ScheduleSlot(
                day_of_week=2, week_type="ALL", pair_number=2, time_start="10:15", time_end="11:45",
                subject_id=subj_objs[3].id, subgroup=0, building_name="Корпус 1 БГПУ", room_number="Ауд. 410",
                building_lat=BGPU_BUILDING_1_LAT, building_lon=BGPU_BUILDING_1_LON, radius_meters=150,
            ),
        ]
        session.add_all(slots)
        await session.flush()

        # Создаем запись реестра пар на сегодня
        today = date.today()
        for slot in slots:
            session.add(PairRegistry(slot_id=slot.id, calendar_date=today))

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_database())
