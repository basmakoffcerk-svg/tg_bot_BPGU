import asyncio
import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.app import create_app
from core.config import settings
from core.database import Base, get_db
from core.security import generate_test_init_data
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

TEST_BOT_TOKEN = settings.BOT_TOKEN
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def seed_test_data(db_session: AsyncSession):
    # 1. Students
    starosta = Student(
        id=1,
        telegram_id=111111,
        full_name="Иванов Иван Иванович",
        subgroup=1,
        role=RoleEnum.STAROSTA.value,
        status=StudentStatusEnum.ACTIVE.value,
    )
    zam = Student(
        id=2,
        telegram_id=222222,
        full_name="Кириллов Кирилл Кириллович",
        subgroup=1,
        role=RoleEnum.ZAM.value,
        status=StudentStatusEnum.ACTIVE.value,
    )
    student1 = Student(
        id=3,
        telegram_id=333333,
        full_name="Александров Александр Александрович",
        subgroup=1,
        role=RoleEnum.STUDENT.value,
        status=StudentStatusEnum.ACTIVE.value,
    )
    student2 = Student(
        id=4,
        telegram_id=444444,
        full_name="Петров Петр Петрович",
        subgroup=2,
        role=RoleEnum.STUDENT.value,
        status=StudentStatusEnum.ACTIVE.value,
    )
    unlinked = Student(
        id=5,
        telegram_id=None,
        full_name="Борисов Борис Борисович",
        subgroup=1,
        role=RoleEnum.STUDENT.value,
        status=StudentStatusEnum.PENDING.value,
    )
    db_session.add_all([starosta, zam, student1, student2, unlinked])
    await db_session.flush()

    # 2. Subject
    subject = Subject(
        id=1, title="Высшая математика", teacher_name="Смирнов А. В.", subject_type=SubjectTypeEnum.LECTURE.value
    )
    db_session.add(subject)
    await db_session.flush()

    # 3. Schedule Slot (BSPU Building 2: 53.893769, 27.544440)
    slot = ScheduleSlot(
        id=1,
        day_of_week=datetime.date.today().isoweekday(),
        week_type=WeekTypeEnum.ALL.value,
        pair_number=1,
        time_start="08:30",
        time_end="10:00",
        subject_id=subject.id,
        subgroup=0,
        building_name="Корпус 2",
        room_number="304",
        building_lat=53.893769,
        building_lon=27.544440,
        radius_meters=150,
    )
    db_session.add(slot)
    await db_session.flush()

    # 4. Pair in registry for today
    pair = PairsRegistry(id=1, slot_id=slot.id, calendar_date=datetime.date.today(), is_locked=False)
    db_session.add(pair)
    await db_session.commit()

    return {
        "starosta": starosta,
        "zam": zam,
        "student1": student1,
        "student2": student2,
        "unlinked": unlinked,
        "slot": slot,
        "pair": pair,
    }


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers_starosta():
    init_data = generate_test_init_data(111111, TEST_BOT_TOKEN, first_name="Иван", last_name="Иванов")
    return {"X-Telegram-Init-Data": init_data}


@pytest.fixture
def auth_headers_student():
    init_data = generate_test_init_data(333333, TEST_BOT_TOKEN, first_name="Александр", last_name="Александров")
    return {"X-Telegram-Init-Data": init_data}
