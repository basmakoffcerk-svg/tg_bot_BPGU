from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

def get_main_menu_keyboard(is_starosta: bool = False) -> ReplyKeyboardMarkup:
    """Native Telegram Reply Keyboard without any Mini App dependencies."""
    kb = [
        [KeyboardButton(text="📍 Отметиться на паре (GPS)", request_location=True)],
        [KeyboardButton(text="📅 Расписание на сегодня"), KeyboardButton(text="📊 Моя посещаемость")],
    ]
    if is_starosta:
        kb.append([
            KeyboardButton(text="👑 Шахматка группы"),
            KeyboardButton(text="📥 Загрузить расписание (Excel)")
        ])
        kb.append([
            KeyboardButton(text="📊 Рапортичка за неделю"),
            KeyboardButton(text="📢 Объявление группе")
        ])

    kb.append([KeyboardButton(text="ℹ️ Помощь")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_starosta_quick_actions_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for Starosta actions directly in chat."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👑 Открыть Шахматку в чате", callback_data="open_chat_grid")],
            [InlineKeyboardButton(text="📄 Скачать рапортичку (.xlsx)", callback_data="export_week_report")],
            [InlineKeyboardButton(text="📥 Скачать шаблон расписания (.xlsx)", callback_data="download_schedule_template")],
            [InlineKeyboardButton(text="📢 Отправить объявление группе", callback_data="prompt_broadcast")],
        ]
    )
