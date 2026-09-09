import asyncio
from core.database import AsyncSessionLocal
from models import Student, RoleEnum, StudentStatusEnum
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Student).where(Student.role == RoleEnum.STAROSTA.value))
        starosta = res.scalar_one_or_none()
        if starosta:
            starosta.telegram_id = 1131010316
            starosta.status = StudentStatusEnum.ACTIVE.value
            await session.commit()
            print(f"STAROSTA_LINKED: {starosta.full_name} -> ID 1131010316")
        else:
            print("STAROSTA_NOT_FOUND")

if __name__ == "__main__":
    asyncio.run(main())
