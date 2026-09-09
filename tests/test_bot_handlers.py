from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Chat, Message, User

from bot.handlers.commands import (
    handle_help_command,
    handle_status_command,
)
from bot.handlers.onboarding import (
    handle_approve_claim,
    handle_start_command,
    handle_student_claim,
)


def create_mock_message(user_id: int, full_name: str = "Test User", text: str = "/start") -> Message:
    message = MagicMock(spec=Message)
    message.from_user = User(id=user_id, is_bot=False, first_name="Test", last_name="User", username="testuser")
    message.chat = Chat(id=user_id, type="private")
    message.text = text
    message.answer = AsyncMock()
    return message


def create_mock_callback(user_id: int, data: str) -> CallbackQuery:
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = User(id=user_id, is_bot=False, first_name="Test", last_name="User", username="testuser")
    callback.data = data
    callback.answer = AsyncMock()
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.message.edit_reply_markup = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.message.answer_document = AsyncMock()
    return callback


@pytest.mark.asyncio
async def test_bot_start_handler_unlinked(db_session, seed_test_data, monkeypatch):
    monkeypatch.setattr("bot.handlers.onboarding.AsyncSessionLocal", lambda: db_session)

    msg = create_mock_message(user_id=999888, text="/start")
    await handle_start_command(msg)

    msg.answer.assert_called_once()
    assert "Добро пожаловать" in msg.answer.call_args[1]["text"]


@pytest.mark.asyncio
async def test_bot_start_handler_active_student(db_session, seed_test_data, monkeypatch):
    monkeypatch.setattr("bot.handlers.onboarding.AsyncSessionLocal", lambda: db_session)

    msg = create_mock_message(user_id=333333, text="/start")
    await handle_start_command(msg)

    msg.answer.assert_called_once()
    assert "С возвращением" in msg.answer.call_args[1]["text"]


@pytest.mark.asyncio
async def test_bot_claim_and_approval_flow(db_session, seed_test_data, monkeypatch):
    monkeypatch.setattr("bot.handlers.onboarding.AsyncSessionLocal", lambda: db_session)

    mock_bot = AsyncMock()
    cb_claim = create_mock_callback(user_id=777777, data="claim_student:5")
    await handle_student_claim(cb_claim, mock_bot)

    cb_claim.message.edit_text.assert_called_once()
    assert "Запрос отправлен старосте" in cb_claim.message.edit_text.call_args[0][0]

    # Starosta approves claim
    cb_approve = create_mock_callback(user_id=111111, data="approve_claim:5:777777")
    await handle_approve_claim(cb_approve, mock_bot)

    cb_approve.message.edit_text.assert_called_once()
    assert "Заявка подтверждена" in cb_approve.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_bot_help_and_status(db_session, seed_test_data, monkeypatch):
    monkeypatch.setattr("bot.handlers.commands.AsyncSessionLocal", lambda: db_session)

    msg_help = create_mock_message(user_id=333333, text="/help")
    await handle_help_command(msg_help)
    msg_help.answer.assert_called_once()
    assert "Справка по системе" in msg_help.answer.call_args[0][0]

    msg_status = create_mock_message(user_id=333333, text="/status")
    await handle_status_command(msg_status)
    msg_status.answer.assert_called_once()
    assert "Статистика студента" in msg_status.answer.call_args[0][0]
