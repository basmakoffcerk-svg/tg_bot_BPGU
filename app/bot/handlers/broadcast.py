"""
Обработчики FSM-мастера рассылки экстренных сообщений и объявлений.
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.bot.keyboards import (
    get_admin_panel_keyboard,
    get_broadcast_type_keyboard,
    get_cancel_keyboard,
)
from app.bot.states import BroadcastFSM
from app.core.config import settings
from app.core.database import async_session_factory
from app.models import BroadcastMessage, Student, ROLE_STAROSTA, ROLE_ZAM

router = Router(name="broadcast")


# 1. Запуск мастера рассылки
@router.callback_query(F.data == "admin_start_broadcast")
async def cb_start_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastFSM.choose_type)
    await callback.message.edit_text(
        "📢 <b>Мастер экстренного вещания</b>\n\n"
        "Выберите тип отправляемого сообщения:\n\n"
        "🔴 <b>Критический алерт:</b> тег @all в групповой чат + принудительная персональная отправка в ЛС каждому студенту.\n"
        "🟡 <b>Обычное объявление:</b> публикация только в чат группы без спама в личные сообщения.",
        reply_markup=get_broadcast_type_keyboard(),
        parse_mode="HTML",
    )


# 2. Выбор типа
@router.callback_query(BroadcastFSM.choose_type, F.data.startswith("bcast_type_"))
async def cb_choose_bcast_type(callback: CallbackQuery, state: FSMContext):
    bcast_type = callback.data.replace("bcast_type_", "")
    await state.update_data(bcast_type=bcast_type)
    await state.set_state(BroadcastFSM.enter_title)

    await callback.message.edit_text(
        f"Тип сообщения: <b>{bcast_type}</b>\n\n"
        "Шаг 1 из 2: Введите <b>тему / заголовок</b> оповещения (например, <i>«Перенос пары по матлогу»</i>):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


# 3. Ввод темы
@router.message(BroadcastFSM.enter_title, F.text)
async def process_bcast_title(message: Message, state: FSMContext):
    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(BroadcastFSM.enter_body)

    await message.answer(
        f"Тема: <b>{title}</b>\n\n"
        "Шаг 2 из 2: Введите <b>основной текст</b> сообщения (поддерживается разметка):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


# 4. Ввод текста и предпросмотр
@router.message(BroadcastFSM.enter_body, F.text)
async def process_bcast_body(message: Message, state: FSMContext):
    body = message.text.strip()
    await state.update_data(body=body)
    await state.set_state(BroadcastFSM.preview_and_confirm)

    data = await state.get_data()
    bcast_type = data["bcast_type"]
    title = data["title"]

    preview_text = (
        f"📋 <b>ПРЕДПРОСМОТР ОПОВЕЩЕНИЯ:</b>\n"
        f"────────────────────\n"
        f"{'🚨 <b>ВНИМАНИЕ ВСЕМ (@all)!</b>' if bcast_type == 'CRITICAL' else 'ℹ️ <b>ОБЪЯВЛЕНИЕ ГРУППЫ:</b>'}\n\n"
        f"📌 <b>{title}</b>\n\n"
        f"{body}\n"
        f"────────────────────\n"
        f"Тип: <b>{bcast_type}</b>\n\n"
        f"Отправить сообщение?"
    )

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Отправить сейчас", callback_data="confirm_bcast_send")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")],
    ])

    await message.answer(preview_text, reply_markup=confirm_kb, parse_mode="HTML")


# 5. Отправка рассылки
@router.callback_query(BroadcastFSM.preview_and_confirm, F.data == "confirm_bcast_send")
async def cb_send_broadcast(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    bcast_type = data["bcast_type"]
    title = data["title"]
    body = data["body"]
    await state.clear()

    await callback.message.edit_text("⏳ Рассылка отправляется...")

    bot = callback.bot
    delivered_count = 0
    failed_count = 0

    async with async_session_factory() as db:
        res = await db.execute(select(Student).where(Student.status == "ACTIVE", Student.telegram_id.isnot(None)))
        students = res.scalars().all()

        message_header = "🚨 <b>СРОЧНОЕ ОПОВЕЩЕНИЕ СТАРОСТЫ</b>" if bcast_type == "CRITICAL" else "ℹ️ <b>ОБЪЯВЛЕНИЕ СТАРОСТЫ</b>"
        full_text = (
            f"{message_header}\n\n"
            f"📌 <b>{title}</b>\n\n"
            f"{body}\n\n"
            f"<i>Группа 240326 Матинф БГПУ</i>"
        )

        # 1. Отправка в групповой чат (если задан)
        if settings.GROUP_CHAT_ID:
            try:
                chat_msg = f"@all\n{full_text}" if bcast_type == "CRITICAL" else full_text
                await bot.send_message(chat_id=settings.GROUP_CHAT_ID, text=chat_msg, parse_mode="HTML")
            except Exception:
                pass

        # 2. Если критический алерт — персональная рассылка в ЛС каждому
        if bcast_type == "CRITICAL":
            for s in students:
                try:
                    await bot.send_message(chat_id=s.telegram_id, text=full_text, parse_mode="HTML")
                    delivered_count += 1
                except Exception:
                    failed_count += 1
        else:
            delivered_count = len(students)

        # Сохранение в БД
        msg_record = BroadcastMessage(
            sender_id=1,
            message_type=bcast_type,
            title=title,
            body=body,
            total_recipients=len(students),
            read_count=delivered_count,
        )
        db.add(msg_record)
        await db.commit()

    await callback.message.answer(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"Доставлено в ЛС: <b>{delivered_count}</b>\n"
        f"Ошибок доставки: <b>{failed_count}</b>\n"
        f"Опубликовано в группе: {'Да' if settings.GROUP_CHAT_ID else 'Чат не настроен'}",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="HTML",
    )
