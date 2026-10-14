from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.tova import challenge_kb
from services import challenges as challenges_service
from services import queue as queue_service
from services import rate_limit
from services import users as users_service

logger = logging.getLogger(__name__)

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
        await message.answer("Вы заблокированы и не можете играть в TOVA.")
        return

    # Direct challenge when replying to another user's message
    if message.reply_to_message and message.reply_to_message.from_user:
        target_tg_user = message.reply_to_message.from_user

        if target_tg_user.id == message.from_user.id:
            await message.answer("Нельзя бросить вызов самому себе.")
            return

        if target_tg_user.is_bot:
            await message.answer("Нельзя бросить вызов боту.")
            return

        if not user.nickname:
            await message.answer(
                "Сначала зарегистрируйте никнейм:\n"
                "TOVA → Регистрация → Изменить никнейм\n"
                "(только в личке с ботом)."
            )
            return

        target_user = await users_service.get_or_create_user(
            session,
            tg_id=target_tg_user.id,
            username=target_tg_user.username,
        )

        if target_user.is_banned:
            await message.answer("Этот игрок заблокирован и не может принять вызов.")
            return

        if not target_user.nickname:
            target_name = (
                f"@{target_tg_user.username}"
                if target_tg_user.username
                else target_tg_user.full_name
            )
            await message.answer(
                f"Игрок {target_name} еще не зарегистрировал никнейм в TOVA и не может принять вызов."
            )
            return

        # Check caller's active challenges
        outgoing = await challenges_service.get_outgoing_challenge(session, user.id)
        if outgoing:
            target_nick = outgoing.target.nickname if outgoing.target else "сопернику"
            await message.answer(
                f"У вас уже есть активный вызов игроку <b>{target_nick}</b>.\n"
                "Сначала отмените его (/cancel_tova или кнопкой в сообщении), чтобы бросить новый вызов."
            )
            return

        incoming = await challenges_service.get_incoming_challenge(session, user.id)
        if incoming:
            challenger_nick = (
                incoming.challenger.nickname if incoming.challenger else "соперника"
            )
            await message.answer(
                f"Вам уже бросил вызов игрок <b>{challenger_nick}</b>.\n"
                "Примите его или отклоните перед отправкой нового вызова."
            )
            return

        # Check target's active challenges
        target_active = await challenges_service.get_active_challenge_for_user(
            session, target_user.id
        )
        if target_active:
            await message.answer(
                f"Игрок <b>{target_user.nickname}</b> сейчас уже участвует в дуэли "
                "или ожидает ответа на вызов. Попробуйте позже."
            )
            return

        # Remove both from random matchmaking queue if queued
        await queue_service.leave_queue(session, user)
        await queue_service.leave_queue(session, target_user)

        challenge = await challenges_service.create_challenge(
            session,
            challenger_id=user.id,
            target_id=target_user.id,
            chat_id=message.chat.id,
        )

        sent = await message.answer(
            f"⚔️ <b>{user.nickname}</b> бросил вызов игроку <b>{target_user.nickname}</b>!\n\n"
            "Матч состоится, если соперник примет вызов.",
            reply_markup=challenge_kb(challenge.id),
        )
        challenge.message_id = sent.message_id
        await session.commit()
        return

    # Random matchmaking (no reply to message)
    # Check if user is in an active duel
    active_challenge = await challenges_service.get_active_challenge_for_user(
        session, user.id
    )
    if active_challenge:
        if active_challenge.challenger_id == user.id:
            opp_nick = (
                active_challenge.target.nickname
                if active_challenge.target
                else "сопернику"
            )
            await message.answer(
                f"У вас есть активный вызов игроку <b>{opp_nick}</b>.\n"
                "Сначала отмените его (/cancel_tova), чтобы искать случайного соперника."
            )
        else:
            opp_nick = (
                active_challenge.challenger.nickname
                if active_challenge.challenger
                else "соперника"
            )
            await message.answer(
                f"Вам брошен вызов от игрока <b>{opp_nick}</b>.\n"
                "Примите его или отклоните перед поиском случайного соперника."
            )
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
    if not message.from_user:
        return

    user = await users_service.get_or_create_user(
        session,
        tg_id=message.from_user.id,
        username=message.from_user.username,
    )

    # 1. Check if user sent an outgoing challenge
    outgoing = await challenges_service.get_outgoing_challenge(session, user.id)
    if outgoing:
        target_nick = outgoing.target.nickname if outgoing.target else "сопернику"
        await challenges_service.cancel_challenge(session, outgoing)
        if outgoing.chat_id and outgoing.message_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=outgoing.chat_id,
                    message_id=outgoing.message_id,
                    text=f"🚫 <b>{user.nickname}</b> отменил вызов игроку <b>{target_nick}</b>.",
                    reply_markup=None,
                )
            except Exception:
                pass
        await queue_service.leave_queue(session, user)
        await session.commit()
        await message.answer(f"Вы отменили вызов игроку <b>{target_nick}</b>.")
        return

    # 2. Check if user has an incoming challenge
    incoming = await challenges_service.get_incoming_challenge(session, user.id)
    if incoming:
        challenger_nick = (
            incoming.challenger.nickname if incoming.challenger else "соперника"
        )
        await challenges_service.decline_challenge(session, incoming)
        if incoming.chat_id and incoming.message_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=incoming.chat_id,
                    message_id=incoming.message_id,
                    text=f"❌ <b>{user.nickname}</b> отклонил вызов от <b>{challenger_nick}</b>.",
                    reply_markup=None,
                )
            except Exception:
                pass
        await queue_service.leave_queue(session, user)
        await session.commit()
        await message.answer(f"Вы отклонили вызов от игрока <b>{challenger_nick}</b>.")
        return

    # 3. Check queue
    left = await queue_service.leave_queue(session, user)
    await session.commit()
    if left:
        await message.answer("Вы вышли из очереди TOVA.")
    else:
        await message.answer("У вас нет активной очереди или вызовов TOVA.")


@router.callback_query(F.data.startswith("challenge:accept:"))
async def cb_challenge_accept(callback: CallbackQuery, session: AsyncSession) -> None:
    challenge_id = int(callback.data.split(":")[2])
    challenge = await challenges_service.get_challenge_by_id(session, challenge_id)
    if not challenge or challenge.status != "pending":
        await callback.answer("Этот вызов уже неактивен.", show_alert=True)
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        return

    target = challenge.target
    challenger = challenge.challenger
    if callback.from_user.id != target.tg_id:
        await callback.answer(
            f"Принять вызов может только {target.nickname}!", show_alert=True
        )
        return

    await challenges_service.accept_challenge(session, challenge)
    await queue_service.leave_queue(session, challenger)
    await queue_service.leave_queue(session, target)
    await session.commit()

    match_chat_text = (
        f"⚔️ <b>{target.nickname}</b> принял вызов от <b>{challenger.nickname}</b>!\n\n"
        "Матч начался! Сыграйте матч по правилам TOVA.\n"
        "Результат отправляйте боту в личке:\n"
        f"<code>/result_tova {challenger.nickname} 0:0 {target.nickname}</code>"
    )
    if callback.message:
        try:
            await callback.message.edit_text(match_chat_text, reply_markup=None)
        except Exception:
            pass

    text_challenger = (
        "Вызов принят! Матч начался.\n\n"
        f"Вы: <b>{challenger.nickname}</b>\n"
        f"Соперник: <b>{target.nickname}</b>\n\n"
        "Сыграйте матч по правилам TOVA.\n"
        "Результат отправляйте боту в личке:\n"
        f"<code>/result_tova {challenger.nickname} 0:0 {target.nickname}</code>"
    )
    text_target = (
        "Вызов принят! Матч начался.\n\n"
        f"Вы: <b>{target.nickname}</b>\n"
        f"Соперник: <b>{challenger.nickname}</b>\n\n"
        "Сыграйте матч по правилам TOVA.\n"
        "Результат отправляйте боту в личке:\n"
        f"<code>/result_tova {target.nickname} 0:0 {challenger.nickname}</code>"
    )
    try:
        await callback.bot.send_message(challenger.tg_id, text_challenger)
    except Exception:
        pass
    try:
        await callback.bot.send_message(target.tg_id, text_target)
    except Exception:
        pass

    await callback.answer("Вы приняли вызов!")


@router.callback_query(F.data.startswith("challenge:decline:"))
async def cb_challenge_decline(callback: CallbackQuery, session: AsyncSession) -> None:
    challenge_id = int(callback.data.split(":")[2])
    challenge = await challenges_service.get_challenge_by_id(session, challenge_id)
    if not challenge or challenge.status != "pending":
        await callback.answer("Этот вызов уже неактивен.", show_alert=True)
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        return

    target = challenge.target
    challenger = challenge.challenger
    if callback.from_user.id != target.tg_id:
        await callback.answer(
            f"Отклонить вызов может только {target.nickname}!", show_alert=True
        )
        return

    await challenges_service.decline_challenge(session, challenge)
    await session.commit()

    decline_text = (
        f"❌ <b>{target.nickname}</b> отклонил вызов от <b>{challenger.nickname}</b>."
    )
    if callback.message:
        try:
            await callback.message.edit_text(decline_text, reply_markup=None)
        except Exception:
            pass

    try:
        await callback.bot.send_message(
            challenger.tg_id,
            f"Игрок <b>{target.nickname}</b> отклонил ваш вызов.",
        )
    except Exception:
        pass

    await callback.answer("Вы отклонили вызов.")


@router.callback_query(F.data.startswith("challenge:cancel:"))
async def cb_challenge_cancel(callback: CallbackQuery, session: AsyncSession) -> None:
    challenge_id = int(callback.data.split(":")[2])
    challenge = await challenges_service.get_challenge_by_id(session, challenge_id)
    if not challenge or challenge.status != "pending":
        await callback.answer("Этот вызов уже неактивен.", show_alert=True)
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        return

    challenger = challenge.challenger
    target = challenge.target
    if callback.from_user.id != challenger.tg_id:
        await callback.answer(
            f"Отменить вызов может только {challenger.nickname}!", show_alert=True
        )
        return

    await challenges_service.cancel_challenge(session, challenge)
    await session.commit()

    cancel_text = (
        f"🚫 <b>{challenger.nickname}</b> отменил вызов игроку <b>{target.nickname}</b>."
    )
    if callback.message:
        try:
            await callback.message.edit_text(cancel_text, reply_markup=None)
        except Exception:
            pass

    await callback.answer("Вызов отменен.")

