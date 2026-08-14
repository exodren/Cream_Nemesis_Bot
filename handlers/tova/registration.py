from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from handlers.tova.private import bot_deep_link, private_redirect_kb
from handlers.tova.states import NicknameFSM
from keyboards.main import back_only_kb
from keyboards.tova import tova_reg_kb
from services import users as users_service
from texts import TOVA_REG_MENU

router = Router(name="tova_registration")


@router.callback_query(F.data == "menu:tova:reg:set")
async def cb_set_nickname(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    if not callback.message:
        return

    if callback.message.chat.type != ChatType.PRIVATE:
        url = await bot_deep_link(callback.bot, "tova_nick")
        await callback.message.answer(
            "Смену никнейма можно выполнить только в личке с ботом.",
            reply_markup=private_redirect_kb(url),
        )
        return

    user = await users_service.get_or_create_user(
        session,
        tg_id=callback.from_user.id,
        username=callback.from_user.username,
    )
    current = f"\nТекущий никнейм: <b>{user.nickname}</b>" if user.nickname else ""
    await state.set_state(NicknameFSM.waiting_nickname)
    await callback.message.answer(
        "Введите свой игровой никнейм в FC Mobile.\n"
        "Без пробелов, до 64 символов."
        f"{current}\n\n"
        "Отмена: /cancel"
    )


@router.callback_query(F.data == "menu:tova:reg:del")
async def cb_del_nickname(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    if not callback.message:
        return

    await state.clear()
    user = await users_service.get_or_create_user(
        session,
        tg_id=callback.from_user.id,
        username=callback.from_user.username,
    )
    text = await users_service.clear_nickname(session, user)
    await callback.message.answer(text, reply_markup=tova_reg_kb())


@router.message(Command("cancel"), StateFilter(NicknameFSM.waiting_nickname))
async def cancel_nickname(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Ввод никнейма отменён.", reply_markup=tova_reg_kb())


@router.message(NicknameFSM.waiting_nickname, F.chat.type == ChatType.PRIVATE, F.text)
async def save_nickname(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.text or message.text.startswith("/"):
        await message.answer("Отправьте никнейм текстом или /cancel для отмены.")
        return

    user = await users_service.get_or_create_user(
        session,
        tg_id=message.from_user.id,
        username=message.from_user.username,
    )
    ok, text = await users_service.set_nickname(session, user, message.text)
    if not ok:
        await session.refresh(user, attribute_names=["nickname"])
        kept = (
            f"\nТекущий никнейм не изменён: <b>{user.nickname}</b>"
            if user.nickname
            else "\nСтарый никнейм не задан — записывать нечего."
        )
        await message.answer(text + kept + "\nПопробуйте ещё раз или /cancel.")
        return

    await state.clear()
    await message.answer(text, reply_markup=back_only_kb("menu:tova:reg"))


@router.message(NicknameFSM.waiting_nickname, F.chat.type != ChatType.PRIVATE)
async def nickname_not_private(message: Message) -> None:
    url = await bot_deep_link(message.bot, "tova_nick")
    await message.reply(
        "Ввод никнейма принимается только в личке с ботом.",
        reply_markup=private_redirect_kb(url),
    )


async def show_reg_menu(message: Message, session: AsyncSession) -> None:
    user = await users_service.get_or_create_user(
        session,
        tg_id=message.from_user.id,
        username=message.from_user.username,
    )
    nick_line = (
        f"\n\nВаш никнейм: <b>{user.nickname}</b>"
        if user.nickname
        else "\n\nНикнейм ещё не задан."
    )
    await message.answer(TOVA_REG_MENU + nick_line, reply_markup=tova_reg_kb())
