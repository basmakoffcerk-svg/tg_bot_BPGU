"""
Клавиатуры и инлайн-кнопки aiogram 3.x для АРМ Старосты.
"""
from typing import List, Tuple
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)
from app.core.config import settings


def get_main_menu_keyboard(role: str) -> InlineKeyboardMarkup:
    """Главное меню пользователя."""
    webapp_url = settings.FRONTEND_URL + "/webapp/index.html"
    buttons = []
    if webapp_url.startswith("https://"):
        buttons.append([InlineKeyboardButton(text="📱 Открыть Пульт (Mini App)", web_app=WebAppInfo(url=webapp_url))])
    
    buttons.append([
        InlineKeyboardButton(text="📅 Мое расписание", callback_data="btn_schedule_today"),
        InlineKeyboardButton(text="📊 Моя посещаемость", callback_data="btn_my_stats"),
    ])
    if role in ("STAROSTA", "ZAM"):
        buttons.append([
            InlineKeyboardButton(text="⚙️ Панель Старосты", callback_data="btn_admin_menu"),
            InlineKeyboardButton(text="📑 Рапортичка (.xlsx)", callback_data="btn_export_report"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_reply_main_keyboard(role: str) -> ReplyKeyboardMarkup:
    """Текстовая клавиатура Telegram для быстрого доступа к командам и геочекину."""
    webapp_url = settings.FRONTEND_URL + "/webapp/index.html"
    first_row = []
    if webapp_url.startswith("https://"):
        first_row.append(KeyboardButton(text="📱 Открыть Пульт (TMA)", web_app=WebAppInfo(url=webapp_url)))
    first_row.append(KeyboardButton(text="📍 Отметиться на паре (GPS)", request_location=True))

    keyboard = [
        first_row,
        [
            KeyboardButton(text="📅 Расписание"),
            KeyboardButton(text="📊 Моя статистика"),
        ],
    ]
    if role in ("STAROSTA", "ZAM"):
        keyboard.append([
            KeyboardButton(text="⚙️ Панель Старосты"),
            KeyboardButton(text="📑 Рапортичка (.xlsx)"),
        ])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_student_claim_keyboard(available_students: List[Tuple[int, str, int]]) -> InlineKeyboardMarkup:
    """Список свободных ФИО из вайтлиста для самопривязки."""
    buttons = []
    for s_id, full_name, subgroup in available_students:
        buttons.append([
            InlineKeyboardButton(
                text=f"{full_name} (п/г {subgroup})",
                callback_data=f"claim_{s_id}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Панель управления старосты."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Управление группой", callback_data="admin_group_manage"),
            InlineKeyboardButton(text="📅 Расписание", callback_data="admin_schedule_manage"),
        ],
        [
            InlineKeyboardButton(text="📊 Экспресс-шахматка", callback_data="admin_quick_grid"),
            InlineKeyboardButton(text="📢 Экстренная рассылка", callback_data="admin_start_broadcast"),
        ],
        [
            InlineKeyboardButton(text="📑 Рапортичка в Excel", callback_data="btn_export_report"),
            InlineKeyboardButton(text="🔒 Зафиксировать пару", callback_data="admin_lock_current_pair"),
        ],
        [
            InlineKeyboardButton(text="🔙 В главное меню", callback_data="btn_back_main"),
        ]
    ])


def get_group_management_keyboard() -> InlineKeyboardMarkup:
    """Меню управления списком студентов."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 Загрузить файл (Excel / CSV)", callback_data="grp_import_file"),
            InlineKeyboardButton(text="✍️ Ввести текстом", callback_data="grp_import_text"),
        ],
        [
            InlineKeyboardButton(text="➕ Добавить студента", callback_data="grp_add_manual"),
            InlineKeyboardButton(text="📤 Выгрузить список (.xlsx)", callback_data="grp_export_xlsx"),
        ],
        [
            InlineKeyboardButton(text="📄 Скачать шаблон Excel", callback_data="grp_download_template"),
            InlineKeyboardButton(text="📋 Список группы", callback_data="grp_list_p0"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад в админку", callback_data="btn_admin_menu"),
        ]
    ])


def get_schedule_management_keyboard() -> InlineKeyboardMarkup:
    """Меню управления расписанием."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 Загрузить расписание (.xlsx)", callback_data="sch_import_file"),
            InlineKeyboardButton(text="📄 Скачать шаблон Excel", callback_data="sch_download_template"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад в админку", callback_data="btn_admin_menu"),
        ]
    ])


def get_paginated_students_keyboard(
    students: List[Tuple[int, str, int, str, bool]],  # (id, name, subg, role, is_bound)
    page: int = 0,
    page_size: int = 6,
    prefix: str = "claim",
) -> InlineKeyboardMarkup:
    """Пагинатор списка студентов (по page_size на страницу)."""
    total = len(students)
    start = page * page_size
    end = start + page_size
    chunk = students[start:end]

    buttons = []
    for s_id, name, subg, role, is_bound in chunk:
        status_mark = "🟢" if is_bound else "⚪"
        role_mark = " (Староста)" if role == "STAROSTA" else (" (Зам)" if role == "ZAM" else "")
        label = f"{status_mark} {name} (п/г {subg}){role_mark}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"{prefix}_{s_id}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"page_{prefix}_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{(total + page_size - 1) // page_size or 1}", callback_data="noop"))
    if end < total:
        nav_row.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"page_{prefix}_{page + 1}"))

    if nav_row:
        buttons.append(nav_row)

    if prefix == "claim":
        buttons.append([InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_claims")])
    else:
        buttons.append([InlineKeyboardButton(text="🔙 Назад к управлению", callback_data="admin_group_manage")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_starosta_approval_keyboard(student_id: int, telegram_id: int) -> InlineKeyboardMarkup:
    """Кнопки одобрения/отклонения привязки профиля."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{student_id}_{telegram_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{student_id}_{telegram_id}"),
        ]
    ])


def get_broadcast_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа рассылки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Критический алерт (@all + ЛС)", callback_data="bcast_type_CRITICAL"),
        ],
        [
            InlineKeyboardButton(text="🟡 Обычное объявление (в группу)", callback_data="bcast_type_INFO"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"),
        ]
    ])


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены текущего действия."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
    ])


def get_confirm_import_keyboard() -> InlineKeyboardMarkup:
    """Кнопки подтверждения импорта."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Загрузить в базу", callback_data="confirm_import_yes"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_action"),
        ]
    ])


def get_quick_grid_keyboard(pair_id: int, students_status: List[Tuple[int, str, str]]) -> InlineKeyboardMarkup:
    """Экспресс-шахматка в Telegram: кнопки студентов для быстрого переключения статуса."""
    buttons = []
    for st_id, name, st in students_status:
        short_name = name.split()[0] + " " + (name.split()[1][0] + "." if len(name.split()) > 1 else "")
        badge = "🟢" if st == "PRESENT" else ("🟡" if st == "MANUAL_CONFIRM" else ("🟣" if st == "ABSENT_EXCUSED" else "🔴"))
        buttons.append([
            InlineKeyboardButton(
                text=f"{badge} {short_name}: {st}",
                callback_data=f"toggle_st_{pair_id}_{st_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="🔒 Зафиксировать пару", callback_data=f"lock_p_{pair_id}"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_grid_{pair_id}"),
    ])
    buttons.append([InlineKeyboardButton(text="🔙 В админку", callback_data="btn_admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
