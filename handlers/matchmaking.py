from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from services import queue as queue_service
from services import rate_limit
from services import users as users_service

router = Router(name="matchmaking")

GO_TOVA_COOLDOWN = 8.0


@router.message(Command("go_tova"))
async def cmd_go_tova(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not message.from_user:
        return

    key = f"go_tova:{message.from_user.id}"
    if not rate_limit.allow(key, GO_TOVA_COOLDOWN):
        left = rate_limit.seconds_left(key, GO_TOVA_COOLDOWN)
        await message.answer(f"Подождите {left} сек. перед повторным /go_tova.")
        return

    current = await state.get_state()
    if current is not None and str(current).startswith("ResultFSM"):
        await message.answer(
            "Сначала завершите или отмените сдачу результата (/cancel)."
        )
        return

    user = await users_service.get_or_create_user(
        session,
        tg_id=message.from_user.id,
        username=message.from_user.username,
    )
    if user.is_banned:
        await message.answer("Вы заблокированы и не можете искать матч TOVA.")
        return

    status, opponent = await queue_service.enqueue_or_match(session, user)

    if status == "need_nickname":
        await message.answer(
            "Сначала зарегистрируйте никнейм:\n"
            "TOVA → Регистрация → Изменить никнейм\n"
            "(только в личке с ботом)."
        )
        return

    if status == "already_queued":
        await message.answer(
            "Вы уже в очереди поиска TOVA.\n"
            "Ожидайте соперника или выйдите: /cancel_tova"
        )
        return

    if status == "waiting":
        await message.answer(
            "Ищем соперника TOVA…\n"
            "Вы в очереди. Отмена: /cancel_tova"
        )
        return

    # matched
    assert opponent is not None
    text_self = (
        "Соперник найден!\n\n"
        f"Вы: <b>{user.nickname}</b>\n"
        f"Соперник: <b>{opponent.nickname}</b>\n\n"
        "Сыграйте матч по правилам TOVA.\n"
        "Результат отправляйте боту в личке:\n"
        f"<code>/result_tova {user.nickname} 0:0 {opponent.nickname}</code>"
    )
    text_opp = (
        "Соперник найден!\n\n"
        f"Вы: <b>{opponent.nickname}</b>\n"
        f"Соперник: <b>{user.nickname}</b>\n\n"
        "Сыграйте матч по правилам TOVA.\n"
        "Результат отправляйте боту в личке:\n"
        f"<code>/result_tova {opponent.nickname} 0:0 {user.nickname}</code>"
    )
    await message.answer(text_self)
    try:
        await message.bot.send_message(opponent.tg_id, text_opp)
    except Exception:
        await message.answer(
            "Соперник найден, но не удалось написать ему в ЛС "
            "(возможно, он не запускал бота). Попросите его открыть бота."
        )


@router.message(Command("cancel_tova"))
async def cmd_cancel_tova(message: Message, session: AsyncSession) -> None:
    user = await users_service.get_or_create_user(
        session,
        tg_id=message.from_user.id,
        username=message.from_user.username,
    )
    left = await queue_service.leave_queue(session, user)
    if left:
        await message.answer("Вы вышли из очереди TOVA.")
    else:
        await message.answer("Вы не были в очереди TOVA.")
