# Cream Nemesis Bot

Telegram-бот лиги Cream Nemesis (`@CreamNemesis_bot`).

## Стек

- aiogram 3.x
- SQLAlchemy async + SQLite (**WAL**)
- APScheduler (планировщик cron-задач)
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
| `SUPER_ADMIN_IDS` | Telegram ID супер-администраторов, уровень 4-5 (через запятую). Абсолютный иммунитет от мута/бана/варна |
| `SUPER_ADMIN_USERNAMES` | Юзерки супер-админов (без @, через запятую) |
| `ADMIN_IDS` | Telegram ID обычных админов через запятую (`/season_manage`, Quick-Kick, админ-панель) |
| `ADMIN_USERNAMES` | Юзерки с правами бота (warn/ban/TOVA/админ-панель), без @ |
| `TOVA_ADMIN_ID` | ID модератора TOVA (карточки на проверку) |
| `ADMINS_CN` | Юзерки основателей Cream Nemesis (в меню выводятся как **«Основатели Cream Nemesis»**) |
| `ADMINS_LPL` / `ADMINS_RI` / `ADMINS_VSA` / `ADMINS_TOVA` | Юзерки админов соответствующих лиг для кнопки «Админы» в меню |
| `MAIN_CHAT_ID` | ID чата лиги: mute/ban, выходы, ссылки ЛПЛ / тренер / зал CN, авто-теги ЛПЛ. Формат `-100...` |
| `RI_CHAT_ID` | ID чата турниров РИ. Если пусто — берётся `MAIN_CHAT_ID` |
| `VSA_CHAT_ID` | ID чата VSA (зал славы). Если пусто — берётся `MAIN_CHAT_ID` |
| `TOPIC_*` | ID тем форума. Пусто = кнопка не ведёт на битую ссылку. Снять: `/topicid` в теме |
| `CURRENT_SEASON` | стартовый номер сезона TOVA (при первом запуске); далее сезон ведётся в БД |
| `DATABASE_URL` | опционально, по умолчанию `data/bot.db` |

Узнать свой ID: напишите [@userinfobot](https://t.me/userinfobot).

## Иерархия администраторов

Система реализует **5 уровней доступа** (таблица `admin_roles` в БД):

| Уровень | Название | Кто |
|---------|----------|-----|
| 5 | Владелец | `@Fara1807` |
| 4 | Главный администратор | `@nTarasov00` |
| 3 | Старший администратор | — |
| 2 | Администратор | — |
| 1 | Модератор | — |
| 0 | Обычный пользователь | все остальные |

### Правила применения санкций

- Администратор уровня **X** может применить санкцию к пользователю уровня **Y** только если **X > Y**.
- Если X <= Y — бот отвечает: `«Недостаточно прав»`.
- Уровни 4 и 5 имеют **абсолютный иммунитет** — бот отвечает: `«Владельцу нельзя применять ограничения»`.

### Мут младших администраторов

При муте пользователя с активными правами администратора Telegram бот:

1. Сохраняет текущие права в `AdminRole.saved_permissions` (JSON).
2. Снимает права через Telegram Bot API.
3. Выдаёт ограничение (`restrict`) на указанный срок.
4. По истечении мута **автоматически восстанавливает** права (через APScheduler).

### Добавление администраторов через бота

Команда `/addadmin @username [уровень]` (только супер-админ):

- Создаёт/обновляет запись в `admin_roles`.
- Синхронизирует права через Telegram Bot API.

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
| `/start` | главное меню (для админов включает кнопку «Админ-панель») |
| `/help` | справка и связь с администрацией |
| `/cancel` | отмена FSM (ник / результат / загрузка ростера ЛПЛ), только ЛС |
| `/go_tova` | поиск соперника |
| `/cancel_tova` | выход из очереди |
| `/result_tova nick1 8:2 nick2` | сдача результата (**только ЛС**) |
| `/admin` | инлайн админ-панель (управление сезонами, список варнов, ростер ЛПЛ) |
| `/warn @user - Nick [причина]` | выдать варн с привязкой ника лиги (срок 30 дней; 3 варна = автобан) |
| `/unwarn @user` | снять последнее активное предупреждение |
| `/warns` | список активных варнов и дней до сгорания |
| `/mute [@user] [время]` | ограничение пользователя (с учётом иерархии) |
| `/unmute [@user]` | снятие ограничения (с восстановлением прав для админов) |
| `/ban` `/unban` | бан / разбан пользователя (при бане деактивируется в сезоне TOVA) |
| `/addadmin @user [lvl]` | добавить/обновить администратора с уровнем 1-3 (только супер-админ) |
| `/season_manage` | управление сезонами TOVA (**только** `ADMIN_IDS`) |
| `/pending_tova` | повторная рассылка матчей на проверке (админы TOVA) |
| `/topicid` | ID текущей темы форума (только цифра, без лишних уведомлений) |
| `/chatid` | ID текущего чата |

## TOVA: сезоны, архив, выходы

- Участники сезона хранятся в БД (`season_participants.is_active`).
- Таблица и бомбардиры **текущего** сезона — только активные игроки.
- **Архив сезонов** — TOVA → меню прошлых сезонов (статистика / таблица / бомбардиры).
- Выход или кик из `MAIN_CHAT_ID` → алерт админам в ЛС + кнопка **«Снять с турнира»**.
- `/season_manage` — завершить сезон или начать новый.
- Матчи `pending_admin` пересылаются при рестарте бота; вручную — `/pending_tova`.
- Навигация по inline-кнопкам в ЛС **редактирует** сообщение, а не плодит новые.

## Админ-панель V2 и планировщик

- Кнопка **Админ-панель** в `/start` и команда `/admin` доступны только `ADMIN_IDS` / `ADMIN_USERNAMES`.
- Все админ-хэндлеры защищены через единый фильтр `AdminFilter` (`filters/admin.py`).
- **Варны:** `/warn @user - NickName [причина]` — сохраняет ник лиги; варны сгорают автоматически через **30 дней** (ежедневный cron в 03:00 Asia/Almaty). При 3 активных варнах — автоматический бан в чате лиги.
- **Состав ЛПЛ и авто-тег:** загрузка состава текстом в админ-панели → отправка скрытых HTML-тегов (`#lpl`) в `MAIN_CHAT_ID` по расписанию в 12:00, 16:00, 20:00 (Asia/Almaty) или по кнопке «Тегнуть сейчас».
- Планировщик: `APScheduler` (`services/scheduler.py`).
- **Раздел «Админы»:** для лиги Cream Nemesis контакты выводятся под заголовком **«Основатели Cream Nemesis»**.

## Техтребования

1. **SQLite WAL** — включается в `db/base.py` при старте (лог `journal_mode=wal`).
2. **FSM только в ЛС** — никнейм, бомбардиры, скриншоты; из группы — редирект.
3. **Безопасная модерация** — API ban/mute в `try/except`.
4. **Иерархия прав** — все санкции проверяются через `services/moderation.py` по уровням из `admin_roles`.
5. **Уведомления** — без лишних эмодзи и технических формулировок в текстах для пользователей.

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

## Импорт участников — `sync_chat_members.py`

Добавлен одноразовый скрипт `sync_chat_members.py` для импорта всех участников Telegram-чата в локальную БД `users`.

- Требования: `pyrogram`, `tgcrypto` (рекомендуется), рабочий пользователь Telegram с доступом к чату.
- Скрипт использует ваш `API_ID`, `API_HASH` и `CHAT_ID`:

```bash
export API_ID=123456
export API_HASH=yourhash
export CHAT_ID="-1001234567890"
python sync_chat_members.py
```

Скрипт перебирает участников через Pyrogram, пропускает ботов и вызывает `services.users.get_or_create_user(...)` для каждого участника.

## Как запушить обновления в GitHub

> `.env` и `data/bot.db` в `.gitignore` — они **никогда** не попадают в коммит.

1. Посмотреть статус и создать ветку:

```bash
git status
git checkout -b feature/my-changes
```

2. Добавить файлы и закоммитить:

```bash
git add README.md handlers/ services/
git commit -m "feat: описание изменений"
```

3. Отправить ветку на GitHub:

```bash
git push -u origin feature/my-changes
```

4. Открыть Pull Request на GitHub из вашей ветки → `main`.

5. Прямой пуш в `main` (если нет PR):

```bash
git checkout main
git pull origin main
git merge --no-ff feature/my-changes
git push origin main
```

**Полезные советы:**

- `git stash` — временно сохранить локальные правки перед `git pull`.
- `git reset --hard origin/main` — откат к состоянию удалённого репо.
