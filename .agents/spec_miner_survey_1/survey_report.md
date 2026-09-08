# ИСЧЕРПЫВАЮЩИЙ ОТЧЕТ СПЕЦИФИКАЦИОННОГО АНАЛИЗА (SPECIFICATION MINING REPORT)
## Проект: АРМ Старосты («Пульт управления группой 240326 Матинф БГПУ»)
**Агент-исследователь:** `spec_miner_survey_1`  
**Дата обследования:** 2026-09-08  
**Источники спецификации:** `ORIGINAL_REQUEST.md`, `docs/SRS.md`, `docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/API.md`, `docs/DEPLOYMENT.md`, `README.md`, `.env.example`, `requirements.txt`.

---

## 1. Полная инвентаризация функционала и пользовательских сценариев (Feature Inventory)

### 1.1. Роли пользователей и матрица доступа (RBAC)
Система разграничивает полномочия на основе трех ролей:
1. **Студент (`STUDENT`)**:
   - Онбординг через привязку к вайтлисту группы 240326.
   - Просмотр актуального расписания на текущий день с учетом своей подгруппы (1 или 2).
   - Просмотр таймера обратного отсчета до открытия окна геочекина.
   - Выполнение геочекина на занятии по GPS с проверкой точности ($\le 50$ м) и расстояния ($\le 150$ м).
   - Просмотр собственного статуса присутствия и дистанции.
   - Получение персональных уведомлений и экстренных алертов в ЛС от бота.
2. **Заместитель старосты (`ZAM` / Admin)**:
   - Все полномочия роли `STUDENT`.
   - Доступ к интерактивной шахматке посещаемости группы на выбранную пару в Mini App.
   - Ручной оверрайд (override) статусов студентов (с фиксацией в `audit_log`).
   - Формирование и скачивание официальной ведомости деканата в формате `.xlsx` (через TMA и команду `/report`).
   - Отправка обычных информационных объявлений (`INFO`) в группу.
   - Получение еженедельной автоматической рапортички (суббота 16:00).
3. **Староста (`STAROSTA` / SuperAdmin)**:
   - Все полномочия ролей `STUDENT` и `ZAM`.
   - Окончательное запирание журнала пары (`lock pair`), запрещающее чекин и изменения задним числом.
   - Отправка экстренных критических оповещений (`CRITICAL`: тег `@all` в групповой чат + принудительный персональный спам в ЛС каждому студенту с трекингом прочтения).
   - 1-клик одобрение или отклонение заявок студентов при онбординге через инлайн-кнопки в Telegram.
   - Назначение и снятие заместителя старосты (`ZAM`).
   - Управление расписанием и списочным составом группы.

### 1.2. Пользовательские сценарии (User Journeys)

#### Сценарий 1: Онбординг студента и привязка к вайтлисту
1. Студент открывает Telegram-бота и отправляет `/start`.
2. Бот выполняет поиск по `students.telegram_id`:
   - Если пользователь уже `ACTIVE` — выводится главное меню и кнопка запуска TMA.
   - Если статус `PENDING` — выводится сообщение: «Ваша заявка ожидает подтверждения старостой».
   - Если `telegram_id` отсутствует в БД — бот делает выборку из таблицы `students` всех записей, где `telegram_id IS NULL` (непривязанный вайтлист группы 240326).
3. Студенту выводится инлайн-клавиатура со списком ФИО и подгрупп.
4. Студент кликает на свою фамилию и подтверждает выбор.
5. Запись студента получает временную привязку со статусом `PENDING`.
6. Бот немедленно отправляет старосте (`STAROSTA_TELEGRAM_ID`) уведомление:
   *«🔔 Заявка на регистрацию: Студент @username (ID: 123456789) заявляет, что он — Иванов Иван Иванович (1 подгруппа). Подтвердить?»*
   с инлайн-кнопками `[ ✅ Подтвердить ]` и `[ ❌ Отклонить ]`.
7. Староста в 1 клик нажимает кнопку:
   - При одобрении: `students.status = 'ACTIVE'`, `students.telegram_id` сохраняется, старосте редактируется сообщение на `✅ Заявка одобрена`, студенту отправляется приветственное сообщение с кнопкой WebApp `📱 Открыть пульт`.
   - При отклонении: запись студента освобождается (`telegram_id = NULL`), студенту отправляется уведомление об отказе.

#### Сценарий 2: Просмотр расписания и выполнение геочекина
1. Студент запускает Telegram Mini App через Menu Button (`📱 Открыть пульт`) или инлайн-кнопку.
2. WebApp SDK считывает `initData` и отправляет заголовок `X-Telegram-Init-Data` на бэкенд (`POST /api/v1/auth/telegram`).
3. Бэкенд валидирует HMAC-SHA256 подпись и возвращает профиль, права доступа и параметры текущей учебной недели (номер недели, числитель `ODD` / знаменатель `EVEN`).
4. TMA запрашивает расписание на сегодня (`GET /api/v1/schedule/today`).
5. Отображаются карточки пар, соответствующие дню недели, четности недели и подгруппе студента (подгруппа 1 видит свои пары и общие, подгруппа 2 — свои и общие).
6. В карточке текущей пары отображается состояние окна чекина:
   - До открытия (ранее 5 минут до старта пары): таймер обратного отсчета до открытия окна.
   - Во время окна (`[time_start - 5 мин ... time_start + 15 мин]`): активная кнопка «Отметиться на паре».
   - После закрытия (спустя 15 минут от старта): статус `TIME_EXPIRED`.
7. При нажатии «Отметиться на паре»:
   - TMA вызывает HTML5 Geolocation API (`navigator.geolocation.getCurrentPosition`) с параметрами `enableHighAccuracy: true`, `timeout: 10000`, `maximumAge: 0`.
   - Проверка точности на клиенте: если `accuracy > 50` м, чекин блокируется с предупреждением: «Низкая точность GPS (> 50 м). Подойдите к окну».
   - Клиент передает `pair_id`, `client_lat`, `client_lon`, `accuracy`, `timestamp` в `POST /api/v1/attendance/checkin`.
8. Бэкенд производит 5-ступенчатую серверную валидацию:
   - Проверка срока давности клиентской метки времени: $|t_{client} - t_{server}| \le 30$ сек.
   - Проверка точности: $accuracy \le 50.0$ м.
   - Проверка открытости пары: `is_locked == false`.
   - Проверка временного окна пары: $t_{current} \in [time\_start - 5\text{м} \dots time\_start + 15\text{м}]$.
   - Вычисление расстояния $d$ по формуле гаверсинусов до эталонных координат аудитории/корпуса.
9. Если $d \le 150.0$ м:
   - Создается/обновляется запись в таблице `attendance`: `status = 'PRESENT'`, `distance_meters = d`, `accuracy_meters = accuracy`, `checkin_time = NOW()`.
   - Возвращается 200 OK, в TMA карточка окрашивается в зеленый цвет с текстом: «Вы успешно отметились! Дистанция: $d$ м».
10. Если $d > 150.0$ м:
   - Возвращается 400 Bad Request (RFC 7807, `type: out-of-bounds`), TMA отображает красное предупреждение с указанием фактического расстояния до корпуса.

#### Сценарий 3: Интерактивная шахматка старосты и ручной оверрайд
1. Староста или Замстаросты открывает в TMA вкладку «Шахматка».
2. Вызывается `GET /api/v1/attendance/grid/{pair_id}`.
3. Отображается сводная панель (всего студентов, присутствуют, отсутствуют, подтверждены вручную, уважительная причина) и список студентов по алфавиту с цветовыми бейджами:
   - 🟢 `PRESENT` (зеленый) — геочекин подтвержден.
   - ⚪ `ABSENT_UNEXCUSED` (серый/красный) — студент не отметился («Н»).
   - 🟡 `MANUAL_CONFIRM` (желтый) — подтверждено старостой вручную.
   - 🔵 `LATE` (синий) — опоздание («О»).
   - 🟣 `ABSENT_EXCUSED` (фиолетовый) — пропуск по уважительной причине («У»).
4. Одиночный тап по карточке студента: циклический свитчер `PRESENT` $\rightarrow$ `ABSENT_UNEXCUSED` $\rightarrow$ `LATE` $\rightarrow$ `MANUAL_CONFIRM`.
5. Долгий тап: всплывающее модальное окно для ввода причины пропуска (`excuse_reason`: «Справка №...», «Заявление от 08.09») с установкой статуса `ABSENT_EXCUSED`.
6. Отправка `PATCH /api/v1/attendance/override`.
7. Запись события в таблицу `audit_log` (`admin_id`, действие, `target_student_id`, JSON с изменениями).
8. Фиксация пары: Староста нажимает «Зафиксировать пару» $\rightarrow$ `POST /api/v1/attendance/lock/{pair_id}` $\rightarrow$ `pairs_registry.is_locked = 1`. Редактирование блокируется.

#### Сценарий 4: Экспорт ведомости в Excel (Деканат)
1. Вызов по требованию:
   - В Telegram-боте командой `/report` или через кнопку в TMA «Выгрузить рапортичку» (`POST /api/v1/reports/export`).
   - Выбор диапазона: «Текущая неделя», «Прошлая неделя», «Месяц», произвольные даты.
   - Генератор на `openpyxl` формирует файл по университетскому стандарту с формулами `COUNTIF` и `SUM`.
   - Файл `.xlsx` отправляется старосте в ЛС Telegram документом.
2. Автоматический еженедельный триггер:
   - APScheduler каждую субботу в 16:00 генерирует сводную ведомость за прошедшую учебную неделю и отправляет файл старосте и замстаросты со сводкой пропусков.

#### Сценарий 5: Экстренные оповещения (Broadcasting)
1. Староста формирует оповещение через TMA или команду бота (`POST /api/v1/alerts/broadcast`).
2. Выбирает пресет (перенос пары, задержка преподавателя, сдача справок, ссылка на дистанционную пару) или вводит произвольный текст.
3. Тип `CRITICAL`:
   - Отправка в групповой чат (`GROUP_CHAT_ID`) с тегом `@all`.
   - Пакетная рассылка в личные сообщения каждому подтвержденному студенту группы через Telegram Bot API.
   - Сбор статистики доставки и прочтения (в таблице `broadcast_messages`).
4. Тип `INFO`: публикация только в групповой чат без рассылки в ЛС.

---

## 2. Модели данных, таблицы, колонки, связи и ограничения

База данных: **SQLite** в режиме `WAL` (`PRAGMA journal_mode = WAL`).  
ORM: **SQLAlchemy 2.0 Async** (`AsyncEngine`, `Mapped`, `mapped_column`).

### 2.1. Таблица `students` (Студенты и учетные записи)
| Колонка | Тип данных | Ограничения | Описание |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | PK, AUTOINCREMENT | Первичный ключ студента |
| `telegram_id` | `BIGINT` | UNIQUE, NULL | Telegram User ID (NULL до онбординга) |
| `full_name` | `VARCHAR(150)` | NOT NULL | Полное ФИО по официальному списку группы |
| `subgroup` | `INTEGER` | NOT NULL, CHECK(subgroup IN (1, 2)) | Номер учебной подгруппы |
| `role` | `VARCHAR(20)` | NOT NULL, DEFAULT 'STUDENT', CHECK(role IN ('STUDENT', 'ZAM', 'STAROSTA')) | Роль в системе (RBAC) |
| `status` | `VARCHAR(20)` | NOT NULL, DEFAULT 'PENDING', CHECK(status IN ('PENDING', 'ACTIVE', 'BLOCKED')) | Статус аккаунта |
| `created_at` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | Время создания записи |
| `updated_at` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | Время последнего обновления |

- **Индексы:** `idx_students_telegram_id ON students(telegram_id)`, `idx_students_full_name ON students(full_name)`.

### 2.2. Таблица `subjects` (Учебные дисциплины)
| Колонка | Тип данных | Ограничения | Описание |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | PK, AUTOINCREMENT | Первичный ключ дисциплины |
| `title` | `VARCHAR(150)` | NOT NULL | Название предмета (например, «Высшая математика») |
| `teacher_name` | `VARCHAR(120)` | NULL | ФИО преподавателя |
| `subject_type` | `VARCHAR(20)` | NOT NULL, CHECK(subject_type IN ('LECTURE', 'PRACTICE', 'LAB')) | Тип занятия |

### 2.3. Таблица `schedule_slots` (Базовая сетка расписания)
| Колонка | Тип данных | Ограничения | Описание |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | PK, AUTOINCREMENT | Идентификатор слота расписания |
| `day_of_week` | `INTEGER` | NOT NULL, CHECK(day_of_week BETWEEN 1 AND 6) | День недели (1 = Пн, 6 = Сб) |
| `week_type` | `VARCHAR(10)` | NOT NULL, DEFAULT 'ALL', CHECK(week_type IN ('ODD', 'EVEN', 'ALL')) | Числитель (`ODD`), Знаменатель (`EVEN`), Каждая (`ALL`) |
| `pair_number` | `INTEGER` | NOT NULL, CHECK(pair_number BETWEEN 1 AND 6) | Номер пары (1..6) |
| `time_start` | `VARCHAR(5)` | NOT NULL | Время начала занятия (`HH:MM`, например "08:30") |
| `time_end` | `VARCHAR(5)` | NOT NULL | Время окончания занятия (`HH:MM`, например "10:00") |
| `subject_id` | `INTEGER` | NOT NULL, FK $\rightarrow$ `subjects(id)` ON DELETE CASCADE | Внешний ключ на дисциплину |
| `subgroup` | `INTEGER` | NOT NULL, DEFAULT 0, CHECK(subgroup IN (0, 1, 2)) | 0 — вся группа, 1 — 1-я подгруппа, 2 — 2-я |
| `building_name` | `VARCHAR(100)` | NOT NULL | Наименование учебного корпуса |
| `room_number` | `VARCHAR(20)` | NOT NULL | Номер аудитории |
| `building_lat` | `REAL` | NOT NULL | Эталонная широта центра корпуса/аудитории |
| `building_lon` | `REAL` | NOT NULL | Эталонная долгота центра корпуса/аудитории |
| `radius_meters` | `INTEGER` | NOT NULL, DEFAULT 150 | Допустимый радиус валидации (м) |

- **Индексы:** `idx_schedule_lookup ON schedule_slots(day_of_week, week_type, subgroup)`.

### 2.4. Таблица `pairs_registry` (Фактический календарный реестр пар)
| Колонка | Тип данных | Ограничения | Описание |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | PK, AUTOINCREMENT | Первичный ключ проведенной/текущей пары |
| `slot_id` | `INTEGER` | NOT NULL, FK $\rightarrow$ `schedule_slots(id)` ON DELETE RESTRICT | Ссылка на слот расписания |
| `calendar_date` | `DATE` | NOT NULL | Дата проведения занятия (`YYYY-MM-DD`) |
| `is_locked` | `BOOLEAN` | NOT NULL, DEFAULT 0 | Флаг блокировки журнала старостой |
| `locked_at` | `TIMESTAMP` | NULL | Временная метка блокировки |
| `locked_by_id` | `INTEGER` | NULL, FK $\rightarrow$ `students(id)` | Староста, зафиксировавший пару |

- **Ограничения уникальности:** `CONSTRAINT uq_slot_date UNIQUE (slot_id, calendar_date)`.
- **Индексы:** `idx_pairs_calendar_date ON pairs_registry(calendar_date)`.

### 2.5. Таблица `attendance` (Журнал посещаемости)
| Колонка | Тип данных | Ограничения | Описание |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | PK, AUTOINCREMENT | Идентификатор записи посещаемости |
| `pair_id` | `INTEGER` | NOT NULL, FK $\rightarrow$ `pairs_registry(id)` ON DELETE CASCADE | Внешний ключ на пару |
| `student_id` | `INTEGER` | NOT NULL, FK $\rightarrow$ `students(id)` ON DELETE CASCADE | Внешний ключ на студента |
| `status` | `VARCHAR(25)` | NOT NULL, DEFAULT 'ABSENT_UNEXCUSED', CHECK(status IN ('PRESENT', 'ABSENT_UNEXCUSED', 'ABSENT_EXCUSED', 'MANUAL_CONFIRM', 'LATE')) | Статус присутствия |
| `checkin_time` | `TIMESTAMP` | NULL | Точное время фиксации чекина |
| `client_lat` | `REAL` | NULL | Координата широты с устройства студента |
| `client_lon` | `REAL` | NULL | Координата долготы с устройства студента |
| `distance_meters` | `REAL` | NULL | Расчетное расстояние $d$ до корпуса в метрах |
| `accuracy_meters` | `REAL` | NULL | Погрешность GPS датчика устройства ($\le 50$ м) |
| `verified_by_admin` | `BOOLEAN` | NOT NULL, DEFAULT 0 | Флаг ручного вмешательства старосты/зама |
| `excuse_reason` | `TEXT` | NULL | Обоснование уважительного пропуска |
| `created_at` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | Время создания записи |
| `updated_at` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | Время последнего обновления |

- **Ограничения уникальности:** `CONSTRAINT uq_pair_student UNIQUE (pair_id, student_id)`.
- **Индексы:** `idx_attendance_pair ON attendance(pair_id)`, `idx_attendance_student ON attendance(student_id)`.

### 2.6. Таблица `broadcast_messages` (Журнал рассылок и оповещений)
| Колонка | Тип данных | Ограничения | Описание |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | PK, AUTOINCREMENT | Идентификатор рассылки |
| `sender_id` | `INTEGER` | NOT NULL, FK $\rightarrow$ `students(id)` | Отправитель (Староста / Зам) |
| `message_type` | `VARCHAR(20)` | NOT NULL, CHECK(message_type IN ('CRITICAL', 'INFO')) | Тип сообщения |
| `title` | `VARCHAR(150)` | NOT NULL | Заголовок оповещения |
| `body` | `TEXT` | NOT NULL | Текст сообщения |
| `total_recipients` | `INTEGER` | NOT NULL, DEFAULT 0 | Количество целевых получателей |
| `read_count` | `INTEGER` | NOT NULL, DEFAULT 0 | Количество прочитавших |
| `sent_at` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | Время отправки |

### 2.7. Таблица `audit_log` (Журнал аудита действий администрации)
| Колонка | Тип данных | Ограничения | Описание |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | PK, AUTOINCREMENT | Идентификатор записи аудита |
| `admin_id` | `INTEGER` | NOT NULL, FK $\rightarrow$ `students(id)` | Администратор, выполнивший действие |
| `action` | `VARCHAR(50)` | NOT NULL | Название действия (`STATUS_OVERRIDE`, `PAIR_LOCK`, `BROADCAST`, etc.) |
| `target_id` | `INTEGER` | NULL | Идентификатор затронутой сущности |
| `details_json` | `TEXT` | NULL | Детали изменения (было/стало, параметры в JSON) |
| `created_at` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | Время совершения действия |

### 2.8. Прагмы и настройки SQLite для высокой конкурентности
```sql
PRAGMA journal_mode = WAL;         -- Разделение блокировок чтения и записи
PRAGMA synchronous = NORMAL;       -- Баланс надежности и дискового I/O
PRAGMA foreign_keys = ON;          -- Строгий контроль ссылочной целостности
PRAGMA busy_timeout = 5000;        -- Ожидание до 5 секунд при блокировке таблицы
PRAGMA cache_size = -64000;        -- 64 МБ оперативной памяти под кэш страниц
```

---

## 3. Криптографическая валидация Telegram initData и RBAC

### 3.1. Спецификация алгоритма валидации initData (HMAC-SHA256)
Аутентификация клиентских запросов TMA исключает использование классических паролей и базируется на криптографическом протоколе Telegram WebApp:

1. **Источник данных:** Клиентское приложение передает строку `window.Telegram.WebApp.initData` в HTTP-заголовке `X-Telegram-Init-Data`.
2. **Формат входящей строки:** Query-string вида `query_id=...&user=%7B...%7D&auth_date=1694178000&hash=5a9b...`.
3. **Шаг 1 (Парсинг):** Строка разбивается на пары ключ-значение с декодированием URL-символов.
4. **Шаг 2 (Извлечение хэша):** Из словаря извлекается и удаляется параметр `hash`. Если `hash` отсутствует — отклонение с кодом `401 Unauthorized`.
5. **Шаг 3 (Проверка свежести `auth_date`):**
   - Значение `auth_date` переводится в `int` (Unix epoch timestamp).
   - Вычисляется разница с серверным временем: $\Delta t = |t_{server} - auth\_date|$.
   - Если $\Delta t > 86400$ секунд (24 часа), сессия считается просроченной $\rightarrow$ ошибка `401 Unauthorized` (`"Session expired"`).
6. **Шаг 4 (Формирование контрольной строки):**
   - Все оставшиеся параметры сортируются по алфавиту ключей в лексикографическом порядке.
   - Формируется строка проверки данных (`data_check_string`):
     ```python
     data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
     ```
7. **Шаг 5 (Вычисление секретного ключа):**
   - Вычисляется HMAC-SHA256 от токена бота (`BOT_TOKEN`) с константным ключом `b"WebAppData"`:
     ```python
     secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
     ```
8. **Шаг 6 (Вычисление и сравнение контрольной подписи):**
   - Вычисляется HMAC-SHA256 от `data_check_string` с использованием `secret_key`:
     ```python
     calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
     ```
   - Производится безопасное сравнение во избежание timing-атак:
     ```python
     is_valid = hmac.compare_digest(calculated_hash, received_hash)
     ```
9. **Шаг 7 (Разрешение пользователя):**
   - Из распарсенного поля `user` (JSON) извлекается `user["id"]` (`telegram_id`).
   - Производится поиск в БД `students` по `telegram_id`.
   - Если пользователь найден и `status == 'ACTIVE'`, формируется объект контекста `User` с его ролью (`STUDENT`, `ZAM`, `STAROSTA`).
   - Если пользователь не найден или заблокирован — `403 Forbidden`.

### 3.2. Матрица разграничения доступа (RBAC Matrix)

| Ресурс / Действие | Студент (`STUDENT`) | Замстаросты (`ZAM`) | Староста (`STAROSTA`) |
| :--- | :---: | :---: | :---: |
| `POST /auth/telegram` | ✅ | ✅ | ✅ |
| `GET /schedule/today` | ✅ (своя подгруппа) | ✅ (все расписание) | ✅ (все расписание) |
| `POST /attendance/checkin` | ✅ | ✅ | ✅ |
| `GET /attendance/grid/{pair_id}` | ❌ | ✅ | ✅ |
| `PATCH /attendance/override` | ❌ | ✅ (с записью в аудит) | ✅ (с записью в аудит) |
| `POST /attendance/lock/{pair_id}` | ❌ | ❌ | ✅ (строго) |
| `POST /reports/export` | ❌ | ✅ | ✅ |
| `POST /alerts/broadcast` (CRITICAL) | ❌ | ❌ | ✅ (строго) |
| `POST /alerts/broadcast` (INFO) | ❌ | ✅ | ✅ |
| Управление вайтлистом и назначение Зама | ❌ | ❌ | ✅ |

---

## 4. Алгоритм геочекина (Haversine), координаты корпусов и правила временных окон

### 4.1. Математическая модель расчета дистанции (Haversine Formula)
Для вычисления геодезического расстояния на сфере между координатами студента $(\varphi_1, \lambda_1)$ и центра аудиторного корпуса $(\varphi_2, \lambda_2)$ используется формула гаверсинусов:

$$\Delta \varphi = \frac{(\text{lat}_2 - \text{lat}_1) \cdot \pi}{180}, \quad \Delta \lambda = \frac{(\text{lon}_2 - \text{lon}_1) \cdot \pi}{180}$$

$$a = \sin^2\left(\frac{\Delta \varphi}{2}\right) + \cos\left(\frac{\text{lat}_1 \cdot \pi}{180}\right) \cdot \cos\left(\frac{\text{lat}_2 \cdot \pi}{180}\right) \cdot \sin^2\left(\frac{\Delta \lambda}{2}\right)$$

$$c = 2 \cdot \operatorname{atan2}\left(\sqrt{a}, \sqrt{1 - a}\right) \quad \text{или} \quad 2 \cdot \arcsin(\sqrt{a})$$

$$d = R_{\text{earth}} \cdot c$$

где средний радиус Земли принят равным $R_{\text{earth}} = 6\,371\,000$ метров ($6\,371$ км).

### 4.2. Критерии валидации геочекина
1. **Точность GPS датчика (`accuracy`):**
   - Порог: $accuracy \le 50.0$ метров.
   - Если $accuracy > 50.0$ м $\rightarrow$ отказ в регистрации присутствия, ошибка `400 Bad Request` (`code: INACCURATE_GPS`).
2. **Допустимый радиус валидации (`radius_meters`):**
   - Порог по умолчанию: $d \le 150.0$ метров (может переопределяться индивидуально для каждого слота в `schedule_slots.radius_meters`).
   - Если $d \le 150.0$ м $\rightarrow$ статус `PRESENT`, запись координат и расчетного расстояния.
   - Если $d > 150.0$ м $\rightarrow$ отказ, ошибка `400 Bad Request` (`code: OUT_OF_BOUNDS`), вывод сообщения с точным указанием дистанции студента до корпуса.
3. **Защита от спуфинга времени (Timestamp delta):**
   - $|t_{client\_sensor} - t_{server}| \le 30$ секунд.

### 4.3. Координаты учебных корпусов БГПУ
В расписании и шаблонах слотов зафиксированы координаты основных локаций:
- **Главный корпус БГПУ:**
  - Широта (`lat`): `55.751244` (или `54.726140` в Уфе / эталонные координаты слота)
  - Долгота (`lon`): `37.618423` (или `55.945280` в Уфе)
  - Радиус: `150` метров
- **Корпус Б / Учебный корпус №2:**
  - Широта (`lat`): `55.753100`
  - Долгота (`lon`): `37.621000`
  - Радиус: `150` метров

### 4.4. Сетка звонков пар и интервалы чекина
Сетка занятий для группы 240326 Матинф:
| Номер пары | Время проведения | Окно открытия чекина (–5 мин) | Окно закрытия чекина (+15 мин) | Длительность окна |
| :---: | :---: | :---: | :---: | :---: |
| **1 пара** | 08:30 – 10:00 | **08:25** | **08:45** | 20 минут |
| **2 пара** | 10:15 – 11:45 | **10:10** | **10:30** | 20 минут |
| **3 пара** | 12:00 – 13:30 | **11:55** | **12:15** | 20 минут |
| **4 пара** | 14:00 – 15:30 | **13:55** | **14:15** | 20 минут |
| **5 пара** | 15:45 – 17:15 | **15:40** | **16:00** | 20 минут |
| **6 пара** | 17:30 – 19:00 | **17:25** | **17:45** | 20 минут |

**Правила окон:**
- Чекин разрешен строго в интервале $[time\_start - 5\text{м} \dots time\_start + 15\text{м}]$.
- До $time\_start - 5\text{м}$: статус `CHECKIN_NOT_OPEN`, отображение обратного таймера.
- После $time\_start + 15\text{м}$: статус `TIME_EXPIRED`. Если студент пытается отметиться, возвращается `400 Bad Request`.
- Если пара зафиксирована (`is_locked == true`): статус `PAIR_LOCKED`.

---

## 5. Спецификация REST API (FastAPI)

Базовый путь: `/api/v1`  
Заголовок авторизации: `X-Telegram-Init-Data`  
Формат ошибок: RFC 7807 (`application/problem+json` или `application/json`)

```json
{
  "type": "https://errors.starosta.app/out-of-bounds",
  "title": "Геолокация вне допустимого радиуса",
  "status": 400,
  "detail": "Вы находитесь на расстоянии 340 м от корпуса Б при лимите 150 м.",
  "instance": "/api/v1/attendance/checkin",
  "data": {
    "distance": 340.5,
    "limit": 150
  }
}
```

### 5.1. `GET /api/v1/health`
- **Назначение:** Мониторинг жизнеспособности сервиса, подключения к SQLite и активности бота.
- **Роли:** Публичный (без авторизации).
- **Response 200 OK:**
  ```json
  {
    "status": "healthy",
    "database": "connected",
    "telegram_bot": "active",
    "server_time": "2026-09-08T18:00:00+03:00"
  }
  ```

### 5.2. `POST /api/v1/auth/telegram`
- **Назначение:** Валидация криптографической подписи WebApp initData, выдача профиля и прав доступа.
- **Роли:** Любая (включая новых пользователей).
- **Headers:** `X-Telegram-Init-Data: query_id=...&hash=...`
- **Response 200 OK:**
  ```json
  {
    "user": {
      "id": 14,
      "telegram_id": 987654321,
      "full_name": "Иванов Иван Иванович",
      "subgroup": 1,
      "role": "STAROSTA",
      "status": "ACTIVE"
    },
    "permissions": {
      "can_view_grid": true,
      "can_override_status": true,
      "can_lock_pairs": true,
      "can_broadcast_critical": true,
      "can_export_reports": true
    },
    "current_week": {
      "week_number": 3,
      "week_type": "ODD",
      "is_study_day": true
    }
  }
  ```
- **Response 401 Unauthorized:**
  ```json
  {
    "title": "Недействительная подпись initData",
    "status": 401,
    "detail": "Подпись данных Telegram не прошла криптографическую проверку HMAC-SHA256."
  }
  ```

### 5.3. `GET /api/v1/schedule/today`
- **Назначение:** Получение пар текущего дня с геокоординатами, статусом окон чекина и отметкой студента.
- **Роли:** `STUDENT`, `ZAM`, `STAROSTA`.
- **Response 200 OK:**
  ```json
  {
    "date": "2026-09-08",
    "day_of_week": 2,
    "week_type": "EVEN",
    "pairs": [
      {
        "pair_id": 102,
        "pair_number": 1,
        "time_start": "08:30",
        "time_end": "10:00",
        "subject": "Высшая математика",
        "teacher": "Смирнов А. В.",
        "type": "LECTURE",
        "room": "304",
        "building": "Главный корпус",
        "building_coordinates": {
          "lat": 55.751244,
          "lon": 37.618423
        },
        "checkin_status": {
          "is_active": false,
          "window_start": "08:25",
          "window_end": "08:45",
          "reason_closed": "TIME_EXPIRED"
        },
        "my_attendance": {
          "status": "PRESENT",
          "distance": 42.1,
          "checkin_time": "2026-09-08T08:34:12"
        }
      },
      {
        "pair_id": 103,
        "pair_number": 2,
        "time_start": "10:15",
        "time_end": "11:45",
        "subject": "Операционные системы (Лаб)",
        "teacher": "Козлов Д. С.",
        "type": "LAB",
        "room": "212-Б",
        "building": "Корпус Б",
        "building_coordinates": {
          "lat": 55.753100,
          "lon": 37.621000
        },
        "checkin_status": {
          "is_active": true,
          "window_start": "10:10",
          "window_end": "10:30",
          "seconds_remaining": 540
        },
        "my_attendance": null
      }
    ]
  }
  ```

### 5.4. `POST /api/v1/attendance/checkin`
- **Назначение:** Фиксация геочекина студента на пару.
- **Роли:** `STUDENT`, `ZAM`, `STAROSTA`.
- **Request Body:**
  ```json
  {
    "pair_id": 103,
    "client_lat": 55.753140,
    "client_lon": 37.620950,
    "accuracy": 18.5,
    "timestamp": 1725801900
  }
  ```
- **Response 200 OK:**
  ```json
  {
    "status": "PRESENT",
    "pair_id": 103,
    "distance_meters": 32.4,
    "checkin_time": "2026-09-08T10:17:34",
    "message": "Присутствие успешно подтверждено!"
  }
  ```
- **Response 400 Bad Request (Вне радиуса):**
  ```json
  {
    "type": "https://errors.starosta.app/out-of-bounds",
    "title": "Геолокация вне аудитории",
    "status": 400,
    "detail": "Вы находитесь вне аудиторного фонда.",
    "data": {
      "distance": 312.8,
      "max_allowed": 150.0
    }
  }
  ```
- **Response 400 Bad Request (Неточный GPS / Закрытое окно / Пара заперта):**
  - При `accuracy > 50`: `"detail": "Точность GPS датчика (85.2 м) превышает допустимый лимит (50 м)."`
  - При чекине вне окна: `"detail": "Окно чекина закрыто для данной пары."`
  - При `is_locked == true`: `"detail": "Журнал пары зафиксирован старостой."`

### 5.5. `GET /api/v1/attendance/grid/{pair_id}`
- **Назначение:** Интерактивная шахматка посещаемости группы на пару.
- **Роли:** `STAROSTA`, `ZAM`.
- **Response 200 OK:**
  ```json
  {
    "pair_id": 103,
    "subject": "Операционные системы (Лаб)",
    "is_locked": false,
    "summary": {
      "total_students": 28,
      "present_count": 24,
      "absent_unexcused_count": 3,
      "absent_excused_count": 1,
      "manual_confirmed_count": 1
    },
    "students": [
      {
        "student_id": 1,
        "full_name": "Александров Александр",
        "subgroup": 1,
        "status": "PRESENT",
        "badge_color": "green",
        "distance": 15.2,
        "checkin_time": "10:12:05",
        "verified_by_admin": false
      },
      {
        "student_id": 2,
        "full_name": "Борисов Борис",
        "subgroup": 1,
        "status": "MANUAL_CONFIRM",
        "badge_color": "yellow",
        "distance": null,
        "checkin_time": null,
        "verified_by_admin": true,
        "note": "Разряжен аккумулятор"
      },
      {
        "student_id": 3,
        "full_name": "Волков Владимир",
        "subgroup": 1,
        "status": "ABSENT_EXCUSED",
        "badge_color": "purple",
        "excuse_reason": "Справка №421"
      }
    ]
  }
  ```
- **Response 403 Forbidden:** При попытке вызова обычным студентом.

### 5.6. `PATCH /api/v1/attendance/override`
- **Назначение:** Ручная смена статуса присутствия студента старостой или замом.
- **Роли:** `STAROSTA`, `ZAM`.
- **Request Body:**
  ```json
  {
    "pair_id": 103,
    "student_id": 2,
    "new_status": "ABSENT_EXCUSED",
    "excuse_reason": "Заявление на имя декана от 08.09"
  }
  ```
- **Response 200 OK:**
  ```json
  {
    "success": true,
    "pair_id": 103,
    "student_id": 2,
    "status": "ABSENT_EXCUSED",
    "updated_at": "2026-09-08T10:25:10"
  }
  ```

### 5.7. `POST /api/v1/attendance/lock/{pair_id}`
- **Назначение:** Запирание журнала пары (запрет последующего чекина).
- **Роли:** `STAROSTA` (строго, Зам получает 403).
- **Response 200 OK:**
  ```json
  {
    "success": true,
    "pair_id": 103,
    "is_locked": true,
    "locked_at": "2026-09-08T11:45:00"
  }
  ```

### 5.8. `POST /api/v1/alerts/broadcast`
- **Назначение:** Отправка экстренного или информационного оповещения группе.
- **Роли:** `STAROSTA` (типы `CRITICAL` и `INFO`), `ZAM` (только `INFO`).
- **Request Body:**
  ```json
  {
    "type": "CRITICAL",
    "title": "Перенос пары",
    "body": "Пара по ОС перенесена в аудиторию 401 Корпуса А!"
  }
  ```
- **Response 202 Accepted:**
  ```json
  {
    "broadcast_id": 7,
    "queued_recipients": 28,
    "channel_posted": true,
    "status": "SENDING"
  }
  ```

### 5.9. `POST /api/v1/reports/export`
- **Назначение:** Формирование официальной ведомости деканата в Excel.
- **Роли:** `STAROSTA`, `ZAM`.
- **Request Body:**
  ```json
  {
    "date_from": "2026-09-01",
    "date_to": "2026-09-08",
    "delivery_method": "TELEGRAM_DM"
  }
  ```
- **Response 200 OK:**
  ```json
  {
    "file_name": "Рапортичка_240326_01.09-08.09.xlsx",
    "delivered_to_telegram": true,
    "total_pairs": 24,
    "total_absent_hours": 18
  }
  ```

---

## 6. Требования к официальной ведомости деканата (Excel / openpyxl)

### 6.1. Университетский стандарт оформления
- **Целевая аудитория:** Деканат факультета физико-математического образования БГПУ, куратор группы 240326.
- **Формат файла:** Microsoft Excel OpenXML (`.xlsx`), создаваемый библиотекой `openpyxl`.
- **Структура документа (Лист 1):**
  1. **Шапка документа (Строки 1–4):**
     - Строка 1: «БАШКИРСКИЙ ГОСУДАРСТВЕННЫЙ ПЕДАГОГИЧЕСКИЙ УНИВЕРСИТЕТ ИМ. М. АКМУЛЛЫ» (по центру, Bold, 14pt).
     - Строка 2: «Факультет физико-математического образования | Академическая группа 240326 «Матинф»» (12pt).
     - Строка 3: «ЖУРНАЛ УЧЕТА ПОСЕЩАЕМОСТИ УЧЕБНЫХ ЗАНЯТИЙ (РАПОРТИЧКА)» (Bold, 12pt).
     - Строка 4: «Отчетный период: с {date_from} по {date_to} | Учебная неделя: №{week_number} ({week_type})» (Italic, 11pt).
  2. **Табличная сетка (Двухуровневый Header):**
     - Заголовок Уровень 1:
       - Колонка A: «№ п/п» (объединение строк 6:7).
       - Колонка B: «ФИО Студента» (объединение строк 6:7).
       - Колонки дней недели: Понедельник, Вторник, Среда, Четверг, Пятница, Суббота (каждый день объединяет по 6 подколонок пар).
       - Сводные колонки: «ИТОГО ПРОПУЩЕНО ЧАСОВ» (объединяет 3 подколонки: Неуваж. (Н), Уваж. (У), Всего).
     - Заголовок Уровень 2 (Строка 7):
       - Под каждым днем недели: номера пар `1 | 2 | 3 | 4 | 5 | 6`.
       - Под сводкой: `Н (час) | У (час) | Всего (час)`.
  3. **Строки студентов (Строка 8 и далее):**
     - Колонка A: Порядковый номер (1, 2, ... N).
     - Колонка B: Полное ФИО строго по алфавиту.
     - Ячейки посещаемости:
       - `·` (точка) или пусто — присутствовал (`PRESENT`, `MANUAL_CONFIRM`).
       - `Н` — пропуск без уважительной причины (`ABSENT_UNEXCUSED`).
       - `У` — пропуск по уважительной причине (`ABSENT_EXCUSED`).
       - `О` — опоздание (`LATE`).
  4. **Формулы в строках студентов:**
     - 1 академическая пара = 2 академических часа.
     - Подсчет неуважительных часов:  
       `=COUNTIF(C8:AK8, "Н") * 2`
     - Подсчет уважительных часов:  
       `=COUNTIF(C8:AK8, "У") * 2`
     - Суммарный пропуск студента:  
       `=AL8 + AM8` (сумма ячеек Н и У).
  5. **Итоговая строка по группе («ИТОГО ПО ГРУППЕ»):**
     - В конце таблицы строка с жирным начертанием.
     - Формула суммы пропущенных часов по всем студентам:  
       `=SUM(AL8:AL37)` и `=SUM(AM8:AM37)`.

### 6.2. Стилизация ячеек через openpyxl
- **Шрифты:** `Font(name="Calibri", size=11)`, для заголовков `Font(name="Calibri", size=11, bold=True)`.
- **Границы (Borders):** Тонкая сплошная рамка вокруг всех ячеек с данными (`Border(top=thin, bottom=thin, left=thin, right=thin)`), двойная рамка для итоговой строки (`bottom=double`).
- **Выравнивание (Alignment):**
  - ФИО: по левому краю (`Alignment(horizontal="left", vertical="center")`).
  - Номера пар, отметки (`Н`, `У`, `О`): по центру (`Alignment(horizontal="center", vertical="center")`).
- **Цветовые акценты (Fills):**
  - Шапка: легкий серый фон `PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")`.
  - Подсветка пропусков: ячейка `Н` с мягким красным акцентом, `У` — с мягким сиреневым акцентом.
- **Автоподбор ширины колонок:** Скрипт рассчитывает `max_len` по содержимому и устанавливает `column_dimensions[col].width`.

### 6.3. Регламент формирования и доставки
1. **По запросу старосты:** Мгновенная сборка за заданный интервал и отправка в личные сообщения Telegram файлом `.xlsx`.
2. **Фоновый автотриггер:** APScheduler `AsyncIOScheduler` настроен на cron:  
   `trigger = CronTrigger(day_of_week='sat', hour=16, minute=0, timezone=settings.TIMEZONE)`.  
   Каждую субботу в 16:00 собираются данные за завершившуюся неделю (Пн-Сб), формируется файл `Рапортичка_240326_Неделя_{N}.xlsx` и отправляется старосте и его заместителю.

---

## 7. Спецификация взаимодействия с Telegram-ботом (aiogram 3.x)

### 7.1. Регистрация команд бота
- `/start` — Запуск онбординга или открытие главного меню.
- `/status` — Просмотр текущей пары, статуса чекина и личной статистики посещаемости.
- `/report` — Запрос на формирование и отправку Excel-рапортички (только `STAROSTA`, `ZAM`).
- `/help` — Руководство по работе с ботом и геочекином.

### 7.2. Механика онбординга и 1-клик одобрения старостой
1. При команде `/start` неавторизованному пользователю выводится текст:
   *«👋 Привет! Это бот группы 240326 «Матинф». Для доступа к расписанию и чекину выберите свое имя из списка группы:»*
2. Клавиатура формируется динамически из базы данных:
   - Инлайн-кнопки с ФИО студентов, у которых `telegram_id IS NULL`.
   - Если список большой — пагинация по 8–10 фамилий на страницу (`◀️ Назад`, `Вперед ▶️`).
3. При клике на фамилию:
   - Бот запрашивает подтверждение: *«Вы действительно Иванов Иван Иванович (1 подгруппа)?»*
   - Кнопки: `[ ✅ Да, это я ]` / `[ ❌ Отмена ]`.
4. При подтверждении:
   - Запись переходит в статус `PENDING`.
   - Студенту выводится сообщение: *«⏳ Заявка отправлена старосте группы на подтверждение.»*
5. Старосте в Telegram (`STAROSTA_TELEGRAM_ID`) отправляется сообщение:
   ```text
   🔔 Заявка на регистрацию в группе 240326:
   👤 Пользователь: @username (ID: 123456789)
   📋 ФИО в списке: Иванов Иван Иванович
   👥 Подгруппа: 1
   ```
   с инлайн-клавиатурой:
   ```text
   [ ✅ Подтвердить ]  (callback: approve:{student_id}:{tg_id})
   [ ❌ Отклонить ]     (callback: reject:{student_id})
   ```
6. Обработка нажатия старостой:
   - **Одобрение:**
     - `UPDATE students SET telegram_id = :tg_id, status = 'ACTIVE' WHERE id = :student_id`.
     - Сообщение старосты редактируется: `✅ Заявка Иванова И. И. одобрена.`
     - Студенту отправляется сообщение: *«🎉 Ваша регистрация подтверждена! Добро пожаловать в АРМ Старосты.»* с кнопкой открытия Mini App.
   - **Отклонение:**
     - Запись студента освобождается (`telegram_id = NULL`, `status = 'PENDING'`).
     - Сообщение старосты редактируется: `❌ Заявка отклонена.`
     - Студенту отправляется: *«❌ Ваша заявка была отклонена старостой. Если произошла ошибка, обратитесь к старосте лично.»*

### 7.3. Интеграция с Telegram Mini App
- Настройка кнопки **Menu Button** через Bot API:
  ```python
  await bot.set_chat_menu_button(
      menu_button=MenuButtonWebApp(
          text="📱 Открыть пульт",
          web_app=WebAppInfo(url=settings.FRONTEND_URL)
      )
  )
  ```
- В главном меню и в ответах бота отправляется инлайн-кнопка с типом `web_app`:
  ```python
  InlineKeyboardButton(text="🚀 Запустить Mini App", web_app=WebAppInfo(url=settings.FRONTEND_URL))
  ```

### 7.4. Модуль рассылки оповещений (Broadcaster)
1. **Критический алерт (`CRITICAL`):**
   - Вызывается старостой через TMA или интерфейс бота.
   - Текст сообщения форматируется с пометкой `🚨 ЭКСТРЕННОЕ ОПОВЕЩЕНИЕ`.
   - Шаг 1: Публикация в общий групповой чат `GROUP_CHAT_ID` с тегом `@all` / упоминанием всех активных студентов.
   - Шаг 2: Фоновый цикл отправки в личные сообщения каждому студенту из таблицы `students` с `status = 'ACTIVE'` и непустым `telegram_id`.
   - Защита от троттлинга Telegram: пауза 0.05 сек между отправками, перехват исключений `TelegramForbiddenError` (если бот заблокирован пользователем) и `TelegramRetryAfter`.
   - Фиксация в `broadcast_messages`: подсчет успешных доставок.
2. **Информационное объявление (`INFO`):**
   - Отправка сообщения с пометкой `📢 ОБЪЯВЛЕНИЕ` только в групповой чат `GROUP_CHAT_ID` без персональных ЛС.

---

## 8. Итоговая таблица обнаруженных фичей (Features Discovered)

| # | Категория | Фича | Описание | Входные данные | Выходные данные | Поведение при ошибке | Источник |
|---|---|---|---|---|---|---|---|
| 1 | Auth & RBAC | HMAC-SHA256 InitData Validation | Валидация подлинности запуска TMA через Telegram Bot Token | Заголовок `X-Telegram-Init-Data` | 200 OK + JSON профиля (`id`, `role`, `status`, `permissions`) | 401 Unauthorized (неверный хэш или устаревший `auth_date` > 24ч) | `docs/ARCHITECTURE.md`, `docs/API.md` |
| 2 | Auth & RBAC | Ролевой доступ (RBAC) | Разграничение прав между Студентом, Замстаросты и Старостой | Роль пользователя в токене/сессии | Доступ к эндпоинтам шахматки, алертов, отчетов | 403 Forbidden ("Insufficient permissions") | `docs/SRS.md`, `docs/ARCHITECTURE.md` |
| 3 | Onboarding | Pre-seeded Whitelist | Предзагруженный список группы 240326 Матинф с номерами подгрупп | ФИО студентов, подгруппа (1 или 2) | Список доступных ФИО без привязки `telegram_id` | Сообщение об отсутствии свободных фамилий | `docs/SRS.md`, `docs/DATABASE.md` |
| 4 | Onboarding | 1-Click Approval Старостой | Подтверждение привязки профиля студента инлайн-кнопками в Telegram | Callback `approve:{id}:{tg_id}` / `reject:{id}` | Активация аккаунта (`ACTIVE`), уведомление студента | Сообщение об ошибке или истечении срока заявки | `docs/SRS.md`, `ORIGINAL_REQUEST.md` |
| 5 | Schedule | Учебная сетка и четность недель | Вычисление текущего дня, четности недели (ODD/EVEN) и пар по подгруппе | Текущая дата, подгруппа студента | Список пар на день с метаданными и координатами | Пустой список пар (выходной день) | `docs/SRS.md`, `docs/API.md` |
| 6 | Attendance | Geolocation Haversine Checkin | Подтверждение присутствия по GPS-координатам мобильного устройства | `pair_id`, `client_lat`, `client_lon`, `accuracy`, `timestamp` | 200 OK (`status: PRESENT`, `distance_meters`) | 400 Bad Request (`OUT_OF_BOUNDS`, указание расстояния) | `docs/SRS.md`, `docs/API.md` |
| 7 | Attendance | GPS Accuracy Filter | Отсечение неточных координат сотового позиционирования | `accuracy` с датчика устройства | Пропуск при $accuracy \le 50$ м | 400 Bad Request (`INACCURATE_GPS`) | `docs/SRS.md`, `docs/API.md` |
| 8 | Attendance | Временные окна чекина | Чекин строго за 5 мин до начала и первые 15 мин пары | Серверное время, `time_start` пары | Пропуск чекина в окне [-5м...+15м] | 400 Bad Request (`CHECKIN_WINDOW_CLOSED`) | `docs/SRS.md`, `docs/API.md` |
| 9 | Attendance | Шахматка посещаемости (Grid) | Интерактивная таблица посещаемости пары для старосты | `pair_id` | Сетка студентов со статусами и цветовыми бейджами | 403 Forbidden (для обычных студентов) | `docs/API.md`, `docs/SRS.md` |
| 10 | Attendance | Ручной оверрайд статусов | Смена статуса старостой (кликом или с указанием причины) | `pair_id`, `student_id`, `new_status`, `excuse_reason` | Обновленный статус + запись в `audit_log` | 400 Bad Request (недопустимый статус) | `docs/SRS.md`, `docs/API.md` |
| 11 | Attendance | Запирание журнала пары (Lock) | Фиксация журнала старостой, закрывающая дальнейший чекин | `pair_id` | `is_locked = 1`, `locked_at = NOW()` | 403 Forbidden (если вызывает Замстаросты) | `docs/SRS.md`, `docs/API.md` |
| 12 | Reporting | Генератор ведомости деканата | Сборка рапортички в формате `.xlsx` с формулами `openpyxl` | `date_from`, `date_to`, `delivery_method` | Файл `.xlsx`, доставка старосте в Telegram | Ошибка генерации при пустой выборке | `docs/SRS.md`, `docs/API.md` |
| 13 | Reporting | Еженедельный автоотчет (Cron) | Автоматическая выгрузка рапортички каждую субботу в 16:00 | Триггер APScheduler | Отправка `.xlsx` старосте и замстаросты | Логирование ошибки в `logs/app.log` | `docs/SRS.md`, `docs/DEPLOYMENT.md` |
| 14 | Alerts | Критический алерт (@all + ЛС) | Экстренное гарантированное оповещение всех студентов группы | `title`, `body`, тип `CRITICAL` | Пост в группу + персональные ЛС студентам | Обработка заблокированных ботов без падения | `docs/SRS.md`, `docs/API.md` |
| 15 | Alerts | Информационное объявление | Публикация сообщения в группу без рассылки в ЛС | `title`, `body`, тип `INFO` | Пост в групповой чат | Ошибка Telegram API при неверном `GROUP_CHAT_ID` | `docs/SRS.md`, `docs/API.md` |
| 16 | System | Healthcheck & Monitoring | Проверка статуса БД, aiogram-бота и серверного времени | `GET /api/v1/health` | JSON со статусами подсистем | 500 / 503 при деградации БД | `docs/DEPLOYMENT.md` |
| 17 | Database | WAL Mode & Concurrency | Обеспечение параллельного чекина 30 студентов за 5 сек | Запросы чекина в транзакциях SQLite | Успешная запись без `database locked` | Срабатывание `busy_timeout = 5000` | `docs/DATABASE.md` |
| 18 | Database | Онлайн-бэкап базы данных | Резервное копирование базы `database.sqlite` без остановки сервера | Ежедневный триггер в 23:59 | Снэпшот в `backups/backup_YYYYMMDD.sqlite` | Уведомление в приватный канал старосты | `docs/DATABASE.md` |

---

## 9. Граничные случаи и поведение системы (Edge Cases)

| # | Фича | Входные данные / Ситуация | Наблюдаемое / Специфицированное поведение |
|---|---|---|---|
| 1 | Geocheckin | Расстояние $d = 151$ м (превышение на 1 м) | Возврат ошибки 400 Bad Request (`type: out-of-bounds`, `distance: 151.0`, `max_allowed: 150.0`). Запись в статус `ABSENT_UNEXCUSED`. |
| 2 | Geocheckin | Погрешность GPS датчика $accuracy = 51$ м | Ошибка 400 Bad Request (`INACCURATE_GPS`). Предупреждение студенту выйти к окну или сбросить службы геолокации. |
| 3 | Geocheckin | Чекин в $08:24$ при начале пары в $08:30$ (за 6 мин до старта) | Ошибка 400 Bad Request (`CHECKIN_WINDOW_CLOSED`). В интерфейсе TMA кнопка неактивна, тикает таймер до $08:25$. |
| 4 | Geocheckin | Чекин в $08:46$ при начале пары в $08:30$ (прошло 16 мин) | Ошибка 400 Bad Request (`CHECKIN_WINDOW_CLOSED`). Чекин заблокирован со статусом `TIME_EXPIRED`. |
| 5 | Geocheckin | Рассинхронизация часов клиента и сервера более 30 сек | Отклонение запроса чекина как потенциального повторного воспроизведения (anti-spoofing). |
| 6 | InitData Auth | Срок жизни `auth_date` составляет 24 часа и 1 минуту | Ошибка 401 Unauthorized (`"Session expired"`). Требуется перезапуск TMA. |
| 7 | InitData Auth | Модификация хотя бы одного символа в `initData` на клиенте | Несовпадение вычисленного HMAC-SHA256 с переданным `hash`. Немедленный возврат 401 Unauthorized. |
| 8 | RBAC | Заместитель старосты (`ZAM`) пытается вызвать `/attendance/lock/{pair_id}` | Ошибка 403 Forbidden. Запирание пар разрешено исключительно роли `STAROSTA`. |
| 9 | RBAC | Обычный студент (`STUDENT`) пытается получить сетку посещаемости `/attendance/grid/{pair_id}` | Ошибка 403 Forbidden. Доступ имеют только `STAROSTA` и `ZAM`. |
| 10 | Onboarding | Два студента одновременно заявляют одно и то же ФИО | Первый получает статус `PENDING`. Для второго ФИО блокируется до решения старосты; если староста отклоняет первого, ФИО снова становится доступно. |
| 11 | Onboarding | Староста отклоняет заявку студента | Аккаунт студента отвязывается, `telegram_id` снова `NULL`, студенту направляется вежливое уведомление об отказе. |
| 12 | Subgroup split | 1-я подгруппа на Лабе в Корпусе Б (212-Б), 2-я подгруппа на Физкультуре в Главном корпусе | `schedule_slots` возвращает разные координаты корпусов для подгрупп 1 и 2 в один и тот же слот. Геочекин валидируется строго по корпусу своей подгруппы. |
| 13 | High Concurrency | Вся группа (30 человек) нажимает «Отметиться» в течение 5 секунд | За счет `PRAGMA journal_mode = WAL`, `synchronous = NORMAL` и `busy_timeout = 5000` запросы выполняются параллельно без сбоя `database locked`. |
| 14 | Broadcasting | 3 студента из группы заблокировали бота в Telegram | Бот ловит `TelegramForbiddenError`, логирует пропуск доставки для данных `telegram_id`, продолжает рассылку остальным 27 студентам и возвращает в отчете факт успешной доставки 27 адресатам. |
| 15 | Pair Lock | Староста зафиксировал пару (`is_locked = 1`), студент пытается отметиться | Бэкенд возвращает 400 Bad Request (`"Журнал пары зафиксирован старостой"`). В интерфейсе TMA отображается архивный бейдж. |
| 16 | Excel Export | Экспорт за период без пар (например, каникулы) | Генератор формирует корректный пустой бланк с шапкой группы 240326, списком студентов по алфавиту и нулями в формулах часов без падения `IndexError`. |
