from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from handlers.callback_ui import edit_screen
from keyboards.admins import (
    admins_league_kb,
    admins_league_text,
    admins_menu_kb,
    admins_overview_text,
    staff_kb,
    staff_text,
)
from services import admin_roles as roles_service
from keyboards.coach import coach_kb
from keyboards.hall import hall_menu_kb
from keyboards.lpl import lpl_menu_kb, lpl_rules_kb
from keyboards.main import main_menu_kb
from keyboards.ri import ri_menu_kb, ri_tables_kb
from keyboards.tova import tova_menu_kb, tova_reg_kb
from texts import (
    HALL_MENU,
    LPL_MENU,
    LPL_RULES,
    REGULATION,
    RI_INTRO,
    RI_TABLES_MENU,
    RULES_CN,
    TOVA_HOW_TO,
    TOVA_MENU,
    TOVA_REG_MENU,
    TOVA_RULES,
    VSA_INTRO,
)

router = Router(name="menu")


@router.callback_query(F.data == "menu:topic_missing")
async def menu_topic_missing(callback: CallbackQuery) -> None:
    await callback.answer(
        "Тема не настроена. Зайди в нужную тему чата, напиши /topicid и пропиши ID в .env",
        show_alert=True,
    )


@router.callback_query(F.data == "menu:main")
async def menu_main(callback: CallbackQuery) -> None:
    user = callback.from_user
    mention = f"@{user.username}" if user.username else user.full_name
    from config import get_settings
    from texts import START

    await edit_screen(
        callback,
        START.format(mention=mention),
        main_menu_kb(is_admin=get_settings().is_admin(user.id, user.username)),
    )


@router.callback_query(F.data == "menu:regulation")
async def menu_regulation(callback: CallbackQuery) -> None:
    from keyboards.main import back_only_kb

    await edit_screen(callback, REGULATION, back_only_kb("menu:main"))


@router.callback_query(F.data == "menu:rules")
async def menu_rules(callback: CallbackQuery) -> None:
    from keyboards.main import back_only_kb

    await edit_screen(callback, RULES_CN, back_only_kb("menu:main"))


@router.callback_query(F.data == "menu:lpl")
async def menu_lpl(callback: CallbackQuery) -> None:
    await edit_screen(callback, LPL_MENU, lpl_menu_kb())


@router.callback_query(F.data == "menu:lpl:rules")
async def menu_lpl_rules(callback: CallbackQuery) -> None:
    await edit_screen(callback, LPL_RULES, lpl_rules_kb())


@router.callback_query(F.data == "menu:coach")
async def menu_coach(callback: CallbackQuery) -> None:
    await edit_screen(
        callback,
        "Режим Тренера — переход в тему чата.\n"
        "<i>Ссылка работает только для участников закрытого чата.</i>",
        coach_kb(),
    )


@router.callback_query(F.data == "menu:ri")
async def menu_ri(callback: CallbackQuery) -> None:
    await edit_screen(callback, RI_INTRO, ri_menu_kb())


@router.callback_query(F.data == "menu:ri:tables")
async def menu_ri_tables(callback: CallbackQuery) -> None:
    await edit_screen(callback, RI_TABLES_MENU, ri_tables_kb())


@router.callback_query(F.data == "menu:vsa")
async def menu_vsa(callback: CallbackQuery) -> None:
    from keyboards.main import back_only_kb

    await edit_screen(callback, VSA_INTRO, back_only_kb("menu:main"))


@router.callback_query(F.data == "menu:hall")
async def menu_hall(callback: CallbackQuery) -> None:
    await edit_screen(callback, HALL_MENU, hall_menu_kb())


@router.callback_query(F.data == "menu:admins")
async def menu_admins(callback: CallbackQuery, session: AsyncSession) -> None:
    staff = await roles_service.list_admins(session)
    await edit_screen(callback, admins_overview_text(staff), admins_menu_kb())


@router.callback_query(F.data.startswith("menu:admins:"))
async def menu_admins_league(callback: CallbackQuery, session: AsyncSession) -> None:
    league = (callback.data or "").rsplit(":", 1)[-1]
    if league == "staff":
        staff = await roles_service.list_admins(session)
        await edit_screen(callback, f"<b>Модерация чата</b>\n\n{staff_text(staff)}", staff_kb(staff))
        return
    await edit_screen(callback, admins_league_text(league), admins_league_kb(league))


@router.callback_query(F.data == "menu:tova")
async def menu_tova(callback: CallbackQuery) -> None:
    await edit_screen(callback, TOVA_MENU, tova_menu_kb())


@router.callback_query(F.data == "menu:tova:reg")
async def menu_tova_reg(callback: CallbackQuery, session: AsyncSession) -> None:
    from services import users as users_service

    user = await users_service.get_or_create_user(
        session,
        tg_id=callback.from_user.id,
        username=callback.from_user.username,
    )
    nick_line = (
        f"\n\nВаш никнейм: <b>{user.nickname}</b>"
        if user.nickname
        else "\n\nНикнейм ещё не задан."
    )
    await edit_screen(callback, TOVA_REG_MENU + nick_line, tova_reg_kb())


@router.callback_query(F.data == "menu:tova:rules")
async def menu_tova_rules(callback: CallbackQuery) -> None:
    from keyboards.main import back_only_kb

    await edit_screen(callback, TOVA_RULES, back_only_kb("menu:tova"))


@router.callback_query(F.data == "menu:tova:howto")
async def menu_tova_howto(callback: CallbackQuery) -> None:
    from keyboards.main import back_only_kb

    await edit_screen(callback, TOVA_HOW_TO, back_only_kb("menu:tova"))
