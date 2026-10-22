from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from filters import AdminFilter
from handlers.callback_ui import edit_screen
from keyboards.admin_panel import (
    admin_level_kb,
    admin_lpl_roster_kb,
    admin_panel_kb,
    admin_roles_kb,
    admin_seasons_kb,
)
from keyboards.main import back_only_kb
from services import admin_roles as roles_service
from services import lpl_roster as lpl_service
from services import moderation as mod
from services import users as users_service
from handlers.season_manage import season_manage_text
from services.scheduler import job_lpl_auto_tag

router = Router(name="admin_panel")
router.message.filter(AdminFilter(min_level=4))
router.callback_query.filter(AdminFilter(min_level=4))
logger = logging.getLogger(__name__)

ADMIN_HELP = (
    "<b>Справка модерации</b>\n\n"
    "<b>/warn</b> @user [- Nick] [причина]\n"
    "<b>/unwarn</b> @user\n"
    "<b>/warns</b> — список активных варнов\n"
    "<b>/mute</b> @user 60 · <b>/unmute</b>\n"
    "<b>/ban</b> · <b>/unban</b>\n"
    "<b>/pending_tova</b> — карточки на проверке\n\n"
    "<b>Уровни:</b> 1–2 — мут · 3 — мут, варны · 4–5 — всё + админ-панель.\n"
    "Санкции только к тем, у кого уровень ниже; 4–5 неприкосновенны.\n\n"
    "Варн автоматически сгорает через 30 дней.\n"
    "Теги ЛПЛ уходят в чат лиги в 12:00, 16:00 и 20:00 (Asia/Almaty)."
)


class LplRosterFSM(StatesGroup):
    waiting_roster = State()


class AdminRolesFSM(StatesGroup):
    waiting_target = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    await message.answer(
        "<b>Админ-панель</b>\nВыберите раздел:",
        reply_markup=admin_panel_kb(),
    )


@router.callback_query(F.data == "admin:panel")
async def cb_admin_panel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await edit_screen(
        callback,
        "<b>Админ-панель</b>\nВыберите раздел:",
        admin_panel_kb(),
    )


@router.callback_query(F.data == "admin:help")
async def cb_admin_help(callback: CallbackQuery) -> None:
    await edit_screen(callback, ADMIN_HELP, back_only_kb("admin:panel"))


@router.callback_query(F.data == "admin:warns")
async def cb_admin_warns(callback: CallbackQuery, session: AsyncSession) -> None:
    rows = await mod.list_active_warn_summary(session)
    await edit_screen(
        callback,
        mod.format_active_warns_text(rows),
        back_only_kb("admin:panel"),
    )


@router.callback_query(F.data == "admin:seasons")
async def cb_admin_seasons(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user or callback.from_user.id not in get_settings().admin_ids:
        await callback.answer("Только для ADMIN_IDS.", show_alert=True)
        return
    text = await season_manage_text(session)
    await edit_screen(callback, text, admin_seasons_kb())


@router.callback_query(F.data == "admin:lpl_roster")
async def cb_lpl_roster_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await edit_screen(
        callback,
        "<b>Управление составом ЛПЛ</b>\n"
        "Загрузите список с @username — бот сохранит состав "
        "и будет тегать его скрытыми ссылками 3 раза в день.",
        admin_lpl_roster_kb(),
    )


@router.callback_query(F.data == "admin:lpl_roster:show")
async def cb_lpl_roster_show(callback: CallbackQuery, session: AsyncSession) -> None:
    members = await lpl_service.list_roster(session)
    if not members:
        await callback.answer("Состав ЛПЛ пуст.", show_alert=True)
    await edit_screen(
        callback,
        lpl_service.format_roster_text(members),
        admin_lpl_roster_kb(),
        answer=bool(members),
    )


@router.callback_query(F.data == "admin:lpl_roster:clear")
async def cb_lpl_roster_clear(callback: CallbackQuery, session: AsyncSession) -> None:
    removed = await lpl_service.clear_roster(session)
    await callback.answer(f"Удалено: {removed}", show_alert=True)
    await edit_screen(
        callback,
        lpl_service.format_roster_text([]),
        admin_lpl_roster_kb(),
        answer=False,
    )


@router.callback_query(F.data == "admin:lpl_roster:upload")
async def cb_lpl_roster_upload(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(LplRosterFSM.waiting_roster)
    await edit_screen(
        callback,
        "<b>Загрузка состава ЛПЛ</b>\n\n"
        "Пришлите одним сообщением список с @username "
        "(можно с любым текстом вокруг — парсер вытащит все упоминания).\n\n"
        "Отмена: /cancel",
        back_only_kb("admin:lpl_roster"),
    )


@router.message(Command("cancel"), StateFilter(LplRosterFSM.waiting_roster))
async def cancel_lpl_roster(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Загрузка состава отменена.", reply_markup=admin_panel_kb())


@router.message(LplRosterFSM.waiting_roster, F.chat.type == ChatType.PRIVATE, F.text)
async def save_lpl_roster(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.text or message.text.startswith("/"):
        await message.answer("Пришлите текст со списком @username или /cancel.")
        return

    usernames = lpl_service.parse_usernames(message.text)
    if not usernames:
        await message.answer(
            "Не найдено ни одного @username. Пример:\n"
            "@player1 @player2\n"
            "или многострочный список."
        )
        return

    count = await lpl_service.replace_roster(session, usernames)
    resolved = await lpl_service.resolve_missing_tg_ids(session, message.bot)
    await state.clear()
    members = await lpl_service.list_roster(session)
    await message.answer(
        f"Состав ЛПЛ обновлён: <b>{count}</b> игроков"
        + (f" (tg id найден для +{resolved})" if resolved else "")
        + ".\n\n"
        + lpl_service.format_roster_text(members),
        reply_markup=admin_lpl_roster_kb(),
    )
    logger.info("LPL roster updated by admin=%s count=%s", message.from_user.id if message.from_user else None, count)


@router.callback_query(F.data == "admin:lpl_tag_now")
async def cb_lpl_tag_now(callback: CallbackQuery, session: AsyncSession) -> None:
    settings = get_settings()
    if not settings.main_chat_id:
        await callback.answer("MAIN_CHAT_ID не задан.", show_alert=True)
        return

    members = await lpl_service.list_roster(session)
    if not members:
        await callback.answer("Состав ЛПЛ пуст.", show_alert=True)
        return

    await callback.answer("Отправляю…")
    try:
        await job_lpl_auto_tag(callback.bot)
        await edit_screen(
            callback,
            f"Тег ЛПЛ отправлен в топик состава ({len(members)} участников).",
            admin_panel_kb(),
            answer=False,
        )
    except Exception:
        logger.exception("Manual LPL tag failed")
        await edit_screen(
            callback,
            "Не удалось отправить тег. Смотрите логи.",
            admin_panel_kb(),
            answer=False,
        )


async def _roles_screen(session: AsyncSession) -> str:
    admins = await roles_service.list_admins(session)
    lines = [
        f"{a.admin_level} · {roles_service.ROLE_NAMES[a.admin_level]} — "
        + (f"@{a.username}" if a.username else f"<code>{a.user_id}</code>")
        for a in admins
    ]
    body = "\n".join(lines) or "Список пуст."
    return f"<b>Администраторы</b>\n\n{body}\n\nНажмите на админа, чтобы изменить уровень."


async def _max_level(callback_or_message, session: AsyncSession) -> int | None:
    u = callback_or_message.from_user
    return await roles_service.max_assignable_level(session, u.id, u.username)


@router.callback_query(F.data == "admin:roles")
async def cb_admin_roles(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    if await _max_level(callback, session) is None:
        await callback.answer("Только для уровней 4–5.", show_alert=True)
        return
    await edit_screen(callback, await _roles_screen(session), admin_roles_kb(await roles_service.list_admins(session)))


@router.callback_query(F.data == "admin:roles:add")
async def cb_admin_roles_add(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if await _max_level(callback, session) is None:
        await callback.answer("Только для уровней 4–5.", show_alert=True)
        return
    await state.set_state(AdminRolesFSM.waiting_target)
    await edit_screen(
        callback,
        "<b>Назначение администратора</b>\n\n"
        "Пришлите @username или Telegram ID, либо перешлите сообщение пользователя.\n\n"
        "Отмена: /cancel",
        back_only_kb("admin:roles"),
    )


@router.message(Command("cancel"), StateFilter(AdminRolesFSM.waiting_target))
async def cancel_admin_roles(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=admin_panel_kb())


@router.message(AdminRolesFSM.waiting_target, F.chat.type == ChatType.PRIVATE)
async def admin_roles_target(message: Message, state: FSMContext, session: AsyncSession) -> None:
    max_level = await _max_level(message, session)
    if max_level is None:
        await state.clear()
        return
    text = (message.text or "").strip()
    target = None
    fwd = getattr(message.forward_origin, "sender_user", None)
    if fwd:
        target = await users_service.get_or_create_user(session, tg_id=fwd.id, username=fwd.username)
    elif text.isdigit():
        target = await users_service.get_or_create_user(session, tg_id=int(text))
    elif text.startswith("@"):
        chat_id = get_settings().main_chat_id or message.chat.id
        target, _ = await mod.resolve_target_user(session, bot=message.bot, chat_id=chat_id, username=text)
    if target is None:
        await message.answer(
            "Пользователь не найден. Пришлите @username, Telegram ID или перешлите его сообщение "
            "(если пересылка скрыта — попросите его написать боту /start). Отмена: /cancel"
        )
        return
    await state.clear()
    mention = f"@{target.username}" if target.username else str(target.tg_id)
    await message.answer(f"Выберите уровень для {mention}:", reply_markup=admin_level_kb(target.tg_id, max_level))


@router.callback_query(F.data.startswith("admin:roles:pick:"))
async def cb_admin_roles_pick(callback: CallbackQuery, session: AsyncSession) -> None:
    max_level = await _max_level(callback, session)
    if max_level is None:
        await callback.answer("Только для уровней 4–5.", show_alert=True)
        return
    user_id = int(callback.data.rsplit(":", 1)[1])
    await edit_screen(callback, f"Выберите уровень для <code>{user_id}</code>:", admin_level_kb(user_id, max_level))


@router.callback_query(F.data.startswith("admin:roles:set:"))
async def cb_admin_roles_set(callback: CallbackQuery, session: AsyncSession) -> None:
    max_level = await _max_level(callback, session)
    if max_level is None:
        await callback.answer("Только для уровней 4–5.", show_alert=True)
        return
    _, _, _, user_id, level = callback.data.split(":")
    target = await users_service.get_or_create_user(session, tg_id=int(user_id))
    chat_id = get_settings().main_chat_id or callback.from_user.id
    report = await roles_service.assign_admin_level(
        session, callback.bot, chat_id, target, int(level), max_level
    )
    await edit_screen(
        callback,
        report + "\n\n" + await _roles_screen(session),
        admin_roles_kb(await roles_service.list_admins(session)),
    )
