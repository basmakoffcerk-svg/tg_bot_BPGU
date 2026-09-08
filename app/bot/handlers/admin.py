"""
Обработчики панели управления старосты и замстаросты.
"""
from __future__ import annotations
from datetime import date
from typing import Union
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot.keyboards import (
    get_admin_panel_keyboard,
    get_main_menu_keyboard,
    get_quick_grid_keyboard,
)
from app.core.config import settings
from app.core.database import async_session_factory
from app.models import (
    Attendance,
    AuditLog,
    PairRegistry,
    ScheduleSlot,
    Student,
    ROLE_STAROSTA,
    ROLE_ZAM,
    STATUS_ABSENT_EXCUSED,
    STATUS_ABSENT_UNEXCUSED,
    STATUS_MANUAL_CONFIRM,
    STATUS_PRESENT,
)
from app.services.excel_generator import generate_dean_report_xlsx

router = Router(name="admin")


async def check_is_admin(user_id: int) -> bool:
    if user_id == settings.STAROSTA_TELEGRAM_ID:
        return True
    async with async_session_factory() as db:
        res = await db.execute(select(Student).where(Student.telegram_id == user_id))
        st = res.scalar_one_or_none()
        return st is not None and st.role in (ROLE_STAROSTA, ROLE_ZAM)


# 1. Вызов админки командой /admin или кнопкой
@router.message(Command("admin"))
@router.message(F.text == "⚙️ Панель Старосты")
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    if not await check_is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа к панели управления старосты.")
        return

    await message.answer(
        "⚙️ <b>Панель управления Старосты</b>\n"
        "Группа <code>240326 Матинф</code> (БГПУ)\n\n"
        "Выберите необходимое действие:",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="HTML",
    )


# 2. Возврат в главное меню
@router.callback_query(F.data == "btn_back_main")
async def cb_back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    async with async_session_factory() as db:
        res = await db.execute(select(Student).where(Student.telegram_id == callback.from_user.id))
        st = res.scalar_one_or_none()
        role = st.role if st else "STUDENT"

    await callback.message.edit_text(
        "👋 Главное меню:",
        reply_markup=get_main_menu_keyboard(role),
    )


# 3. Переход в меню админки
@router.callback_query(F.data == "btn_admin_menu")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("Нет прав.", show_alert=True)
        return

    await callback.message.edit_text(
        "⚙️ <b>Панель управления Старосты</b>\n"
        "Группа <code>240326 Матинф</code> (БГПУ)\n\n"
        "Выберите раздел:",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="HTML",
    )


# 4. Экспресс-шахматка в Telegram
@router.callback_query(F.data.in_(["admin_quick_grid", "refresh_grid"]))
async def cb_quick_grid(callback: CallbackQuery):
    if not await check_is_admin(callback.from_user.id):
        return

    today = date.today()
    async with async_session_factory() as db:
        # Ищем пару на сегодня
        stmt = (
            select(PairRegistry)
            .options(selectinload(PairRegistry.slot).selectinload(ScheduleSlot.subject))
            .where(PairRegistry.calendar_date == today)
            .order_by(PairRegistry.slot_id)
        )
        res = await db.execute(stmt)
        pair = res.scalars().first()

        if not pair:
            await callback.answer("На сегодня нет активных пар в расписании.", show_alert=True)
            return

        # Получаем студентов и посещаемость
        st_res = await db.execute(select(Student).where(Student.status == "ACTIVE").order_by(Student.full_name))
        students = st_res.scalars().all()

        att_res = await db.execute(select(Attendance).where(Attendance.pair_id == pair.id))
        attendances = {a.student_id: a.status for a in att_res.scalars().all()}

        student_status_list = []
        present_cnt = 0
        for s in students:
            st = attendances.get(s.id, STATUS_ABSENT_UNEXCUSED)
            if st in (STATUS_PRESENT, STATUS_MANUAL_CONFIRM):
                present_cnt += 1
            student_status_list.append((s.id, s.full_name, st))

        text = (
            f"📊 <b>Экспресс-шахматка группы 240326</b>\n"
            f"Пара: <b>{pair.slot.subject.title}</b> (Ауд. {pair.slot.room_number})\n"
            f"Присутствует: <b>{present_cnt} из {len(students)}</b>\n\n"
            f"<i>Нажмите на фамилию для циклического переключения статуса:</i>\n"
            f"🟢 Был ➔ 🟡 Вручную ➔ 🟣 Уваж. ➔ 🔴 Пропуск (Н)"
        )

        await callback.message.edit_text(
            text,
            reply_markup=get_quick_grid_keyboard(pair.id, student_status_list[:10]),
            parse_mode="HTML",
        )


# 5. Циклическое переключение статуса студента в экспресс-шахматке
@router.callback_query(F.data.startswith("toggle_st_"))
async def cb_toggle_student_status(callback: CallbackQuery):
    if not await check_is_admin(callback.from_user.id):
        return

    _, _, pair_id_str, st_id_str = callback.data.split("_")
    pair_id = int(pair_id_str)
    student_id = int(st_id_str)

    cycle_map = {
        STATUS_ABSENT_UNEXCUSED: STATUS_PRESENT,
        STATUS_PRESENT: STATUS_MANUAL_CONFIRM,
        STATUS_MANUAL_CONFIRM: STATUS_ABSENT_EXCUSED,
        STATUS_ABSENT_EXCUSED: STATUS_ABSENT_UNEXCUSED,
    }

    async with async_session_factory() as db:
        att_stmt = select(Attendance).where(
            Attendance.pair_id == pair_id,
            Attendance.student_id == student_id,
        )
        res = await db.execute(att_stmt)
        att = res.scalar_one_or_none()

        current_st = att.status if att else STATUS_ABSENT_UNEXCUSED
        new_st = cycle_map.get(current_st, STATUS_PRESENT)

        if not att:
            att = Attendance(
                pair_id=pair_id,
                student_id=student_id,
                status=new_st,
                verified_by_admin=True,
            )
            db.add(att)
        else:
            att.status = new_st
            att.verified_by_admin = True

        audit = AuditLog(
            admin_id=1,
            action="QUICK_TOGGLE",
            target_id=student_id,
            details_json=f'{{"pair_id": {pair_id}, "status": "{new_st}"}}',
        )
        db.add(audit)
        await db.commit()

    await callback.answer(f"Статус изменен на {new_st}")
    # Обновляем шахматку
    await cb_quick_grid(callback)


# 6. Запрос рапортички в Excel прямо в чат
@router.message(F.text == "📑 Рапортичка (.xlsx)")
@router.callback_query(F.data == "btn_export_report")
async def cb_export_report_chat(event: Message | CallbackQuery):
    user_id = event.from_user.id
    if not await check_is_admin(user_id):
        return

    if isinstance(event, CallbackQuery):
        await event.answer("Формирую рапортичку...")
    else:
        await event.answer("⏳ Формирую рапортичку за текущий месяц...")

    today = date.today()
    date_from = today.replace(day=1)  # С начала месяца

    async with async_session_factory() as db:
        st_res = await db.execute(select(Student).where(Student.status == "ACTIVE").order_by(Student.full_name))
        students = [{"id": s.id, "full_name": s.full_name, "subgroup": s.subgroup} for s in st_res.scalars().all()]

        pairs_stmt = (
            select(PairRegistry)
            .options(selectinload(PairRegistry.slot).selectinload(ScheduleSlot.subject))
            .where(PairRegistry.calendar_date >= date_from, PairRegistry.calendar_date <= today)
            .order_by(PairRegistry.calendar_date, PairRegistry.slot_id)
        )
        pairs_res = await db.execute(pairs_stmt)
        pairs = pairs_res.scalars().all()

        dates_and_pairs = []
        seen = set()
        pair_id_to_meta = {}
        for p in pairs:
            pair_id_to_meta[p.id] = (p.calendar_date, p.slot.pair_number)
            key = (p.calendar_date, p.slot.pair_number)
            if key not in seen:
                seen.add(key)
                dates_and_pairs.append((p.calendar_date, p.slot.pair_number, p.slot.subject.title))

        att_stmt = select(Attendance).join(PairRegistry).where(
            PairRegistry.calendar_date >= date_from,
            PairRegistry.calendar_date <= today,
        )
        att_res = await db.execute(att_stmt)
        matrix = {}
        for a in att_res.scalars().all():
            if a.pair_id in pair_id_to_meta:
                c_date, p_num = pair_id_to_meta[a.pair_id]
                matrix[(a.student_id, c_date, p_num)] = a.status

        xlsx_bytes = generate_dean_report_xlsx(
            group_name="240326 Матинф",
            university_name="БГПУ им. М. Танка",
            date_from=date_from,
            date_to=today,
            students=students,
            dates_and_pairs=dates_and_pairs,
            attendance_matrix=matrix,
        )

    filename = f"Рапортичка_240326_{date_from.strftime('%d.%m')}-{today.strftime('%d.%m')}.xlsx"
    file = BufferedInputFile(xlsx_bytes, filename=filename)
    target_msg = event.message if isinstance(event, CallbackQuery) else event
    await target_msg.answer_document(
        document=file,
        caption=f"📑 <b>Официальная рапортичка деканата</b>\n"
                f"Группа: <code>240326 Матинф</code> (БГПУ)\n"
                f"Период: {date_from.strftime('%d.%m.%Y')} — {today.strftime('%d.%m.%Y')}",
        parse_mode="HTML",
    )
