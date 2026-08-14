from __future__ import annotations

from config import get_settings, telegram_c_id

_settings = get_settings()


def _topic(chat_id: int, topic_key: str) -> str | None:
    topic_id = _settings.topics.get(topic_key, 0)
    if not chat_id or not topic_id:
        return None
    return f"https://t.me/c/{telegram_c_id(chat_id)}/{topic_id}"


_MAIN = _settings.main_chat_id
_RI = _settings.ri_chat_id or _MAIN
_VSA = _settings.vsa_chat_id or _MAIN

# --- Main league chat (MAIN_CHAT_ID) ---
LPL_STATS = _topic(_MAIN, "lpl_stats")
LPL_SCORERS = _topic(_MAIN, "lpl_scorers")
LPL_ROSTER = _topic(_MAIN, "lpl_roster")
COACH_MODE = _topic(_MAIN, "coach")
HALL_OF_FAME_CN = _topic(_MAIN, "hall_cn")

# --- Equal Play / РИ chat (RI_CHAT_ID, иначе MAIN_CHAT_ID) ---
RI_CALENDAR = _topic(_RI, "ri_calendar")
RI_RULES = _topic(_RI, "ri_rules")
RI_REGULATION = _topic(_RI, "ri_regulation")
RI_PARTICIPANTS = _topic(_RI, "ri_participants")
RI_GUIDE = _topic(_RI, "ri_guide")
RI_HALL_OF_FAME = _topic(_RI, "ri_hall")

RI_AWARD_ZIDANE = _topic(_RI, "ri_award_zidane")
RI_AWARD_PUSKAS = _topic(_RI, "ri_award_puskas")
RI_AWARD_YASHIN = _topic(_RI, "ri_award_yashin")
RI_AWARD_BALLON = _topic(_RI, "ri_award_ballon")
RI_AWARD_PROGRESS = _topic(_RI, "ri_award_progress")

# Tables download hub
RI_TABLES_DOWNLOAD = "https://winner-9bee4.firebaseapp.com/download.html"

# ЛЧ
UCL_GROUPS = _topic(_RI, "ucl_groups")
UCL_PLAYOFF = _topic(_RI, "ucl_playoff")
UCL_TABLE = (
    "https://winner-9bee4.firebaseapp.com/"
    "?action=follow_tournament&id=IDoZFzZhuzg9BWFxMoYp"
)

# ЛЕ
UEL_GROUPS = _topic(_RI, "uel_groups")
UEL_PLAYOFF = _topic(_RI, "uel_playoff")
UEL_TABLE = UCL_TABLE

# ЛК
UCL_CONF_GROUPS = _topic(_RI, "uecl_groups")
UCL_CONF_PLAYOFF = _topic(_RI, "uecl_playoff")
UCL_CONF_TABLE = UCL_TABLE

# Чемпионаты
APL = _topic(_RI, "apl")
LALIGA = _topic(_RI, "laliga")
SERIE_A = _topic(_RI, "serie_a")
BUNDESLIGA = _topic(_RI, "bundesliga")
LEAGUES_TABLE = (
    "https://winner-9bee4.firebaseapp.com/"
    "?action=follow_tournament&id=ozquah6d1dtdf7mCzoy5"
)

# Кубки
CUP_APL = _topic(_RI, "cup_apl")
CUP_LALIGA = _topic(_RI, "cup_laliga")
CUP_SERIE_A = _topic(_RI, "cup_serie_a")
CUP_BUNDESLIGA = _topic(_RI, "cup_bundesliga")
CUP_ENGLAND = _topic(_RI, "cup_england")
CUP_SPAIN = _topic(_RI, "cup_spain")
CUP_ITALY = _topic(_RI, "cup_italy")
CUP_GERMANY = _topic(_RI, "cup_germany")
CUPS_LEAGUES_TABLE = (
    "https://winner-9bee4.firebaseapp.com/"
    "?action=follow_tournament&id=bdcewIk194nIWbm1xckC"
)
CUPS_COUNTRIES_TABLE = (
    "https://winner-9bee4.firebaseapp.com/"
    "?action=follow_tournament&id=AJ8TlsmqOpNqzxt8Jl5J"
)

# Суперкубки
SC_UEFA = _topic(_RI, "sc_uefa")
SC_SPAIN = _topic(_RI, "sc_spain")
SC_ENGLAND = _topic(_RI, "sc_england")
SC_ITALY = _topic(_RI, "sc_italy")
SC_GERMANY = _topic(_RI, "sc_germany")
SC_TABLE = (
    "https://winner-9bee4.firebaseapp.com/"
    "?action=follow_tournament&id=Z9ZrKZcwLoyqX31ebTH6"
)

RI_SCORERS_SHEET = (
    "https://docs.google.com/spreadsheets/d/"
    "1s-0wj1ab8RgkxO635LGCU8TVV7h6Jlt3aCHM-_dfy6k/edit?usp=drivesdk"
)

# --- VSA (VSA_CHAT_ID, иначе MAIN_CHAT_ID) ---
VSA_HALL_OF_FAME = _topic(_VSA, "vsa_hall")
