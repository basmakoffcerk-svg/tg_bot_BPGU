import asyncio
import datetime

from sqlalchemy import select

from core.database import AsyncSessionLocal, Base, engine
from models import (
    PairsRegistry,
    RoleEnum,
    ScheduleSlot,
    Student,
    StudentStatusEnum,
    Subject,
    SubjectTypeEnum,
    WeekTypeEnum,
)

# Academic Group 240326 "Матинф" Whitelist
STUDENTS_WHITELIST = [
    # Subgroup 1
    {"full_name": "Андралович Александра Викторовна", "subgroup": 1, "role": RoleEnum.STUDENT.value},
    {"full_name": "Башмаков Сергей Сергеевич", "subgroup": 1, "role": RoleEnum.STAROSTA.value},
    {"full_name": "Бондарчук Егор Алексеевич", "subgroup": 1, "role": RoleEnum.STUDENT.value},
    {"full_name": "Бурдыко Ксения Сергеевна", "subgroup": 1, "role": RoleEnum.STUDENT.value},
    {"full_name": "Гетикова Ева Алексеевна", "subgroup": 1, "role": RoleEnum.STUDENT.value},
    {"full_name": "Гнедько Юлия Юрьевна", "subgroup": 1, "role": RoleEnum.STUDENT.value},
    {"full_name": "Григорьев Владислав Андреевич", "subgroup": 1, "role": RoleEnum.STUDENT.value},
    {"full_name": "Домбровский Матвей Анатольевич", "subgroup": 1, "role": RoleEnum.STUDENT.value},
    {"full_name": "Дриня Ангелина Геннадьевна", "subgroup": 1, "role": RoleEnum.STUDENT.value},
    {"full_name": "Евдокимов Ярослав Павлович", "subgroup": 1, "role": RoleEnum.STUDENT.value},
    {"full_name": "Ковалевская Екатерина Анарбековна", "subgroup": 1, "role": RoleEnum.STUDENT.value},
    {"full_name": "Колычева Дарья Ивановна", "subgroup": 1, "role": RoleEnum.STUDENT.value},
    # Subgroup 2
    {"full_name": "Кузьминич Андрей Евгеньевич", "subgroup": 2, "role": RoleEnum.STUDENT.value},
    {"full_name": "Лахвич Полина Денисовна", "subgroup": 2, "role": RoleEnum.STUDENT.value},
    {"full_name": "Лесько Виктория Алексеевна", "subgroup": 2, "role": RoleEnum.STUDENT.value},
    {"full_name": "Мытник Инесса Дмитриевна", "subgroup": 2, "role": RoleEnum.STUDENT.value},
    {"full_name": "Никитенко Александра Геннадьевна", "subgroup": 2, "role": RoleEnum.STUDENT.value},
    {"full_name": "Паршина Софья Валерьевна", "subgroup": 2, "role": RoleEnum.STUDENT.value},
    {"full_name": "Плотников Алексей Александрович", "subgroup": 2, "role": RoleEnum.STUDENT.value},
    {"full_name": "Порохнявая Юлия Максимовна", "subgroup": 2, "role": RoleEnum.STUDENT.value},
    {"full_name": "Романович Юлия Михайловна", "subgroup": 2, "role": RoleEnum.STUDENT.value},
    {"full_name": "Стрюк Александра Сергеевна", "subgroup": 2, "role": RoleEnum.STUDENT.value},
    {"full_name": "Ходорович Станислав Викторович", "subgroup": 2, "role": RoleEnum.STUDENT.value},
    {"full_name": "Шульжик Алеся Андреевна", "subgroup": 2, "role": RoleEnum.STUDENT.value},
]

# BSPU Campus Building Reference Coordinates (Minsk)
# Korpus 2: https://yandex.by/maps/org/bgpu_korpus_2/172831536241/?ll=27.544440%2C53.893769&z=16
BSPU_BUILDING_2 = {"name": "Корпус 2 (ул. Советская, 18)", "lat": 53.893769, "lon": 27.544440}
BSPU_MAIN_BUILDING = {"name": "Главный корпус (пл. Независимости)", "lat": 53.894100, "lon": 27.544600}
BSPU_BUILDING_B = {"name": "Корпус 3 (ул. Советская)", "lat": 53.894300, "lon": 27.545000}

SUBJECTS_DATA = [
    {"title": "Высшая математика", "teacher_name": "Смирнов А. В.", "subject_type": SubjectTypeEnum.LECTURE.value},
    {
        "title": "Высшая математика (Практика)",
        "teacher_name": "Смирнов А. В.",
        "subject_type": SubjectTypeEnum.PRACTICE.value,
    },
    {"title": "Операционные системы", "teacher_name": "Козлов Д. С.", "subject_type": SubjectTypeEnum.LECTURE.value},
    {"title": "Операционные системы (Лаб)", "teacher_name": "Козлов Д. С.", "subject_type": SubjectTypeEnum.LAB.value},
    {"title": "Базы данных", "teacher_name": "Васильева Е. Н.", "subject_type": SubjectTypeEnum.LECTURE.value},
    {"title": "Базы данных (Лаб)", "teacher_name": "Васильева Е. Н.", "subject_type": SubjectTypeEnum.LAB.value},
    {
        "title": "Архитектура вычислительных систем",
        "teacher_name": "Кузнецов П. И.",
        "subject_type": SubjectTypeEnum.LECTURE.value,
    },
    {
        "title": "Педагогика и психология",
        "teacher_name": "Морозова Т. А.",
        "subject_type": SubjectTypeEnum.LECTURE.value,
    },
]

# 6-day schedule grid
# (day_of_week 1..6, pair_number, start, end, subject_index, subgroup, building, room)
SCHEDULE_TEMPLATE = [
    # Понедельник (1)
    (1, 1, "08:30", "10:00", 0, 0, BSPU_MAIN_BUILDING, "304"),
    (1, 2, "10:15", "11:45", 1, 1, BSPU_MAIN_BUILDING, "308"),
    (1, 2, "10:15", "11:45", 3, 2, BSPU_BUILDING_B, "212-Б"),
    (1, 3, "12:00", "13:30", 2, 0, BSPU_MAIN_BUILDING, "Актовый зал"),
    # Вторник (2)
    (2, 1, "08:30", "10:00", 0, 0, BSPU_MAIN_BUILDING, "304"),
    (2, 2, "10:15", "11:45", 3, 1, BSPU_BUILDING_B, "212-Б"),
    (2, 2, "10:15", "11:45", 1, 2, BSPU_MAIN_BUILDING, "308"),
    (2, 3, "12:00", "13:30", 4, 0, BSPU_MAIN_BUILDING, "402"),
    (2, 4, "14:00", "15:30", 5, 1, BSPU_BUILDING_B, "215-Б"),
    # Среда (3)
    (3, 1, "08:30", "10:00", 6, 0, BSPU_MAIN_BUILDING, "201"),
    (3, 2, "10:15", "11:45", 7, 0, BSPU_BUILDING_2, "105"),
    (3, 3, "12:00", "13:30", 5, 2, BSPU_BUILDING_B, "215-Б"),
    # Четверг (4)
    (4, 1, "08:30", "10:00", 4, 0, BSPU_MAIN_BUILDING, "402"),
    (4, 2, "10:15", "11:45", 2, 0, BSPU_MAIN_BUILDING, "304"),
    (4, 3, "12:00", "13:30", 3, 1, BSPU_BUILDING_B, "212-Б"),
    # Пятница (5)
    (5, 1, "08:30", "10:00", 6, 0, BSPU_MAIN_BUILDING, "201"),
    (5, 2, "10:15", "11:45", 0, 0, BSPU_MAIN_BUILDING, "304"),
    (5, 3, "12:00", "13:30", 1, 0, BSPU_MAIN_BUILDING, "308"),
    # Суббота (6)
    (6, 1, "08:30", "10:00", 7, 0, BSPU_BUILDING_2, "105"),
    (6, 2, "10:15", "11:45", 5, 1, BSPU_BUILDING_B, "215-Б"),
    (6, 2, "10:15", "11:45", 5, 2, BSPU_BUILDING_B, "216-Б"),
]


async def seed_database() -> None:
    # 1. Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check if already seeded
        res = await session.execute(select(Student))
        existing_students = res.scalars().all()
        if existing_students:
            print("[SEED] Database is already seeded.")
            return

        print("[SEED] Seeding students whitelist for group 240326...")
        student_objs = []
        for s in STUDENTS_WHITELIST:
            student = Student(
                full_name=s["full_name"], subgroup=s["subgroup"], role=s["role"], status=StudentStatusEnum.PENDING.value
            )
            session.add(student)
            student_objs.append(student)

        await session.flush()

        print("[SEED] Seeding subjects...")
        subject_objs = []
        for sub in SUBJECTS_DATA:
            subject = Subject(title=sub["title"], teacher_name=sub["teacher_name"], subject_type=sub["subject_type"])
            session.add(subject)
            subject_objs.append(subject)

        await session.flush()

        print("[SEED] Seeding schedule slots...")
        slot_objs = []
        for item in SCHEDULE_TEMPLATE:
            day_of_week, pair_num, t_start, t_end, sub_idx, subg, bldg, room = item
            slot = ScheduleSlot(
                day_of_week=day_of_week,
                week_type=WeekTypeEnum.ALL.value,
                pair_number=pair_num,
                time_start=t_start,
                time_end=t_end,
                subject_id=subject_objs[sub_idx].id,
                subgroup=subg,
                building_name=bldg["name"],
                room_number=room,
                building_lat=bldg["lat"],
                building_lon=bldg["lon"],
                radius_meters=150,
            )
            session.add(slot)
            slot_objs.append(slot)

        await session.flush()

        # Seed calendar pairs for current date
        today = datetime.date.today()
        # Find day of week (Monday=1 .. Sunday=7)
        dow = today.isoweekday()
        if dow <= 6:
            print(f"[SEED] Seeding pairs registry for today ({today}, Day {dow})...")
            for slot in slot_objs:
                if slot.day_of_week == dow:
                    pair = PairsRegistry(slot_id=slot.id, calendar_date=today, is_locked=False)
                    session.add(pair)

        await session.commit()
        print("[SEED] Seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_database())
