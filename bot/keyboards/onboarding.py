from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from models import Student


def get_students_whitelist_keyboard(students: list[Student], page: int = 0, page_size: int = 6) -> InlineKeyboardMarkup:
    """Generates paginated inline keyboard of unassigned students from whitelist."""
    start_idx = page * page_size
    end_idx = start_idx + page_size
    current_page_students = students[start_idx:end_idx]

    buttons = []
    for s in current_page_students:
        buttons.append(
            [InlineKeyboardButton(text=f"{s.full_name} ({s.subgroup} подгр.)", callback_data=f"claim_student:{s.id}")]
        )

    # Pagination navigation row
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"whitelist_page:{page - 1}"))
    if end_idx < len(students):
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"whitelist_page:{page + 1}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_starosta_approval_keyboard(student_id: int, telegram_id: int) -> InlineKeyboardMarkup:
    """Inline keyboard for Starosta to approve or reject student onboarding claim."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_claim:{student_id}:{telegram_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_claim:{student_id}:{telegram_id}"),
            ]
        ]
    )
