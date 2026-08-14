from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from handlers.tova.private import bot_deep_link, ensure_private, private_redirect_kb
from handlers.tova.states import ResultFSM
from services import matches as matches_service
from services import rate_limit
from services import users as users_service
from services.matches import parse_result_command, parse_scorers_line

router = Router(name="results")


def _confirm_kb(match_id: int) -> object:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"tova:confirm:{match_id}:1"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"tova:confirm:{match_id}:0"),
    )
    return builder.as_markup()


def _admin_kb(match_id: int) -> object:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Засчитать", callback_data=f"tova:admin:{match_id}:1"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"tova:admin:{match_id}:0"),
    )
    return builder.as_markup()


@router.message(Command("cancel"), StateFilter(ResultFSM), F.chat.type == ChatType.PRIVATE)
async def cancel_result_fsm(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отправка результата TOVA отменена.")


@router.message(Command("cancel_match", "reject_tova"))
async def cmd_cancel_match(message: Message, session: AsyncSession) -> None:
    if not message.from_user:
        return
    user = await users_service.get_or_create_user(
        session,
        tg_id=message.from_user.id,
        username=message.from_user.username,
    )
    open_match = await matches_service.find_open_match_for_user(session, user)
    if open_match is None:
        await message.answer("У вас нет незакрытых матчей TOVA.")
        return
    if open_match.status == "pending_admin":
        await message.answer(
            f"Матч #{open_match.id} уже на проверке у админов. "
            "Игрок не может отменить его сам."
        )
        return

    status, match = await matches_service.confirm_match_by_user(
        session, open_match, user, accept=False
    )
    if status == "rejected":
        p1 = await matches_service.get_user(session, match.player1_id)
        p2 = await matches_service.get_user(session, match.player2_id)
        await message.answer(
            f"Матч #{match.id} отклонён. Можно снова сдавать результат через /result_tova."
        )
        if p1 and p2:
            for tg_id in {p1.tg_id, p2.tg_id} - {message.from_user.id}:
                try:
                    await message.bot.send_message(
                        tg_id,
                        f"Матч #{match.id} отклонён участником.",
                    )
                except Exception:
                    pass
        return
    await message.answer("Не удалось отклонить матч.")


@router.message(Command("result_tova"))
async def cmd_result_tova(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await ensure_private(
        message,
        hint="Результат матча TOVA принимается только в личке с ботом.",
    ):
        return

    if not message.from_user:
        return

    current = await state.get_state()
    if current and str(current).startswith("ResultFSM"):
        await message.answer(
            "Вы уже вводите результат. Завершите шаги или отмените: /cancel"
        )
        return

    key = f"result_tova:{message.from_user.id}"
    if not rate_limit.allow(key, 5.0):
        await message.answer("Слишком часто. Подождите пару секунд.")
        return

    parsed = parse_result_command(message.text or "")
    if parsed is None:
        await message.answer(
            "Формат:\n"
            "<code>/result_tova nickname1 8:2 nickname2</code>"
        )
        return

    nick1, score1, score2, nick2 = parsed
    user = await users_service.get_or_create_user(
        session,
        tg_id=message.from_user.id,
        username=message.from_user.username,
    )
    if not user.nickname:
        await message.answer("Сначала зарегистрируйте никнейм в разделе TOVA → Регистрация.")
        return

    open_match = await matches_service.find_open_match_for_user(session, user)
    if open_match is not None:
        p1 = await matches_service.get_user(session, open_match.player1_id)
        p2 = await matches_service.get_user(session, open_match.player2_id)
        card = ""
        if p1 and p2:
            card = matches_service.format_match_card(open_match, p1, p2) + "\n\n"
        if open_match.status == "pending_confirm":
            await message.answer(
                card
                + f"У вас уже есть незакрытый матч #{open_match.id}.\n"
                "Подтвердите / отклоните кнопками ниже "
                "или командой /cancel_match.",
                reply_markup=_confirm_kb(open_match.id),
            )
        else:
            await message.answer(
                card
                + f"У вас уже есть матч #{open_match.id} на проверке у админов. "
                "Дождитесь решения."
            )
        return

    await state.set_state(ResultFSM.waiting_scorers_p1)
    await state.update_data(
        nick1=nick1,
        score1=score1,
        score2=score2,
        nick2=nick2,
        submitter_tg_id=user.tg_id,
    )
    await message.answer(
        "Введите бомбардиров для <b>первого</b> игрока одной строкой:\n"
        f"<code>{nick1} — Player (3), Player2 (2)</code>\n\n"
        "Отмена: /cancel"
    )


@router.message(
    ResultFSM.waiting_scorers_p1,
    F.chat.type == ChatType.PRIVATE,
    F.text,
    ~F.text.startswith("/"),
)
async def result_scorers_p1(message: Message, state: FSMContext) -> None:
    parsed = parse_scorers_line(message.text or "")
    if parsed is None:
        await message.answer(
            "Не удалось разобрать строку. Пример:\n"
            "<code>Kawasaki2.0 — C. Ronaldo (5), Mbappé (3)</code>\n\n"
            "Отмена: /cancel"
        )
        return

    data = await state.get_data()
    nick, items = parsed
    if nick.lower() != str(data["nick1"]).lower():
        await message.answer(
            f"Ник в начале строки должен быть <b>{data['nick1']}</b>."
        )
        return

    await state.update_data(scorers_p1=items)
    await state.set_state(ResultFSM.waiting_scorers_p2)
    await message.answer(
        "Введите бомбардиров для <b>второго</b> игрока:\n"
        f"<code>{data['nick2']} — Messi, Neymar Jr.</code>\n\n"
        "Отмена: /cancel"
    )


@router.message(
    ResultFSM.waiting_scorers_p2,
    F.chat.type == ChatType.PRIVATE,
    F.text,
    ~F.text.startswith("/"),
)
async def result_scorers_p2(message: Message, state: FSMContext) -> None:
    parsed = parse_scorers_line(message.text or "")
    if parsed is None:
        await message.answer(
            "Не удалось разобрать строку. Пример:\n"
            "<code>Player2 — Messi, Neymar Jr.</code>\n\n"
            "Отмена: /cancel"
        )
        return

    data = await state.get_data()
    nick, items = parsed
    if nick.lower() != str(data["nick2"]).lower():
        await message.answer(
            f"Ник в начале строки должен быть <b>{data['nick2']}</b>."
        )
        return

    await state.update_data(scorers_p2=items)
    await state.set_state(ResultFSM.waiting_screenshot)
    await message.answer("Пришлите скриншот итоговой статистики матча (фото).\nОтмена: /cancel")


@router.message(ResultFSM.waiting_screenshot, F.chat.type == ChatType.PRIVATE, F.photo)
async def result_screenshot(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    file_id = message.photo[-1].file_id
    submitter = await users_service.get_or_create_user(
        session,
        tg_id=message.from_user.id,
        username=message.from_user.username,
    )

    match, err = await matches_service.create_pending_match(
        session,
        submitter=submitter,
        nick1=data["nick1"],
        score1=int(data["score1"]),
        score2=int(data["score2"]),
        nick2=data["nick2"],
        scorers_p1=[(n, int(c)) for n, c in data["scorers_p1"]],
        scorers_p2=[(n, int(c)) for n, c in data["scorers_p2"]],
        screenshot_file_id=file_id,
    )
    if match is None:
        await state.clear()
        open_match = await matches_service.find_open_match_for_user(session, submitter)
        if open_match is not None and open_match.status == "pending_confirm":
            await message.answer(
                err
                + "\n\nПодтвердите / отклоните незакрытый матч ниже "
                "или /cancel_match.",
                reply_markup=_confirm_kb(open_match.id),
            )
        else:
            await message.answer(err + "\nМожно начать заново: /result_tova ...")
        return

    await state.clear()
    p1 = await matches_service.get_user(session, match.player1_id)
    p2 = await matches_service.get_user(session, match.player2_id)
    goals = await matches_service.load_match_goals(session, match.id)
    assert p1 and p2
    card = matches_service.format_match_card(match, p1, p2, goals)

    await message.answer_photo(file_id, caption=card + "\n\nОжидаем подтверждение соперника.")

    opponent = p2 if submitter.id == p1.id else p1
    try:
        await message.bot.send_photo(
            opponent.tg_id,
            photo=file_id,
            caption=(
                card
                + "\n\nПодтвердите корректность результата."
            ),
            reply_markup=_confirm_kb(match.id),
        )
    except Exception:
        await message.answer(
            "Не удалось отправить запрос сопернику в ЛС. "
            "Попросите его открыть бота. Пока матч можно отклонить: /cancel_match"
        )


@router.message(ResultFSM.waiting_screenshot, F.chat.type == ChatType.PRIVATE, ~F.photo)
async def result_screenshot_need_photo(message: Message) -> None:
    if message.text and message.text.startswith("/"):
        return
    await message.answer("Нужно именно фото скриншота. Или /cancel для отмены.")


@router.message(StateFilter(ResultFSM), F.chat.type != ChatType.PRIVATE)
async def result_fsm_not_private(message: Message) -> None:
    url = await bot_deep_link(message.bot, "tova")
    await message.reply(
        "Ввод результата TOVA только в личке с ботом.",
        reply_markup=private_redirect_kb(url),
    )


@router.callback_query(F.data.startswith("tova:confirm:"))
async def cb_confirm_match(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        return
    _, _, match_id_s, accept_s = parts
    match_id = int(match_id_s)
    accept = accept_s == "1"

    user = await users_service.get_or_create_user(
        session,
        tg_id=callback.from_user.id,
        username=callback.from_user.username,
    )
    match = await matches_service.get_match(session, match_id)
    if match is None:
        await callback.message.answer("Матч не найден.")
        return

    status, match = await matches_service.confirm_match_by_user(
        session, match, user, accept=accept
    )
    p1 = await matches_service.get_user(session, match.player1_id)
    p2 = await matches_service.get_user(session, match.player2_id)
    assert p1 and p2

    if status == "not_participant":
        await callback.message.answer("Вы не участник этого матча.")
        return
    if status == "already_closed":
        await callback.message.answer(f"Матч уже закрыт (статус: {match.status}).")
        return
    if status == "rejected":
        text = f"Матч #{match.id} отклонён участником."
        await callback.message.answer(text)
        for tg_id in {p1.tg_id, p2.tg_id} - {callback.from_user.id}:
            try:
                await callback.bot.send_message(tg_id, text)
            except Exception:
                pass
        return
    if status == "waiting_other":
        await callback.message.answer("Вы подтвердили. Ждём второго участника.")
        return

    # pending_admin
    goals = await matches_service.load_match_goals(session, match.id)
    card = matches_service.format_match_card(match, p1, p2, goals)
    notice = card + "\n\nОба игрока подтвердили. Матч на проверке у администрации TOVA."
    for tg_id in {p1.tg_id, p2.tg_id}:
        try:
            await callback.bot.send_message(tg_id, notice)
        except Exception:
            pass

    settings = get_settings()
    admin_text = "Проверка результата TOVA:\n\n" + card
    admin_ids = set(settings.admin_ids)
    for uname in settings.admin_usernames:
        admin_user = await users_service.get_user_by_username(session, uname)
        if admin_user:
            admin_ids.add(admin_user.tg_id)
    for admin_id in admin_ids:
        try:
            if match.screenshot_file_id:
                await callback.bot.send_photo(
                    admin_id,
                    photo=match.screenshot_file_id,
                    caption=admin_text,
                    reply_markup=_admin_kb(match.id),
                )
            else:
                await callback.bot.send_message(
                    admin_id,
                    admin_text,
                    reply_markup=_admin_kb(match.id),
                )
        except Exception:
            pass


@router.callback_query(F.data.startswith("tova:admin:"))
async def cb_admin_match(callback: CallbackQuery, session: AsyncSession) -> None:
    settings = get_settings()
    if not settings.is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    await callback.answer()
    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        return
    _, _, match_id_s, approve_s = parts
    match_id = int(match_id_s)
    approve = approve_s == "1"

    match = await matches_service.get_match(session, match_id)
    if match is None:
        await callback.message.answer("Матч не найден.")
        return

    status, match = await matches_service.admin_decide_match(
        session, match, approve=approve
    )
    if status == "wrong_status":
        await callback.message.answer(f"Матч в статусе {match.status}, решение недоступно.")
        return

    p1 = await matches_service.get_user(session, match.player1_id)
    p2 = await matches_service.get_user(session, match.player2_id)
    assert p1 and p2
    verb = "засчитан" if approve else "отклонён администрацией"
    text = f"Матч #{match.id} ({p1.nickname} {match.score1}:{match.score2} {p2.nickname}) {verb}."
    await callback.message.answer(text)
    for tg_id in {p1.tg_id, p2.tg_id}:
        try:
            await callback.bot.send_message(tg_id, text)
        except Exception:
            pass
