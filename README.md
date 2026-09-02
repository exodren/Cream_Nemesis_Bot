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
| `CURRENT_SEASON` | номер сезона TOVA |
| `DATABASE_URL` | опционально, по умолчанию `data/bot.db` |

Узнать свой ID: напишите [@userinfobot](https://t.me/userinfobot).

## Права бота в чате

Для модерации добавьте бота **админом** чата с правами:

- удалять сообщения (желательно)
- блокировать пользователей
- ограничивать участников (mute)

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
| `/topicid` `/chatid` | ID чата и темы форума для `.env` |

## Техтребования

1. **SQLite WAL** — включается в `db/base.py` при старте (лог `journal_mode=wal`).
2. **FSM только в ЛС** — никнейм, бомбардиры, скриншоты; из группы — редирект.
3. **Безопасная модерация** — API ban/mute в `try/except`.

## Логи

Пишутся в `logs/bot.log` (консоль + файл).  
Ротация каждые **8 часов** → архивы `logs/bot_YYYY-MM-DD_HH.txt` (см. `logging_setup.py`).

## Документация

- `docs/TEST_PLAN.md` — полный план ручного тестирования кнопок и функций
- `docs/CHECKLIST.md` — краткий чеклист приёмки
- `docs/DEV_PLAN.md` / `docs/PLAN.md` — архитектура

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
