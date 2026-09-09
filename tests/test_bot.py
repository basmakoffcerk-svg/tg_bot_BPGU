from aiogram import Bot, Dispatcher

from bot.bot import create_bot_and_dispatcher
from bot.keyboards import (
    get_starosta_approval_keyboard,
    get_students_whitelist_keyboard,
)
from models import Student


def test_create_bot_and_dispatcher():
    bot, dp = create_bot_and_dispatcher()
    assert isinstance(bot, Bot)
    assert isinstance(dp, Dispatcher)


def test_whitelist_keyboards():
    students = [
        Student(id=1, full_name="Иванов И. И.", subgroup=1),
        Student(id=2, full_name="Петров П. П.", subgroup=2),
    ]
    kb = get_students_whitelist_keyboard(students, page=0)
    assert len(kb.inline_keyboard) == 2
    assert "claim_student:1" in kb.inline_keyboard[0][0].callback_data


def test_starosta_approval_keyboard():
    kb = get_starosta_approval_keyboard(student_id=10, telegram_id=99999)
    assert len(kb.inline_keyboard) == 1
    assert "approve_claim:10:99999" in kb.inline_keyboard[0][0].callback_data
    assert "reject_claim:10:99999" in kb.inline_keyboard[0][1].callback_data
