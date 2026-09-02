# Cream Nemesis Bot

Telegram-бот лиги Cream Nemesis (`@CreamNemesis_bot`).

## Стек

- aiogram 3.x
- SQLAlchemy async + SQLite (**WAL**)
- Pillow (фото-таблицы TOVA)

## Запуск в Docker (рекомендуется на VPS)

Нужны Docker Engine и Compose v2.

```bash
cp .env.example .env   # Windows: copy .env.example .env
# заполните BOT_TOKEN, админов, чаты

docker compose up -d --build
docker compose logs -f bot
```

Данные: `./data/bot.db` (SQLite WAL). Логи: `./logs/bot.log`.

Остановка: `docker compose down`.  
Пересоздать **чистую** БД:

```bash
docker compose down
rm -f data/bot.db data/bot.db-wal data/bot.db-shm   # Windows: del data\bot.db
docker compose up -d
```

При старте таблицы создаются сами (`create_all`), если файла БД нет.  
При обновлении кода **существующая** БД сохраняется: `create_all` создаёт только недостающие таблицы (см. «Обновление на сервере»).

## Локально без Docker (Windows)

```powershell
cd C:\Users\User\Desktop\game_bot
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python bot.py
```

## Переменные `.env`

| Переменная | Описание |
|------------|----------|
| `BOT_TOKEN` | токен от @BotFather |
| `ADMIN_IDS` | Telegram ID админов через запятую |
| `ADMIN_USERNAMES` | Юзерки с правами бота (warn/ban/TOVA), без @ |
| `ADMINS_CN` / `ADMINS_LPL` / `ADMINS_RI` / `ADMINS_VSA` / `ADMINS_TOVA` | Юзерки для кнопки «Админы» в меню |
| `MAIN_CHAT_ID` | ID чата лиги: mute/ban **и** ссылки ЛПЛ / тренер / зал CN. Формат `-100…` |
| `RI_CHAT_ID` | ID чата турниров РИ. Если пусто — берётся `MAIN_CHAT_ID` |
| `VSA_CHAT_ID` | ID чата VSA (зал славы). Если пусто — берётся `MAIN_CHAT_ID` |
| `TOPIC_*` | ID тем форума. Пусто = кнопка не ведёт на битую ссылку. Снять: `/topicid` в теме |
| `CURRENT_SEASON` | стартовый номер сезона TOVA (при первом запуске); далее сезон ведётся в БД (`seasons`) |
| `DATABASE_URL` | опционально, по умолчанию `data/bot.db` |

Узнать свой ID: напишите [@userinfobot](https://t.me/userinfobot).

## Права бота в чате

Для модерации и алертов о выходе добавьте бота **админом** чата с правами:

- удалять сообщения (желательно)
- блокировать пользователей
- ограничивать участников (mute)
- **видеть список участников** (для событий `chat_member` / выход из чата)

Без прав команды `/warn` `/mute` `/ban` не роняют бота — отвечают текстом об ошибке прав.

## Команды

| Команда | Описание |
|---------|----------|
| `/start` | меню |
| `/help` | справка |
| `/cancel` | отмена FSM (ник / результат), только ЛС |
| `/go_tova` | поиск соперника |
| `/cancel_tova` | выход из очереди |
| `/result_tova nick1 8:2 nick2` | сдача результата (**только ЛС**) |
| `/warn` `/unwarn` `/mute` `/unmute` `/ban` `/unban` | админка (`ADMIN_IDS` или `ADMIN_USERNAMES`) |
| `/season_manage` | управление сезонами TOVA (**только** `ADMIN_IDS`) |
| `/pending_tova` | повторная рассылка матчей TOVA на проверке (`pending_admin`; админы TOVA) |
| `/topicid` `/chatid` | ID чата и темы форума для `.env` |

## Техтребования

1. **SQLite WAL** — включается в `db/base.py` при старте (лог `journal_mode=wal`).
2. **FSM только в ЛС** — никнейм, бомбардиры, скриншоты; из группы — редирект.
3. **Безопасная модерация** — API ban/mute в `try/except`.
4. **Сезоны TOVA** — участники привязаны к сезону (`season_participants.is_active`); таблицы и бомбардиры текущего сезона показывают только активных; прошлые сезоны — в меню **Архив сезонов**.
5. **Выход из чата** — алерт админам в ЛС + Quick-Kick (снять с турнира).
6. **Навигация в ЛС** — inline-меню редактирует сообщение на месте (`handlers/callback_ui.py`), чтобы не засорять чат.
7. **Pending TOVA** — при старте бота и по `/pending_tova` карточки матчей на проверке пересылаются админам TOVA.

## Сезоны, выходы, Quick-Kick

- При выходе или кике из `MAIN_CHAT_ID` бот шлёт алерт всем админам (`ADMIN_IDS` + `ADMIN_USERNAMES`, если писали `/start`).
- Под алертом — кнопка снятия с турнира (`is_active = False` в текущем сезоне).
- `/season_manage` — завершить сезон (архив + деактивация участников) или начать новый (номер +1, чистая база участников).
- TOVA → **Архив сезонов** — статистика, таблица и бомбардиры прошлых сезонов.
- Матчи `pending_admin` пересылаются админам TOVA при рестарте бота; вручную — `/pending_tova`.
- Номер текущего сезона хранится в таблице `seasons`; `CURRENT_SEASON` в `.env` используется только при первом bootstrap.

**Ручное тестирование:** `docs/TEST_PLAN_SEASONS.md` (пройти локально **до** деплоя на сервер).

## Логи

Пишутся в `logs/bot.log` (консоль + файл).  
Ротация каждые **8 часов** → архивы `logs/bot_YYYY-MM-DD_HH.txt` (см. `logging_setup.py`).

## Документация

- `docs/NEW_FEATURES.md` — **описание всех новых функций** (сезоны, архив, Quick-Kick, pending TOVA, редактирование ЛС)
- `docs/TEST_PLAN.md` — полный план ручного тестирования кнопок и функций
- `docs/TEST_PLAN_SEASONS.md` — тест сезонов, выходов из чата и Quick-Kick (**перед деплоем**)
- `docs/CHECKLIST.md` — краткий чеклист приёмки
- `docs/DEV_PLAN.md` / `docs/PLAN.md` — архитектура

## Обновление на сервере (без потери БД)

Сначала пройдите `docs/TEST_PLAN_SEASONS.md` локально. На VPS обновляйте **только код**, файл базы не трогайте.

```bash
cd /opt/game_bot   # или ваш путь
git pull
docker compose up -d --build
docker compose logs -f bot
```

Каталог `./data` (файлы `bot.db`, `bot.db-wal`, `bot.db-shm`) должен остаться на месте — он примонтирован в контейнер как volume. При старте SQLAlchemy выполняет `create_all`: **создаёт недостающие таблицы** (`seasons`, `season_participants`), уже существующие пользователи и матчи **не удаляются и не перезаписываются**. Bootstrap один раз заполнит участников сезона для игроков с никнеймом.

**Не делайте** на проде, если нужно сохранить данные:

```bash
rm -f data/bot.db data/bot.db-wal data/bot.db-shm
docker compose down   # с последующим удалением ./data
```

Пересоздание **чистой** БД — только осознанно (см. блок выше в разделе Docker).

### Без Docker (systemd)

```bash
cd /opt/game_bot
git pull
# venv и pip install -r requirements.txt при смене зависимостей
sudo systemctl restart cream-nemesis-bot
```

Путь к БД не меняйте; не удаляйте `data/bot.db`.

## Деплой (кратко)

На VPS можно держать polling через systemd, пример unit:

```ini
[Unit]
Description=Cream Nemesis Bot
After=network.target

[Service]
WorkingDirectory=/opt/game_bot
ExecStart=/opt/game_bot/.venv/bin/python bot.py
Restart=always
RestartSec=5
User=bot

[Install]
WantedBy=multi-user.target
```

Не коммитьте `.env` и `*.db`.
