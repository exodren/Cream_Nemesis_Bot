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
from keyboards.admin_panel import admin_lpl_roster_kb, admin_panel_kb, admin_seasons_kb
from keyboards.main import back_only_kb
from services import lpl_roster as lpl_service
from services import moderation as mod
from handlers.season_manage import season_manage_text
from services.scheduler import job_lpl_auto_tag

router = Router(name="admin_panel")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())
logger = logging.getLogger(__name__)

ADMIN_HELP = (
    "<b>Справка модерации</b>\n\n"
    "<b>/warn</b> @user [- Nick] [причина]\n"
    "<b>/unwarn</b> @user\n"
    "<b>/warns</b> — список активных варнов\n"
    "<b>/mute</b> @user 60 · <b>/unmute</b>\n"
    "<b>/ban</b> · <b>/unban</b>\n"
    "<b>/pending_tova</b> — карточки на проверке\n\n"
    "Варн автоматически сгорает через 30 дней.\n"
    "Теги ЛПЛ уходят в чат лиги в 12:00, 16:00 и 20:00 (Asia/Almaty)."
)


class LplRosterFSM(StatesGroup):
    waiting_roster = State()


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
            f"Тег ЛПЛ отправлен в чат лиги ({len(members)} участников).",
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
