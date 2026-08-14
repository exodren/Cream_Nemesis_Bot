from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import any_state
from aiogram.types import Message

from config import telegram_c_id
from keyboards.main import main_menu_kb

router = Router(name="common")

HELP_TEXT = (
    "<b>Cream Nemesis Bot</b>\n\n"
    "<b>Основные команды</b>\n"
    "/start — главное меню\n"
    "/help — эта справка\n"
    "/cancel — отменить текущий ввод (ник / результат)\n\n"
    "<b>TOVA</b>\n"
    "/go_tova — поиск соперника\n"
    "/cancel_tova — выйти из очереди\n"
    "/result_tova nick1 8:2 nick2 — сдать результат (только в ЛС)\n"
    "/cancel_match — отклонить свой незакрытый матч TOVA\n\n"
    "<b>Админам</b>\n"
    "/warn /unwarn /mute /unmute /ban /unban\n"
    "/topicid — ID чата и темы (для .env)\n\n"
    "Ссылки на темы закрытых чатов открываются только у участников этих чатов."
)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu_kb())


@router.message(Command("topicid", "chatid"))
async def cmd_topicid(message: Message) -> None:
    chat_id = message.chat.id
    thread_id = message.message_thread_id
    c_seg = telegram_c_id(chat_id)
    lines = [
        f"<b>MAIN_CHAT_ID</b> = <code>{chat_id}</code>",
        f"Сегмент ссылки t.me/c/ = <code>{c_seg}</code>",
    ]
    if thread_id:
        lines.append(f"<b>ID темы</b> (TOPIC_…) = <code>{thread_id}</code>")
        lines.append(f"Ссылка: https://t.me/c/{c_seg}/{thread_id}")
        lines.append("\nПропиши этот ID в .env и перезапусти бота.")
    else:
        lines.append(
            "\nЭто не тема форума (или General).\n"
            "Открой нужную тему чата и снова отправь /topicid."
        )
    await message.answer("\n".join(lines))


@router.message(Command("cancel"), StateFilter(any_state))
async def cmd_cancel_any(message: Message, state: FSMContext) -> None:
    if message.chat.type != ChatType.PRIVATE:
        await message.answer("Отмена ввода доступна в личке с ботом.")
        return
    current = await state.get_state()
    if current is None:
        await message.answer("Нечего отменять.")
        return
    await state.clear()
    await message.answer("Ввод отменён.")


@router.message(Command("cancel"), F.chat.type == ChatType.PRIVATE)
async def cmd_cancel_idle(message: Message, state: FSMContext) -> None:
    # Fallback when no FSM state (specific cancel handlers may have higher priority)
    current = await state.get_state()
    if current is None:
        await message.answer("Нечего отменять. Меню: /start")
