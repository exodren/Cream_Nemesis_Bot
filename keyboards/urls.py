from __future__ import annotations

from config import get_settings, telegram_c_id

_settings = get_settings()


def _topic(chat_id: int, topic_key: str) -> str | None:
    topic_id = _settings.topics.get(topic_key, 0)
    if not chat_id or not topic_id:
        return None
    return f"https://t.me/c/{telegram_c_id(chat_id)}/{topic_id}"


_MAIN = _settings.main_chat_id

# --- Main league chat (MAIN_CHAT_ID) ---
LPL_STATS = _topic(_MAIN, "lpl_stats")
LPL_SCORERS = _topic(_MAIN, "lpl_scorers")
LPL_ROSTER = _topic(_MAIN, "lpl_roster")
COACH_MODE = _topic(_MAIN, "coach")
HALL_OF_FAME_CN = _topic(_MAIN, "hall_cn")
RI_HALL_OF_FAME = _topic(_MAIN, "ri_hall")
VSA_HALL_OF_FAME = _topic(_MAIN, "vsa_hall")

# --- РИ: внешние таблицы ---
RI_TABLES_DOWNLOAD = "https://winner-9bee4.firebaseapp.com/download.html"
EUROCUPS_TABLE = (
    "https://winner-9bee4.firebaseapp.com/"
    "?action=follow_tournament&id=IDoZFzZhuzg9BWFxMoYp"
)
LEAGUES_TABLE = (
    "https://winner-9bee4.firebaseapp.com/"
    "?action=follow_tournament&id=ozquah6d1dtdf7mCzoy5"
)
CUPS_LEAGUES_TABLE = (
    "https://winner-9bee4.firebaseapp.com/"
    "?action=follow_tournament&id=bdcewIk194nIWbm1xckC"
)
CUPS_COUNTRIES_TABLE = (
    "https://winner-9bee4.firebaseapp.com/"
    "?action=follow_tournament&id=AJ8TlsmqOpNqzxt8Jl5J"
)
SC_TABLE = (
    "https://winner-9bee4.firebaseapp.com/"
    "?action=follow_tournament&id=Z9ZrKZcwLoyqX31ebTH6"
)
RI_SCORERS_SHEET = (
    "https://docs.google.com/spreadsheets/d/"
    "1s-0wj1ab8RgkxO635LGCU8TVV7h6Jlt3aCHM-_dfy6k/edit?usp=drivesdk"
)
