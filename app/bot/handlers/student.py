"""
Обработчики команд и функций студента: расписание, статистика и геочекин.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot.keyboards import get_main_menu_keyboard
from app.core.config import settings
from app.core.database import async_session_factory
from app.models import (
    Attendance,
    PairRegistry,
    ScheduleSlot,
    Student,
    STATUS_ABSENT_EXCUSED,
    STATUS_ABSENT_UNEXCUSED,
    STATUS_MANUAL_CONFIRM,
    STATUS_PRESENT,
)
from app.services.geo_service import validate_checkin_location

router = Router(name="student")


# 1. Расписание на сегодня (/schedule или кнопка)
@router.message(Command("schedule"))
@router.message(F.text == "📅 Расписание")
@router.callback_query(F.data == "btn_schedule_today")
async def show_schedule(event: Message | CallbackQuery):
    user_id = event.from_user.id
    today = date.today()
    dow = today.isocalendar()[2]
    week_num = today.isocalendar()[1]
    week_type = "ODD" if week_num % 2 != 0 else "EVEN"

    async with async_session_factory() as db:
        # Получаем студента
        res = await db.execute(select(Student).where(Student.telegram_id == user_id))
        student = res.scalar_one_or_none()
        subg = student.subgroup if student else 1

        # Загружаем расписание
        stmt = (
            select(ScheduleSlot)
            .options(selectinload(ScheduleSlot.subject))
            .where(
                ScheduleSlot.day_of_week == dow,
                ScheduleSlot.week_type.in_([week_type, "ALL"]),
                ScheduleSlot.subgroup.in_([0, subg]),
            )
            .order_by(ScheduleSlot.pair_number)
        )
        slots_res = await db.execute(stmt)
        slots = slots_res.scalars().all()

    if not slots:
        text = "📅 <b>Расписание на сегодня:</b>\n\n🎉 Сегодня пар нет! Занятия отсутствуют."
    else:
        text = (
            f"📅 <b>Расписание на сегодня ({today.strftime('%d.%m.%Y')}):</b>\n"
            f"Неделя: <b>{week_num}-я ({'числитель' if week_type == 'ODD' else 'знаменатель'})</b> | Подгруппа: <b>{subg}</b>\n\n"
        )
        for s in slots:
            text += (
                f"⏰ <b>Пара №{s.pair_number} ({s.time_start} - {s.time_end})</b>\n"
                f"📚 <b>{s.subject.title}</b> ({s.subject.subject_type})\n"
                f"👨‍🏫 {s.subject.teacher_name or 'Преподаватель'}\n"
                f"🏢 {s.building_name}, ауд. <b>{s.room_number}</b>\n\n"
            )

    kb = get_main_menu_keyboard(student.role if student else "STUDENT")
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


# 2. Моя статистика посещаемости (/stats или кнопка)
@router.message(Command("stats"))
@router.message(F.text == "📊 Моя статистика")
@router.callback_query(F.data == "btn_my_stats")
async def show_stats(event: Message | CallbackQuery):
    user_id = event.from_user.id

    async with async_session_factory() as db:
        res = await db.execute(select(Student).where(Student.telegram_id == user_id))
        student = res.scalar_one_or_none()

        if not student:
            msg = "Вы еще не привязали свой профиль. Нажмите /start"
            if isinstance(event, CallbackQuery):
                await event.answer(msg, show_alert=True)
            else:
                await event.answer(msg)
            return

        att_res = await db.execute(select(Attendance).where(Attendance.student_id == student.id))
        records = att_res.scalars().all()

    total_records = len(records)
    present_cnt = sum(1 for r in records if r.status in (STATUS_PRESENT, STATUS_MANUAL_CONFIRM))
    unexcused_cnt = sum(1 for r in records if r.status == STATUS_ABSENT_UNEXCUSED)
    excused_cnt = sum(1 for r in records if r.status == STATUS_ABSENT_EXCUSED)

    percent = (present_cnt / total_records * 100) if total_records > 0 else 100.0

    text = (
        f"📊 <b>Личная статистика посещаемости</b>\n"
        f"Студент: <b>{student.full_name}</b> (п/г {student.subgroup})\n"
        f"Группа: <code>240326 Матинф</code> (БГПУ)\n\n"
        f"🟢 Посещено пар: <b>{present_cnt}</b>\n"
        f"🔴 Пропусков без уваж. причины: <b>{unexcused_cnt}</b> ({unexcused_cnt * 2} ч.)\n"
        f"🟣 Пропусков по уваж. причине: <b>{excused_cnt}</b> ({excused_cnt * 2} ч.)\n\n"
        f"📈 Процент посещаемости: <b>{percent:.1f}%</b>"
    )

    kb = get_main_menu_keyboard(student.role)
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


# 3. Геочекин через отправку локации в Telegram
@router.message(F.location)
async def process_location_checkin(message: Message):
    """Студент нажал кнопку 'Поделиться геопозицией' в Telegram."""
    loc = message.location
    lat = loc.latitude
    lon = loc.longitude
    acc = loc.horizontal_accuracy or 15.0
    now_dt = datetime.now()
    today = date.today()

    async with async_session_factory() as db:
        st_res = await db.execute(select(Student).where(Student.telegram_id == message.from_user.id))
        student = st_res.scalar_one_or_none()

        if not student:
            await message.answer("Сначала привяжите свой профиль через /start.")
            return

        # Ищем пару на сегодня
        pairs_res = await db.execute(
            select(PairRegistry)
            .options(selectinload(PairRegistry.slot).selectinload(ScheduleSlot.subject))
            .where(PairRegistry.calendar_date == today)
        )
        pairs = pairs_res.scalars().all()

        current_pair = None
        # Сначала ищем строго в окне старта (за 5 мин до начала и первые 15 мин)
        for p in pairs:
            slot = p.slot
            if slot.subgroup != 0 and slot.subgroup != student.subgroup:
                continue

            sh, sm = map(int, slot.time_start.split(":"))
            start_time = datetime.combine(today, datetime.min.time()).replace(hour=sh, minute=sm)
            window_start = start_time - timedelta(minutes=settings.CHECKIN_WINDOW_BEFORE_MINUTES)
            window_end = start_time + timedelta(minutes=settings.CHECKIN_WINDOW_AFTER_MINUTES)

            if window_start <= now_dt <= window_end:
                current_pair = p
                break

        # Если строгой пары в окне 15 мин нет, но идет текущая пара по расписанию
        if not current_pair:
            for p in pairs:
                slot = p.slot
                if slot.subgroup != 0 and slot.subgroup != student.subgroup:
                    continue
                sh, sm = map(int, slot.time_start.split(":"))
                eh, em = map(int, slot.time_end.split(":"))
                start_time = datetime.combine(today, datetime.min.time()).replace(hour=sh, minute=sm)
                end_time = datetime.combine(today, datetime.min.time()).replace(hour=eh, minute=em)
                if start_time <= now_dt <= end_time:
                    current_pair = p
                    break

        if not current_pair:
            upcoming_info = ""
            for p in pairs:
                slot = p.slot
                if slot.subgroup != 0 and slot.subgroup != student.subgroup:
                    continue
                sh, sm = map(int, slot.time_start.split(":"))
                start_time = datetime.combine(today, datetime.min.time()).replace(hour=sh, minute=sm)
                if start_time > now_dt:
                    upcoming_info = f"\n\nСледующая пара: <b>{slot.subject.title}</b> в {slot.time_start}."
                    break

            await message.answer(
                "❌ <b>Окно геочекина закрыто.</b>\n"
                "Отметиться на паре можно во время проведения занятия (окно чекина открывается за 5 минут до начала)."
                f"{upcoming_info}",
                parse_mode="HTML",
            )
            return

        if current_pair.is_locked:
            await message.answer("❌ Журнал на эту пару уже зафиксирован старостой.")
            return

        # Валидация координат
        is_valid, dist, err_msg = validate_checkin_location(
            client_lat=lat,
            client_lon=lon,
            accuracy=acc,
            target_lat=current_pair.slot.building_lat,
            target_lon=current_pair.slot.building_lon,
            max_radius=current_pair.slot.radius_meters,
            max_accuracy=settings.MAX_GPS_ACCURACY_METERS,
        )

        if not is_valid:
            await message.answer(f"❌ {err_msg}")
            return

        # Фиксация присутствия
        att_res = await db.execute(
            select(Attendance).where(
                Attendance.pair_id == current_pair.id,
                Attendance.student_id == student.id,
            )
        )
        att = att_res.scalar_one_or_none()

        if not att:
            att = Attendance(
                pair_id=current_pair.id,
                student_id=student.id,
                status=STATUS_PRESENT,
                checkin_time=now_dt,
                client_lat=lat,
                client_lon=lon,
                distance_meters=dist,
                accuracy_meters=acc,
            )
            db.add(att)
        else:
            att.status = STATUS_PRESENT
            att.checkin_time = now_dt
            att.distance_meters = dist
            att.accuracy_meters = acc

        await db.commit()

        await message.answer(
            f"🟢 <b>Присутствие на паре успешно подтверждено!</b>\n\n"
            f"Дисциплина: <b>{current_pair.slot.subject.title}</b>\n"
            f"Аудитория: <b>{current_pair.slot.room_number}</b> ({current_pair.slot.building_name})\n"
            f"Дистанция до корпуса: <b>{dist:.1f} м</b>",
            parse_mode="HTML",
        )
