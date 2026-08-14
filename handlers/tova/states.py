from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class NicknameFSM(StatesGroup):
    waiting_nickname = State()


class ResultFSM(StatesGroup):
    waiting_scorers_p1 = State()
    waiting_scorers_p2 = State()
    waiting_screenshot = State()
