# План: Cream Nemesis Bot

Прочитал ТЗ и шаблон `лист_таблицы.jpg`. Ниже план бота под ваш стек.

> **Актуальные дополнения к TOVA** (сезоны в БД, архив, выходы из чата, редактирование меню в ЛС): [`NEW_FEATURES.md`](NEW_FEATURES.md).

**Важно:** в ТЗ засвечен токен BotFather. Перед запуском отзовите его в [@BotFather](https://t.me/BotFather) → `/revoke` и положите новый только в `.env` (в репозиторий не коммитить).

---

## Суть продукта

Два слоя:
1. **Навигационный хаб** — меню, тексты регламентов, URL-кнопки в темы закрытых чатов.
2. **Игровая система TOVA** — регистрация, матчмейкинг, результаты, подтверждения, админ-модерация, статистика и фото-таблицы.

---

## Архитектура

```
game_bot/
├── .env
├── requirements.txt
├── bot.py                 # точка входа, Dispatcher, polling
├── config.py              # токен, admin ids, chat ids, ссылки
├── assets/
│   └── table_template.jpg # лист_таблицы.jpg
├── db/
│   ├── base.py            # engine, session, init
│   └── models.py          # Users, Matches, Goals, Warnings
├── keyboards/
│   ├── main.py            # главное меню (+ Админы)
│   ├── admins.py          # админы лиг из .env
│   ├── lpl.py / ri.py / tova.py / hall.py ...
│   └── urls.py            # t.me/c/... из MAIN/RI/VSA + TOPIC_*
├── handlers/
│   ├── start.py
│   ├── menu/              # регламент, правила, ЛПЛ, РИ, VSA, зал славы
│   ├── tova/              # регистрация, FSM никнейма, статы, таблицы
│   ├── matchmaking.py     # /go_tova
│   ├── results.py         # /result_tova + подтверждение
│   └── admin.py           # /warn /mute /ban /unmute /unban /unwarn + approve TOVA
├── services/
│   ├── tova_stats.py      # агрегации очков/голов
│   ├── table_image.py     # Pillow → BytesIO → BufferedInputFile
│   └── moderation.py      # warn/kick/ban логика
└── middlewares/
    └── db.py              # session на апдейт
```

**ORM:** SQLAlchemy 2.x async (`aiosqlite`) — проще контролировать транзакции вокруг матчей/подтверждений. Tortoise тоже ок, но для этой модели SQLAlchemy привычнее.

---

## Модель данных

| Таблица | Назначение |
|--------|------------|
| **Users** | `tg_id`, `username`, `nickname` (FC Mobile), `is_banned`, `created_at` |
| **Matches** | `player1_id`, `player2_id`, `score1`, `score2`, `status` (`pending_confirm` / `pending_admin` / `confirmed` / `rejected`), `screenshot_file_id`, `season`, `created_at` |
| **Goals** | `match_id`, `user_id`, `player_name` (футболист), `goals_count` |
| **Warnings** | `user_id`, `admin_id`, `reason`, `active`, `created_at` (счётчик = `COUNT` активных) |
| **Seasons** | `number`, `is_current`, `is_archived`, `started_at`, `ended_at` |
| **SeasonParticipant** | `user_id`, `season`, `is_active`, `joined_at`, `deactivated_at` |

Дополнительно (не в ТЗ, но нужно для `/go_tova`):
- **MatchQueue** или поле `Users.in_queue` / in-memory очередь с TTL — кто ждёт соперника.
- Номер текущего сезона: таблица `seasons` + bootstrap из `CURRENT_SEASON` в `.env`.

Очки TOVA: победа **3**, ничья **1**, поражение **0**. Голы — формат `забитые:пропущенные`, не KD.

---

## Навигация (меню)

Главное меню (`/start`) — `InlineKeyboardMarkup`:

| Кнопка | Поведение |
|--------|-----------|
| РЕГЛАМЕНТ / АКТИВ | текст + фото системы очков |
| ПРАВИЛА CN | длинный текст |
| ЛПЛ | submenu: Правила (текст) + 3 URL-кнопки (стата/бомбардиры/состав) |
| Режим Тренера | URL темы `MAIN_CHAT_ID` / `TOPIC_COACH` |
| Турниры РИ | текст + submenu (темы `RI_CHAT_ID`) |
| Турнир по ВСА | текст |
| Зал Славы CN | 3 URL (чаты MAIN / RI / VSA) |
| Админы | юзерки лиг из `ADMINS_*` |
| TOVA | submenu игровой логики |

Все `t.me/c/...` собираются в `keyboards/urls.py` из `MAIN_CHAT_ID` / `RI_CHAT_ID` / `VSA_CHAT_ID` и `TOPIC_*`. Пустой topic → callback «тема не настроена», не битая ссылка. Права бота: `ADMIN_IDS` + `ADMIN_USERNAMES`. Публичный список: кнопка «Админы» / `ADMINS_*`.

Глубина меню РИ→Таблицы→ЛЧ/ЛЕ/… — callback-дерево + кнопка «Назад» на каждом уровне. Тексты — константы/отдельные markdown-файлы, не хардкод в хендлерах.

---

## TOVA — ключевые флоу

### 1. Регистрация
- FSM: `waiting_nickname` после «Изменить никнейм».
- Первое текстовое сообщение в ЛС = никнейм → upsert в `Users`.
- «Удалить никнейм» — `nickname = NULL` (матчи в истории не трогать).

### 2. `/go_tova`
- Только зарегистрированные.
- Если очередь пуста → поставить в очередь, ответить «Ищем соперника…».
- Если есть другой игрок → сматчить, уведомить обоих (никнеймы + «сыграйте матч»).
- Нельзя матчить сам с собой; таймаут очереди (например 10–15 мин).

### 3. `/result_tova nick1 8:2 nick2`
- Парсинг regex: `^/result_tova\s+(\S+)\s+(\d+):(\d+)\s+(\S+)$`.
- Затем FSM: ввод бомбардиров (две строки как в ТЗ) + скриншот.
- Создать `Match` (`pending_confirm`) + `Goals`.
- Кнопки подтверждения второму игроку: ✅ / ❌.
- После обоих «да» → `pending_admin`; админам — карточка на approve/reject.
- Approve → `confirmed` → пересчёт статы (или on-the-fly агрегация по confirmed).

### 4. Статистика / таблицы
- **Статистика сезона** — текст (лидеры + топ-5 + totals).
- **Таблица TOVA** / **Бомбардиры TOVA** — Pillow поверх `лист_таблицы.jpg` → `BufferedInputFile`.
- **Статистика** — личная карточка по `tg_id`.

Пагинация фото-таблицы: если игроков много — несколько кадров или топ-N + «ещё» (иначе шрифт не влезет в шаблон).

---

## Pillow (`services/table_image.py`)

1. Открыть `assets/table_template.jpg`.
2. Зона контента: ~20% сверху (лого) и ~5% снизу (EST. 2024) не трогать.
3. Заголовок таблицы (золотой/угольный), колонки, строки никнеймов/очков.
4. Шрифт serif (Cinzel/Playfair/DejaVu Serif) — положить `.ttf` в `assets/fonts/`.
5. `BytesIO` → `BufferedInputFile(file=..., filename="table.png")`.

Два рендера: standings (`И В Н П Голы Очки`) и scorers (`N Игрок Голы Никнейм`).

---

## Админка

Права: список `ADMIN_IDS` в `.env` (+ опционально проверка `chat_member` status).

| Команда | Действие |
|---------|----------|
| `/warn @user` | +1 в Warnings; при 3 → ban + kick из чата |
| `/unwarn @user` | снять одно активное |
| `/mute @user N` | `restrict_chat_member` на N минут |
| `/unmute @user` | снять restrict |
| `/ban @user` | kick + ban flag |
| `/unban @user` | `unban_chat_member` + снять flag |

Нужен `MAIN_CHAT_ID` (и при необходимости отдельные чаты). Бот — админ чата с правом restrict/ban.

Approve/reject матчей TOVA — отдельные callback’и только для админов.

---

## Стек и рантайм

- **aiogram 3.x** + FSM Storage: `MemoryStorage` для старта, Redis позже если нужен persist.
- **SQLAlchemy async + aiosqlite**.
- **Pillow**.
- Запуск: long polling (`bot.py`); webhook — если вынесете на VPS с HTTPS.
- Конфиг: `pydantic-settings` / `python-dotenv`.

---

## Порядок реализации

1. Каркас: config, DB models, `/start`, главное меню, статические тексты + URL-кнопки.
2. Полное дерево меню (РИ таблицы, премии, зал славы и т.д.).
3. TOVA: никнейм FSM, `/go_tova`, `/result_tova` + подтверждения + админ approve.
4. Агрегации статы + Pillow-таблицы.
5. Модерация `/warn`…`/unban`.
6. Полировка: «Назад», валидации, пагинация таблиц, сезоны.

---

## Риски / решения заранее

| Риск | Решение |
|------|---------|
| URL `t.me/c/...` не открываются вне чата | Ожидаемо; подписать в UI «только для участников» |
| Коллизии никнеймов | Unique constraint + сообщение при дубле |
| Спорный результат | Двойное confirm + admin gate |
| Длинная таблица | Пагинация по 12–15 строк на фото |
| Токен в ТЗ | Revoke + `.env` |

---

Если план ок — могу сразу собрать каркас (структура проекта + меню + модели БД) или начать с полного TOVA-контура. Что важнее первым?
