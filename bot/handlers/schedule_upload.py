import datetime
import io
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Document, Message
from sqlalchemy import select
from core.database import AsyncSessionLocal
from models import RoleEnum, Student
from services.schedule_importer import generate_schedule_template, import_schedule_from_excel

schedule_upload_router = Router()

@schedule_upload_router.message(Command("upload_schedule"))
@schedule_upload_router.message(F.text == "📥 Загрузить расписание (Excel)")
async def handle_upload_schedule_prompt(message: Message):
    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Student).where(Student.telegram_id == user_id))
        student = res.scalar_one_or_none()
        if not student or student.role not in (RoleEnum.STAROSTA.value, RoleEnum.ZAM.value):
            await message.answer("⛔ Данная функция доступна только старосте группы.")
            return

    await message.answer(
        "📅 <b>Загрузка расписания на неделю</b>\n\n"
        "Отправьте мне <b>Excel-файл (.xlsx)</b> с расписанием в ответ на это сообщение.\n\n"
        "💡 Если у вас нет шаблона, нажмите команду /schedule_template, чтобы получить готовый файл с примером.",
        parse_mode="HTML"
    )

@schedule_upload_router.message(Command("schedule_template"))
@schedule_upload_router.callback_query(F.data == "download_schedule_template")
async def handle_download_template(event: Message | CallbackQuery):
    template_buf = generate_schedule_template()
    doc = BufferedInputFile(template_buf.getvalue(), filename="Шаблон_расписания_240326.xlsx")
    caption = "📥 <b>Шаблон расписания на неделю для группы 240326</b>\n\nЗаполните колонки и отправьте файл боту."

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer_document(document=doc, caption=caption, parse_mode="HTML")
    else:
        await event.answer_document(document=doc, caption=caption, parse_mode="HTML")

@schedule_upload_router.message(F.document)
async def handle_schedule_excel_upload(message: Message, bot: Bot):
    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Student).where(Student.telegram_id == user_id))
        student = res.scalar_one_or_none()
        if not student or student.role not in (RoleEnum.STAROSTA.value, RoleEnum.ZAM.value):
            return

        doc: Document = message.document
        if not (doc.file_name and doc.file_name.endswith((".xlsx", ".xls"))):
            await message.answer("⚠️ Пожалуйста, отправьте файл в формате Excel (.xlsx).")
            return

        status_msg = await message.answer("⏳ Читаю расписание и обновляю пары в базе данных...")

        try:
            file_io = io.BytesIO()
            await bot.download(doc, destination=file_io)
            file_bytes = file_io.getvalue()

            success, text, count = await import_schedule_from_excel(file_bytes, session)
            if success:
                await status_msg.edit_text(
                    f"✅ <b>Расписание успешно обновлено!</b>\n\n"
                    f"📌 Загружено пар на текущую неделю: <b>{count}</b>\n"
                    "Сетка в Telegram Mini App и в боте синхронизирована.",
                    parse_mode="HTML"
                )
            else:
                await status_msg.edit_text(f"❌ <b>Ошибка при импорте расписания:</b>\n{text}", parse_mode="HTML")
        except Exception as e:
            await status_msg.edit_text(f"❌ Ошибка обработки файла: {e}")
