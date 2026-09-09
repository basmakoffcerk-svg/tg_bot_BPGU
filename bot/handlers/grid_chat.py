import datetime
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database import AsyncSessionLocal
from models import Attendance, AttendanceStatusEnum, PairsRegistry, RoleEnum, ScheduleSlot, Student
from services.attendance_service import get_checkin_window_status

chat_grid_router = Router()

STATUS_EMOJIS = {
    AttendanceStatusEnum.PRESENT.value: "🟢",
    AttendanceStatusEnum.MANUAL_CONFIRM.value: "🟡",
    AttendanceStatusEnum.LATE.value: "🔵",
    AttendanceStatusEnum.ABSENT_EXCUSED.value: "🟣",
    AttendanceStatusEnum.ABSENT_UNEXCUSED.value: "🔴",
}

STATUS_NAMES = {
    AttendanceStatusEnum.PRESENT.value: "Присутствовал",
    AttendanceStatusEnum.MANUAL_CONFIRM.value: "Подтвержден вручную",
    AttendanceStatusEnum.LATE.value: "Опоздал",
    AttendanceStatusEnum.ABSENT_EXCUSED.value: "Уважительная",
    AttendanceStatusEnum.ABSENT_UNEXCUSED.value: "Неуважительная",
}

@chat_grid_router.message(F.text == "👑 Шахматка группы")
@chat_grid_router.callback_query(F.data == "open_chat_grid")
async def handle_show_pairs_for_grid(event: Message | CallbackQuery):
    today = datetime.date.today()
    async with AsyncSessionLocal() as session:
        # Check permission
        user_id = event.from_user.id
        user_res = await session.execute(select(Student).where(Student.telegram_id == user_id))
        cur_student = user_res.scalar_one_or_none()
        if not cur_student or cur_student.role not in (RoleEnum.STAROSTA.value, RoleEnum.ZAM.value):
            msg = "⛔ Шахматка доступна только старосте и замстаросты."
            if isinstance(event, CallbackQuery):
                await event.answer(msg, show_alert=True)
            else:
                await event.answer(msg)
            return

        # Fetch today's pairs
        res = await session.execute(
            select(PairsRegistry)
            .where(PairsRegistry.calendar_date == today)
            .options(selectinload(PairsRegistry.slot).selectinload(ScheduleSlot.subject))
            .order_by(PairsRegistry.id)
        )
        pairs = res.scalars().all()

        if not pairs:
            text = f"ℹ️ <b>На сегодня ({today.strftime('%d.%m.%Y')}) нет активных пар в реестре.</b>"
            if isinstance(event, CallbackQuery):
                await event.message.edit_text(text, parse_mode="HTML")
            else:
                await event.answer(text, parse_mode="HTML")
            return

        buttons = []
        for p in pairs:
            lock_icon = "🔒" if p.is_locked else "🔓"
            btn_text = f"{lock_icon} {p.slot.pair_number} пара: {p.slot.subject.title[:20]} ({p.slot.time_start})"
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"grid_view_pair:{p.id}")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        text = f"👑 <b>Шахматка посещаемости на сегодня ({today.strftime('%d.%m.%Y')}):</b>\n\nВыберите пару для просмотра и смены статусов:"
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await event.answer(text, reply_markup=kb, parse_mode="HTML")


@chat_grid_router.callback_query(F.data.startswith("grid_view_pair:"))
async def handle_view_pair_grid(callback: CallbackQuery):
    pair_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(PairsRegistry)
            .where(PairsRegistry.id == pair_id)
            .options(selectinload(PairsRegistry.slot).selectinload(ScheduleSlot.subject))
        )
        pair = res.scalar_one_or_none()
        if not pair:
            await callback.answer("Пара не найдена", show_alert=True)
            return

        # Fetch students and attendances
        students_res = await session.execute(select(Student).order_by(Student.subgroup, Student.full_name))
        students = students_res.scalars().all()

        att_res = await session.execute(select(Attendance).where(Attendance.pair_id == pair.id))
        attendances = {a.student_id: a for a in att_res.scalars().all()}

        # Stats
        p_count = sum(1 for a in attendances.values() if a.status in (AttendanceStatusEnum.PRESENT.value, AttendanceStatusEnum.MANUAL_CONFIRM.value))
        late_count = sum(1 for a in attendances.values() if a.status == AttendanceStatusEnum.LATE.value)
        excused_count = sum(1 for a in attendances.values() if a.status == AttendanceStatusEnum.ABSENT_EXCUSED.value)
        unexcused_count = len(students) - (p_count + late_count + excused_count)

        win = get_checkin_window_status(pair.slot, pair.calendar_date)
        win_str = f"🟢 Окно открыто (до {win['window_end']})" if win["is_active"] else f"⚪ Окно закрыто ({pair.slot.time_start} - {pair.slot.time_end})"

        text = (
            f"📖 <b>{pair.slot.subject.title}</b> ({pair.slot.pair_number} пара)\n"
            f"📍 {pair.slot.building_name}, ауд. {pair.slot.room_number}\n"
            f"⏱️ {pair.slot.time_start} - {pair.slot.time_end} | {win_str}\n"
            f"🔒 Заперта: {'Да' if pair.is_locked else 'Нет'}\n\n"
            f"📊 <b>Сводка:</b>\n"
            f"🟢 Присутствуют: {p_count} | 🔵 Опоздали: {late_count}\n"
            f"🟣 Уважительная: {excused_count} | 🔴 Неуважительная: {unexcused_count}\n\n"
            "<i>Нажмите на фамилию студента для быстрой смены статуса:</i>"
        )

        buttons = []
        for st in students:
            att = attendances.get(st.id)
            current_status = att.status if att else AttendanceStatusEnum.ABSENT_UNEXCUSED.value
            emoji = STATUS_EMOJIS.get(current_status, "🔴")
            short_name = " ".join([parts[0], parts[1][0] + "."] if len(parts := st.full_name.split()) > 1 else [st.full_name])
            btn_text = f"{emoji} {short_name} (п/г {st.subgroup})"
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"toggle_att:{pair.id}:{st.id}")])

        # Action bar
        action_row = [
            InlineKeyboardButton(text="🔒 Запереть" if not pair.is_locked else "🔓 Отпереть", callback_data=f"toggle_lock_pair:{pair.id}"),
            InlineKeyboardButton(text="🔙 К списку пар", callback_data="open_chat_grid")
        ]
        buttons.append(action_row)

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@chat_grid_router.callback_query(F.data.startswith("toggle_att:"))
async def handle_toggle_student_status(callback: CallbackQuery):
    _, pair_id_str, student_id_str = callback.data.split(":")
    pair_id = int(pair_id_str)
    student_id = int(student_id_str)

    async with AsyncSessionLocal() as session:
        # Check pair lock
        res_pair = await session.execute(select(PairsRegistry).where(PairsRegistry.id == pair_id))
        pair = res_pair.scalar_one_or_none()
        if not pair:
            await callback.answer("Пара не найдена", show_alert=True)
            return

        if pair.is_locked:
            await callback.answer("🔒 Пара заперта старостой! Изменение статусов заблокировано.", show_alert=True)
            return

        att_res = await session.execute(
            select(Attendance).where(Attendance.pair_id == pair_id, Attendance.student_id == student_id)
        )
        attendance = att_res.scalar_one_or_none()

        cycle = [
            AttendanceStatusEnum.ABSENT_UNEXCUSED.value,
            AttendanceStatusEnum.PRESENT.value,
            AttendanceStatusEnum.MANUAL_CONFIRM.value,
            AttendanceStatusEnum.LATE.value,
            AttendanceStatusEnum.ABSENT_EXCUSED.value,
        ]

        if not attendance:
            next_status = AttendanceStatusEnum.PRESENT.value
            attendance = Attendance(
                pair_id=pair_id,
                student_id=student_id,
                status=next_status,
                checkin_time=datetime.datetime.now(),
                verified_by_admin=True,
            )
            session.add(attendance)
        else:
            cur_idx = cycle.index(attendance.status) if attendance.status in cycle else 0
            next_status = cycle[(cur_idx + 1) % len(cycle)]
            attendance.status = next_status
            attendance.verified_by_admin = True

        await session.commit()
        await callback.answer(f"Статус изменен: {STATUS_EMOJIS.get(next_status)} {STATUS_NAMES.get(next_status)}")

    # Refresh grid view
    await handle_view_pair_grid(callback)


@chat_grid_router.callback_query(F.data.startswith("toggle_lock_pair:"))
async def handle_toggle_lock_pair(callback: CallbackQuery):
    pair_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(PairsRegistry).where(PairsRegistry.id == pair_id))
        pair = res.scalar_one_or_none()
        if pair:
            pair.is_locked = not pair.is_locked
            await session.commit()
            await callback.answer(f"Пара {'заперта 🔒' if pair.is_locked else 'отперта 🔓'}")

    await handle_view_pair_grid(callback)
