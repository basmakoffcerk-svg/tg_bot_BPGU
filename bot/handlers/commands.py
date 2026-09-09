import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import select

from bot.keyboards import get_starosta_quick_actions_keyboard
from core.database import AsyncSessionLocal
from models import Attendance, AttendanceStatusEnum, RoleEnum, Student
from services.excel_generator import generate_attendance_excel

router = Router()


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def handle_help_command(message: Message):
    help_text = (
        "📖 <b>Справка по системе «АРМ Старосты» группы 240326</b>\n\n"
        "<b>Как отметиться на паре:</b>\n"
        "1. Нажмите кнопку <b>«📍 Отметиться на паре (GPS)»</b>.\n"
        "2. Telegram запросит отправку геопозиции (Send Location).\n"
        "3. Если вы находитесь в радиусе 150 м от Корпуса 2 БГПУ (ул. Советская, 18), бот мгновенно подтвердит ваше присутствие 🟢.\n\n"
        "<b>Функции старосты:</b>\n"
        "• <b>👑 Шахматка группы</b> — оперативная ведомость прямо в чате со сменой статусов в 1 клик.\n"
        "• <b>📥 Загрузить расписание (Excel)</b> — загрузка сетки пар на неделю.\n"
        "• <b>📊 Рапортичка за неделю</b> — формирование официального файла ведомости (.xlsx).\n"
        "• <b>📢 Объявление группе</b> — оповещение всех студентов.\n\n"
        "<b>Команды:</b>\n"
        "/start — Меню и профиль\n"
        "/status — Моя статистика\n"
        "/report — Рапортичка\n"
        "/help — Эта справка"
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("status"))
@router.message(F.text == "📊 Моя посещаемость")
async def handle_status_command(message: Message):
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Student).where(Student.telegram_id == user_id))
        student = res.scalar_one_or_none()
        if not student:
            await message.answer("⚠️ Вы не зарегистрированы. Нажмите /start.")
            return

        # Fetch attendances count
        res_att = await session.execute(select(Attendance).where(Attendance.student_id == student.id))
        attendances = res_att.scalars().all()

        present_count = sum(
            1
            for a in attendances
            if a.status in (AttendanceStatusEnum.PRESENT.value, AttendanceStatusEnum.MANUAL_CONFIRM.value)
        )
        unexcused_count = sum(1 for a in attendances if a.status == AttendanceStatusEnum.ABSENT_UNEXCUSED.value)
        excused_count = sum(1 for a in attendances if a.status == AttendanceStatusEnum.ABSENT_EXCUSED.value)
        late_count = sum(1 for a in attendances if a.status == AttendanceStatusEnum.LATE.value)
        total_tracked = len(attendances)

        rate = (present_count / total_tracked * 100) if total_tracked > 0 else 100.0

        status_text = (
            f"👤 <b>Статистика студента:</b> {student.full_name}\n"
            f"🎓 Группа: 240326 «Матинф» | Подгруппа: {student.subgroup}\n\n"
            f"🟢 Посещено пар: <b>{present_count}</b>\n"
            f"🔵 Опозданий: <b>{late_count}</b>\n"
            f"🟣 По уважительной: <b>{excused_count}</b> ({excused_count * 2} ч.)\n"
            f"🔴 Пропусков без причины: <b>{unexcused_count}</b> ({unexcused_count * 2} ч.)\n\n"
            f"📈 Процент посещаемости: <b>{rate:.1f}%</b>"
        )
        await message.answer(status_text, parse_mode="HTML")


@router.message(Command("report"))
async def handle_report_command(message: Message):
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Student).where(Student.telegram_id == user_id))
        student = res.scalar_one_or_none()

        if not student or student.role not in (RoleEnum.STAROSTA.value, RoleEnum.ZAM.value):
            await message.answer("⛔ Данная команда доступна только старосте и заместителю старосты.")
            return

        await message.answer(
            "📋 <b>Управление отчетностью группы 240326</b>",
            reply_markup=get_starosta_quick_actions_keyboard(),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "export_week_report")
async def handle_export_week_report_callback(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Student).where(Student.telegram_id == user_id))
        student = res.scalar_one_or_none()

        if not student or student.role not in (RoleEnum.STAROSTA.value, RoleEnum.ZAM.value):
            await callback.answer("Недостаточно прав!", show_alert=True)
            return

        await callback.answer("Формирую рапортичку...")
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())

        excel_buf, filename, total_pairs, total_absent_hours = await generate_attendance_excel(
            session=session, date_from=monday, date_to=today
        )

        input_file = BufferedInputFile(excel_buf.getvalue(), filename=filename)
        caption = (
            f"📊 <b>Рапортичка группы 240326 «Матинф»</b>\n"
            f"Период: {monday.strftime('%d.%m')} — {today.strftime('%d.%m.%Y')}\n"
            f"Всего пар в сетке: {total_pairs}\n"
            f"Суммарно пропущено: {total_absent_hours} ч."
        )
        await callback.message.answer_document(document=input_file, caption=caption, parse_mode="HTML")

@router.message(F.text == "👑 Панель старосты")
async def handle_starosta_panel_button(message: Message):
    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Student).where(Student.telegram_id == user_id))
        student = res.scalar_one_or_none()
        if not student or student.role not in (RoleEnum.STAROSTA.value, RoleEnum.ZAM.value):
            await message.answer("⛔ Панель доступна только старосте.")
            return

        await message.answer(
            f"👑 <b>Панель старосты группы 240326</b>\n"
            f"Староста: <b>{student.full_name}</b>\n\n"
            "Выберите нужное действие:",
            reply_markup=get_starosta_quick_actions_keyboard(),
            parse_mode="HTML"
        )

@router.message(F.text == "📅 Расписание на сегодня")
async def handle_schedule_today_button(message: Message):
    today = datetime.date.today()
    day_num = today.isoweekday()
    if day_num > 6:
        await message.answer("🎉 Сегодня воскресенье, пар нет!")
        return

    async with AsyncSessionLocal() as session:
        from models import ScheduleSlot
        from sqlalchemy.orm import selectinload
        res = await session.execute(
            select(ScheduleSlot)
            .where(ScheduleSlot.day_of_week == day_num)
            .options(selectinload(ScheduleSlot.subject))
            .order_by(ScheduleSlot.pair_number, ScheduleSlot.subgroup)
        )
        slots = res.scalars().all()
        if not slots:
            await message.answer("ℹ️ На сегодня в расписании нет назначенных пар.")
            return

        lines = [f"📅 <b>Расписание на сегодня ({today.strftime('%d.%m.%Y')}):</b>\n"]
        for s in slots:
            subg_text = f" [п/г {s.subgroup}]" if s.subgroup > 0 else ""
            lines.append(
                f"<b>{s.pair_number} пара ({s.time_start} - {s.time_end}):</b>\n"
                f"📖 {s.subject.title}{subg_text}\n"
                f"👨‍🏫 {s.subject.teacher_name or 'Преподаватель не указан'}\n"
                f"📍 {s.building_name}, ауд. {s.room_number}\n"
            )

        await message.answer("\n".join(lines), parse_mode="HTML")

@router.message(F.location)
async def handle_user_location_checkin(message: Message):
    """Fallback check-in directly via Telegram GPS sharing."""
    user_id = message.from_user.id
    loc = message.location
    lat, lon, acc = loc.latitude, loc.longitude, (loc.horizontal_accuracy or 15.0)

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Student).where(Student.telegram_id == user_id))
        student = res.scalar_one_or_none()
        if not student:
            await message.answer("⚠️ Вы не зарегистрированы. Нажмите /start.")
            return

        from services.attendance_service import get_active_or_upcoming_pair, process_checkin
        pair = await get_active_or_upcoming_pair(session, student)
        if not pair:
            await message.answer("ℹ️ Сейчас нет активной пары для отметки.")
            return

        success, msg, data = await process_checkin(
            session=session,
            student=student,
            pair_id=pair.id,
            client_lat=lat,
            client_lon=lon,
            accuracy=acc
        )

        if success:
            dist = data.get("distance_meters", 0)
            await message.answer(
                f"🟢 <b>Вы успешно отметились!</b>\n\n"
                f"Пара: <b>{pair.slot.subject.title}</b>\n"
                f"Корпус: {pair.slot.building_name}\n"
                f"Дистанция: {dist:.1f} м (точность GPS ±{acc:.1f} м)",
                parse_mode="HTML"
            )
        else:
            await message.answer(f"❌ <b>Отметка не принята:</b>\n{msg}", parse_mode="HTML")

@router.message(F.text == "📊 Рапортичка за неделю")
async def handle_weekly_report_button(message: Message, bot: Bot):
    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Student).where(Student.telegram_id == user_id))
        student = res.scalar_one_or_none()
        if not student or student.role not in (RoleEnum.STAROSTA.value, RoleEnum.ZAM.value):
            await message.answer("⛔ Доступно только старосте.")
            return

        status_msg = await message.answer("⏳ Формирую официальную рапортичку...")
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())

        excel_buf, filename, total_pairs, total_absent_hours = await generate_attendance_excel(
            session=session, date_from=monday, date_to=today
        )

        input_file = BufferedInputFile(excel_buf.getvalue(), filename=filename)
        caption = (
            f"📊 <b>Рапортичка группы 240326 «Матинф»</b>\n"
            f"Период: {monday.strftime('%d.%m')} — {today.strftime('%d.%m.%Y')}\n"
            f"Всего пар в сетке: {total_pairs}\n"
            f"Суммарно пропущено: {total_absent_hours} ч."
        )
        await status_msg.delete()
        await message.answer_document(document=input_file, caption=caption, parse_mode="HTML")

@router.message(F.text == "📢 Объявление группе")
async def handle_broadcast_button(message: Message):
    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Student).where(Student.telegram_id == user_id))
        student = res.scalar_one_or_none()
        if not student or student.role not in (RoleEnum.STAROSTA.value, RoleEnum.ZAM.value):
            await message.answer("⛔ Доступно только старосте.")
            return

        await message.answer(
            "📢 <b>Рассылка объявления группе</b>\n\n"
            "Чтобы отправить объявление, используйте команду:\n"
            "<code>/alert Ваше важное объявление</code>\n\n"
            "Бот разошлет его всем зарегистрированным студентам группы 240326.",
            parse_mode="HTML"
        )
