"""
Состояния FSM (Finite State Machine) для aiogram 3.
"""
from aiogram.fsm.state import State, StatesGroup


class StudentImportFSM(StatesGroup):
    """Сценарий импорта списка студентов (Excel, CSV или текст)."""
    waiting_for_input = State()  # Ожидание загрузки файла или ввода текста
    confirm_import = State()     # Подтверждение импорта после парсинга


class ScheduleImportFSM(StatesGroup):
    """Сценарий импорта расписания."""
    waiting_for_file = State()
    confirm_import = State()


class BroadcastFSM(StatesGroup):
    """Сценарий создания экстренного оповещения / объявления."""
    choose_type = State()        # Выбор CRITICAL или INFO
    enter_title = State()        # Ввод заголовка
    enter_body = State()         # Ввод текста
    preview_and_confirm = State()# Предпросмотр и подтверждение отправки


class ManualStudentAddFSM(StatesGroup):
    """Сценарий ручного добавления студента."""
    enter_full_name = State()
    choose_subgroup = State()
    choose_role = State()


class QuickOverrideFSM(StatesGroup):
    """Сценарий смены статуса присутствия через бота."""
    choose_student = State()
    choose_status = State()
    enter_reason = State()
