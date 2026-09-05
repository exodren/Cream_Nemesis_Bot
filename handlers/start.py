from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from handlers.tova.states import NicknameFSM
from keyboards.main import main_menu_kb
from keyboards.tova import tova_reg_kb
from config import get_settings
from services import users as users_service
from texts import START

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = message.from_user
    mention = f"@{user.username}" if user and user.username else (user.full_name if user else "игрок")
    payload = ""
    if message.text and " " in message.text:
        payload = message.text.split(maxsplit=1)[1].strip().lower()

    await users_service.get_or_create_user(
        session,
        tg_id=user.id,
        username=user.username if user else None,
    )

    if payload in {"tova", "tova_nick"}:
        db_user = await users_service.get_or_create_user(
            session,
            tg_id=user.id,
            username=user.username if user else None,
        )
        nick_line = (
            f"\nТекущий никнейм: <b>{db_user.nickname}</b>"
            if db_user.nickname
            else ""
        )
        if payload == "tova_nick":
            await state.set_state(NicknameFSM.waiting_nickname)
            await message.answer(
                "Введите свой игровой никнейм в FC Mobile.\n"
                "Без пробелов, до 64 символов."
                f"{nick_line}\n\nОтмена: /cancel"
            )
            return
        await message.answer(
            "Раздел TOVA. Выберите действие:" + nick_line,
            reply_markup=tova_reg_kb(),
        )
        return

    await message.answer(
        START.format(mention=mention),
        reply_markup=main_menu_kb(
            is_admin=get_settings().is_admin(
                user.id if user else 0,
                user.username if user else None,
            )
        ),
    )
