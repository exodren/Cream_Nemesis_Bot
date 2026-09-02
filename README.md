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
При обновлении кода **существующая** БД сохраняется: `create_all` создаёт только недостающие таблицы.

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
| `ADMIN_IDS` | Telegram ID админов через запятую (`/season_manage`, Quick-Kick) |
| `ADMIN_USERNAMES` | Юзерки с правами бота (warn/ban/TOVA), без @ |
| `TOVA_ADMIN_ID` | ID модератора TOVA (карточки на проверку) |
| `ADMINS_CN` / `ADMINS_LPL` / `ADMINS_RI` / `ADMINS_VSA` / `ADMINS_TOVA` | Юзерки для кнопки «Админы» в меню |
| `MAIN_CHAT_ID` | ID чата лиги: mute/ban, выходы, ссылки ЛПЛ / тренер / зал CN. Формат `-100…` |
| `RI_CHAT_ID` | ID чата турниров РИ. Если пусто — берётся `MAIN_CHAT_ID` |
| `VSA_CHAT_ID` | ID чата VSA (зал славы). Если пусто — берётся `MAIN_CHAT_ID` |
| `TOPIC_*` | ID тем форума. Пусто = кнопка не ведёт на битую ссылку. Снять: `/topicid` в теме |
| `CURRENT_SEASON` | стартовый номер сезона TOVA (при первом запуске); далее сезон ведётся в БД |
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
| `/pending_tova` | повторная рассылка матчей на проверке (админы TOVA) |
| `/topicid` `/chatid` | ID чата и темы форума для `.env` |

## TOVA: сезоны, архив, выходы

- Участники сезона хранятся в БД (`season_participants.is_active`).
- Таблица и бомбардиры **текущего** сезона — только активные игроки.
- **Архив сезонов** — TOVA → меню прошлых сезонов (статистика / таблица / бомбардиры).
- Выход или кик из `MAIN_CHAT_ID` → алерт админам в ЛС + кнопка **«Снять с турнира»**.
- `/season_manage` — завершить сезон или начать новый.
- Матчи `pending_admin` пересылаются при рестарте бота; вручную — `/pending_tova`.
- Навигация по inline-кнопкам в ЛС **редактирует** сообщение, а не плодит новые.

## Техтребования

1. **SQLite WAL** — включается в `db/base.py` при старте (лог `journal_mode=wal`).
2. **FSM только в ЛС** — никнейм, бомбардиры, скриншоты; из группы — редирект.
3. **Безопасная модерация** — API ban/mute в `try/except`.
4. **Уведомления** — без лишних эмодзи и технических формулировок в текстах для пользователей.

## Логи

Пишутся в `logs/bot.log` (консоль + файл).  
Ротация каждые **8 часов** → архивы `logs/bot_YYYY-MM-DD_HH.txt` (см. `logging_setup.py`).

## Документация (локально)

Папка `docs/` хранится **только на диске**, в GitHub не заливается (см. `.gitignore`).

| Файл | Назначение |
|------|------------|
| `docs/NEW_FEATURES.md` | описание новых функций |
| `docs/TEST_PLAN_SEASONS.md` | тест сезонов и деплоя (перед продом) |
| `docs/TEST_PLAN.md` | полный план ручного тестирования |
| `docs/CHECKLIST.md` | краткий чеклист приёмки |
| `docs/DEV_PLAN.md` / `docs/PLAN.md` | архитектура |

## Обновление на сервере (без потери БД и `.env`)

Путь на VPS: `/opt/Cream_Nemesis_Bot` (или ваш).

**`.env` и `data/bot.db` не в git** — `git pull` их **не перезаписывает**. Бэкап `.env` перед деплоем — страховка, восстанавливать обычно не нужно.

```bash
cd /opt/Cream_Nemesis_Bot

# страховка (опционально)
cp .env .env.bak.$(date +%Y%m%d)

git fetch origin
git reset --hard origin/main

docker compose up -d --build
docker compose logs -f bot --tail 80
```

Если `git pull` ругается на локальные правки — используйте `git reset --hard origin/main` (см. выше).

После обновления сравните `.env` с `.env.example` — **добавьте только недостающие ключи**, весь файл не копируйте:

```bash
grep -E '^[A-Z]' .env.example
```

**Не делайте** на проде, если нужно сохранить данные:

```bash
rm -f data/bot.db data/bot.db-wal data/bot.db-shm
```

При копировании БД для локального теста копируйте все три файла (`bot.db`, `-wal`, `-shm`) и останавливайте бот на сервере.

## Деплой (systemd, без Docker)

```ini
[Unit]
Description=Cream Nemesis Bot
After=network.target

[Service]
WorkingDirectory=/opt/Cream_Nemesis_Bot
ExecStart=/opt/Cream_Nemesis_Bot/.venv/bin/python bot.py
Restart=always
RestartSec=5
User=bot

[Install]
WantedBy=multi-user.target
```

Не коммитьте `.env` и `*.db`.
