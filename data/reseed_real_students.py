import asyncio
from sqlalchemy import select, delete
from core.database import AsyncSessionLocal
from models import Student, Attendance, PairsRegistry, RoleEnum, StudentStatusEnum
from data.seed_data import STUDENTS_WHITELIST

STAROSTA_TG_ID = 1131010316

async def reseed():
    async with AsyncSessionLocal() as session:
        # Clear existing students and related records
        print("[RESEED] Clearing old students...")
        await session.execute(delete(Attendance))
        await session.execute(delete(PairsRegistry))
        await session.execute(delete(Student))
        await session.commit()

        print("[RESEED] Adding 24 real students from group 240326...")
        for s in STUDENTS_WHITELIST:
            is_starosta = (s["full_name"] == "Башмаков Сергей Сергеевич")
            student = Student(
                full_name=s["full_name"],
                subgroup=s["subgroup"],
                role=RoleEnum.STAROSTA.value if is_starosta else RoleEnum.STUDENT.value,
                status=StudentStatusEnum.ACTIVE.value if is_starosta else StudentStatusEnum.PENDING.value,
                telegram_id=STAROSTA_TG_ID if is_starosta else None
            )
            session.add(student)
        
        await session.commit()
        print(f"[RESEED] Done! Starosta linked: Башмаков Сергей Сергеевич -> TG ID: {STAROSTA_TG_ID}")

if __name__ == "__main__":
    asyncio.run(reseed())
