"""
Обработчики импорта и экспорта списков студентов для старосты.
"""
from io import BytesIO
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import select

from app.bot.keyboards import (
    get_cancel_keyboard,
    get_confirm_import_keyboard,
    get_group_management_keyboard,
    get_paginated_students_keyboard,
    get_schedule_management_keyboard,
)
from app.bot.states import ScheduleImportFSM, StudentImportFSM
from app.core.config import settings
from app.core.database import async_session_factory
from app.models import Student, ROLE_STAROSTA, ROLE_ZAM
from app.services.import_service import (
    export_students_to_xlsx,
    generate_schedule_template_xlsx,
    generate_students_template_xlsx,
    parse_schedule_xlsx,
    parse_students_csv,
    parse_students_text,
    parse_students_xlsx,
    save_imported_schedule,
    save_imported_students,
)

router = Router(name="import_export")


async def is_admin_user(user_id: int) -> bool:
    """Проверка прав администратора (Староста или Зам)."""
    if user_id == settings.STAROSTA_TELEGRAM_ID:
        return True
    async with async_session_factory() as db:
        stmt = select(Student).where(Student.telegram_id == user_id)
        res = await db.execute(stmt)
        st = res.scalar_one_or_none()
        return st is not None and st.role in (ROLE_STAROSTA, ROLE_ZAM)


# 1. Меню управления группой
@router.callback_query(F.data == "admin_group_manage")
async def cb_group_manage(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await is_admin_user(callback.from_user.id):
        await callback.answer("У вас нет прав старосты.", show_alert=True)
        return

    await callback.message.edit_text(
        "👥 <b>Управление составом группы 240326 Матинф</b>\n\n"
        "Здесь вы можете загрузить готовый список одногруппников (Excel/CSV/текст), "
        "скачать шаблон для заполнения, выгрузить текущую базу или просмотреть привязанные аккаунты:",
        reply_markup=get_group_management_keyboard(),
        parse_mode="HTML",
    )


# 2. Скачивание шаблона Excel
@router.callback_query(F.data == "grp_download_template")
async def cb_download_template(callback: CallbackQuery):
    if not await is_admin_user(callback.from_user.id):
        return

    template_bytes = generate_students_template_xlsx()
    file = BufferedInputFile(template_bytes, filename="Шаблон_Студенты_240326.xlsx")
    await callback.message.answer_document(
        document=file,
        caption="📄 <b>Шаблон для заполнения списка группы</b>\n\n"
                "Заполните ФИО и номер подгруппы (1 или 2), затем отправьте файл боту через меню «📥 Загрузить файл».",
        parse_mode="HTML",
    )
    await callback.answer()


# 3. Экспорт текущего списка группы в Excel
@router.callback_query(F.data == "grp_export_xlsx")
async def cb_export_group(callback: CallbackQuery):
    if not await is_admin_user(callback.from_user.id):
        return

    async with async_session_factory() as db:
        res = await db.execute(select(Student))
        students = res.scalars().all()

    xlsx_bytes = export_students_to_xlsx(students)
    file = BufferedInputFile(xlsx_bytes, filename="Список_группы_240326.xlsx")
    await callback.message.answer_document(
        document=file,
        caption=f"📤 <b>Актуальный список группы 240326 Матинф</b>\n"
                f"Всего студентов в базе: <b>{len(students)}</b>",
        parse_mode="HTML",
    )
    await callback.answer()


# 4. Просмотр списка группы с пагинацией
@router.callback_query(F.data.startswith("grp_list_p"))
async def cb_list_group_page(callback: CallbackQuery):
    page = int(callback.data.split("_p")[1])
    async with async_session_factory() as db:
        res = await db.execute(select(Student).order_by(Student.subgroup, Student.full_name))
        students = res.scalars().all()

    st_tuples = [(s.id, s.full_name, s.subgroup, s.role, s.telegram_id is not None) for s in students]
    await callback.message.edit_text(
        f"📋 <b>Список группы 240326 Матинф (Всего: {len(students)})</b>\n\n"
        f"🟢 — Telegram привязан\n"
        f"⚪ — Еще не зарегистрировался в боте",
        reply_markup=get_paginated_students_keyboard(st_tuples, page=page, page_size=6, prefix="grpview"),
        parse_mode="HTML",
    )


# 5. Импорт через файл (Excel / CSV)
@router.callback_query(F.data == "grp_import_file")
async def cb_start_import_file(callback: CallbackQuery, state: FSMContext):
    if not await is_admin_user(callback.from_user.id):
        return

    await state.set_state(StudentImportFSM.waiting_for_input)
    await state.update_data(import_type="file")
    await callback.message.edit_text(
        "📥 <b>Загрузка списка студентов из файла</b>\n\n"
        "Отправьте мне файл в формате <b>.xlsx (Excel)</b> или <b>.csv</b> как документ в чат.\n\n"
        "<i>Подсказка: файл должен содержать колонки: ФИО, Подгруппа (1 или 2).</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


# 6. Импорт через текст
@router.callback_query(F.data == "grp_import_text")
async def cb_start_import_text(callback: CallbackQuery, state: FSMContext):
    if not await is_admin_user(callback.from_user.id):
        return

    await state.set_state(StudentImportFSM.waiting_for_input)
    await state.update_data(import_type="text")
    await callback.message.edit_text(
        "✍️ <b>Ввод списка студентов текстом</b>\n\n"
        "Отправьте список сообщением. Каждый студент с новой строки.\n"
        "Формат: <code>ФИО [подгруппа]</code>\n\n"
        "<b>Пример:</b>\n"
        "<code>Иванов Иван Иванович 1\nПетров Петр Петрович 2\nСидорова Анна 1</code>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


# Обработчик полученного документа
@router.message(StudentImportFSM.waiting_for_input, F.document)
async def process_import_document(message: Message, state: FSMContext):
    doc = message.document
    file_name = (doc.file_name or "").lower()

    if not (file_name.endswith(".xlsx") or file_name.endswith(".csv")):
        await message.answer(
            "❌ Неподдерживаемый формат. Пожалуйста, отправьте файл <b>.xlsx</b> или <b>.csv</b>.",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML",
        )
        return

    bot = message.bot
    file_info = await bot.get_file(doc.file_id)
    file_stream = await bot.download_file(file_info.file_path)
    file_bytes = file_stream.read()

    if file_name.endswith(".xlsx"):
        parsed_students, errors = parse_students_xlsx(file_bytes)
    else:
        parsed_students, errors = parse_students_csv(file_bytes)

    if not parsed_students:
        err_text = "\n".join(errors[:5]) if errors else "Файл пуст или структура не распознана."
        await message.answer(
            f"❌ <b>Не удалось прочитать список студентов:</b>\n{err_text}",
            reply_markup=get_group_management_keyboard(),
            parse_mode="HTML",
        )
        await state.clear()
        return

    await state.update_data(parsed_students=parsed_students)
    await state.set_state(StudentImportFSM.confirm_import)

    preview_lines = [f"{i}. {s['full_name']} (п/г {s['subgroup']})" for i, s in enumerate(parsed_students[:8], 1)]
    more = f"\n<i>...и еще {len(parsed_students) - 8} чел.</i>" if len(parsed_students) > 8 else ""

    await message.answer(
        f"✅ <b>Файл успешно разобран!</b>\n\n"
        f"Найдено студентов: <b>{len(parsed_students)}</b>\n\n"
        f"<b>Пример распознанных данных:</b>\n" + "\n".join(preview_lines) + more + "\n\n"
        f"Сохранить этих студентов в базу данных группы 240326?",
        reply_markup=get_confirm_import_keyboard(),
        parse_mode="HTML",
    )


# Обработчик полученного текста
@router.message(StudentImportFSM.waiting_for_input, F.text)
async def process_import_text(message: Message, state: FSMContext):
    if message.text.startswith("/"):
        return

    parsed_students, errors = parse_students_text(message.text)
    if not parsed_students:
        await message.answer(
            "❌ Не удалось распознать ни одного студента. Проверьте формат строк (ФИО подгруппа).",
            reply_markup=get_cancel_keyboard(),
        )
        return

    await state.update_data(parsed_students=parsed_students)
    await state.set_state(StudentImportFSM.confirm_import)

    preview_lines = [f"{i}. {s['full_name']} (п/г {s['subgroup']})" for i, s in enumerate(parsed_students[:8], 1)]
    more = f"\n<i>...и еще {len(parsed_students) - 8} чел.</i>" if len(parsed_students) > 8 else ""

    await message.answer(
        f"✅ <b>Текст успешно разобран!</b>\n\n"
        f"Распознано студентов: <b>{len(parsed_students)}</b>\n\n"
        f"<b>Предпросмотр:</b>\n" + "\n".join(preview_lines) + more + "\n\n"
        f"Загрузить этот список в базу данных?",
        reply_markup=get_confirm_import_keyboard(),
        parse_mode="HTML",
    )


# Подтверждение импорта
@router.callback_query(StudentImportFSM.confirm_import, F.data == "confirm_import_yes")
async def cb_confirm_import(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    parsed_students = data.get("parsed_students", [])
    await state.clear()

    if not parsed_students:
        await callback.answer("Данные для импорта отсутствуют.", show_alert=True)
        return

    async with async_session_factory() as db:
        stats = await save_imported_students(db, parsed_students)

    await callback.message.edit_text(
        f"🎉 <b>Импорт успешно завершен!</b>\n\n"
        f"➕ Добавлено новых студентов: <b>{stats['added']}</b>\n"
        f"🔄 Обновлено существующих: <b>{stats['updated']}</b>\n\n"
        f"Теперь одногруппники могут запустить бота по ссылке и выбрать себя из обновленного вайтлиста.",
        reply_markup=get_group_management_keyboard(),
        parse_mode="HTML",
    )


# -------------------------------------------------------------
# Раздел управления расписанием
# -------------------------------------------------------------

@router.callback_query(F.data == "admin_schedule_manage")
async def cb_schedule_manage(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await is_admin_user(callback.from_user.id):
        await callback.answer("У вас нет прав старосты.", show_alert=True)
        return

    await callback.message.edit_text(
        "📅 <b>Управление расписанием группы 240326 Матинф</b>\n\n"
        "Здесь вы можете загрузить обновленное расписание пар из файла Excel "
        "или скачать стандартный шаблон таблицы.",
        reply_markup=get_schedule_management_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "sch_download_template")
async def cb_download_schedule_template(callback: CallbackQuery):
    if not await is_admin_user(callback.from_user.id):
        return

    template_bytes = generate_schedule_template_xlsx()
    file = BufferedInputFile(template_bytes, filename="Шаблон_Расписание_240326.xlsx")
    await callback.message.answer_document(
        document=file,
        caption="📄 <b>Шаблон расписания занятий</b>\n\n"
                "Заполните дни недели, пары, предметы, корпуса и аудитории. "
                "Затем отправьте файл боту через кнопку «📥 Загрузить расписание».",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "sch_import_file")
async def cb_start_import_schedule(callback: CallbackQuery, state: FSMContext):
    if not await is_admin_user(callback.from_user.id):
        return

    await state.set_state(ScheduleImportFSM.waiting_for_file)
    await callback.message.edit_text(
        "📥 <b>Загрузка расписания из файла Excel</b>\n\n"
        "Отправьте мне файл <b>.xlsx</b> в этот чат как документ.\n\n"
        "<i>Подсказка: таблица должна содержать колонки «День недели», «Пара», «Время начала», «Время окончания», «Предмет», «Корпус», «Аудитория».</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(ScheduleImportFSM.waiting_for_file, F.document)
async def process_schedule_document(message: Message, state: FSMContext):
    doc = message.document
    file_name = (doc.file_name or "").lower()

    if not file_name.endswith(".xlsx"):
        await message.answer(
            "❌ Неподдерживаемый формат. Пожалуйста, отправьте файл <b>.xlsx</b>.",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML",
        )
        return

    bot = message.bot
    file_info = await bot.get_file(doc.file_id)
    file_stream = await bot.download_file(file_info.file_path)
    file_bytes = file_stream.read()

    parsed_slots, errors = parse_schedule_xlsx(file_bytes)
    if not parsed_slots:
        err_text = "\n".join(errors[:5]) if errors else "Файл пуст или структура не распознана."
        await message.answer(
            f"❌ <b>Не удалось разобрать расписание:</b>\n{err_text}",
            reply_markup=get_schedule_management_keyboard(),
            parse_mode="HTML",
        )
        await state.clear()
        return

    await state.update_data(parsed_slots=parsed_slots)
    await state.set_state(ScheduleImportFSM.confirm_import)

    preview_lines = [
        f"• День {s['day_of_week']}, пара {s['slot_number']}: {s['subject']} ({s['building_name']}, ауд. {s['room']})"
        for s in parsed_slots[:5]
    ]
    more = f"\n<i>...и еще {len(parsed_slots) - 5} занятий</i>" if len(parsed_slots) > 5 else ""

    await message.answer(
        f"✅ <b>Расписание успешно прочитано!</b>\n\n"
        f"Найдено занятий в сетке: <b>{len(parsed_slots)}</b>\n\n"
        f"<b>Пример распознанных пар:</b>\n" + "\n".join(preview_lines) + more + "\n\n"
        f"Заменить текущее расписание в базе данных?",
        reply_markup=get_confirm_import_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(ScheduleImportFSM.confirm_import, F.data == "confirm_import_yes")
async def cb_confirm_schedule_import(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    parsed_slots = data.get("parsed_slots", [])
    await state.clear()

    if not parsed_slots:
        await callback.answer("Данные отсутствуют.", show_alert=True)
        return

    async with async_session_factory() as db:
        stats = await save_imported_schedule(db, parsed_slots)

    await callback.message.edit_text(
        f"🎉 <b>Расписание успешно обновлено!</b>\n\n"
        f"📚 Загружено занятий: <b>{stats['added']}</b>\n"
        f"Сетка расписания полностью актуализирована в системе.",
        reply_markup=get_schedule_management_keyboard(),
        parse_mode="HTML",
    )

