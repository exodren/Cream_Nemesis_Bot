from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _parse_admin_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def _parse_usernames(raw: str | None) -> list[str]:
    return [name.lower() for name in _parse_usernames_display(raw)]


def _parse_usernames_display(raw: str | None) -> list[str]:
    if not raw:
        return []
    names: list[str] = []
    for part in raw.split(","):
        name = part.strip().lstrip("@")
        if name:
            names.append(name)
    return names


def _parse_chat_id(raw: str | None, default: int = 0) -> int:
    if not raw or not str(raw).strip():
        return default
    return int(str(raw).strip())


def telegram_c_id(chat_id: int) -> str:
    """Convert API chat id (-1003730057446) to t.me/c/<id>/... segment."""
    if not chat_id:
        return "0"
    digits = str(abs(chat_id))
    if digits.startswith("100") and len(digits) >= 13:
        return digits[3:]
    return digits


TOPIC_ENV_KEYS: dict[str, str] = {
    "lpl_stats": "TOPIC_LPL_STATS",
    "lpl_scorers": "TOPIC_LPL_SCORERS",
    "lpl_roster": "TOPIC_LPL_ROSTER",
    "coach": "TOPIC_COACH",
    "hall_cn": "TOPIC_HALL_CN",
    "ri_calendar": "TOPIC_RI_CALENDAR",
    "ri_rules": "TOPIC_RI_RULES",
    "ri_regulation": "TOPIC_RI_REGULATION",
    "ri_participants": "TOPIC_RI_PARTICIPANTS",
    "ri_guide": "TOPIC_RI_GUIDE",
    "ri_hall": "TOPIC_RI_HALL",
    "ri_award_zidane": "TOPIC_RI_AWARD_ZIDANE",
    "ri_award_puskas": "TOPIC_RI_AWARD_PUSKAS",
    "ri_award_yashin": "TOPIC_RI_AWARD_YASHIN",
    "ri_award_ballon": "TOPIC_RI_AWARD_BALLON",
    "ri_award_progress": "TOPIC_RI_AWARD_PROGRESS",
    "ucl_groups": "TOPIC_UCL_GROUPS",
    "ucl_playoff": "TOPIC_UCL_PLAYOFF",
    "uel_groups": "TOPIC_UEL_GROUPS",
    "uel_playoff": "TOPIC_UEL_PLAYOFF",
    "uecl_groups": "TOPIC_UECL_GROUPS",
    "uecl_playoff": "TOPIC_UECL_PLAYOFF",
    "apl": "TOPIC_APL",
    "laliga": "TOPIC_LALIGA",
    "serie_a": "TOPIC_SERIE_A",
    "bundesliga": "TOPIC_BUNDESLIGA",
    "cup_apl": "TOPIC_CUP_APL",
    "cup_laliga": "TOPIC_CUP_LALIGA",
    "cup_serie_a": "TOPIC_CUP_SERIE_A",
    "cup_bundesliga": "TOPIC_CUP_BUNDESLIGA",
    "cup_england": "TOPIC_CUP_ENGLAND",
    "cup_spain": "TOPIC_CUP_SPAIN",
    "cup_italy": "TOPIC_CUP_ITALY",
    "cup_germany": "TOPIC_CUP_GERMANY",
    "sc_uefa": "TOPIC_SC_UEFA",
    "sc_spain": "TOPIC_SC_SPAIN",
    "sc_england": "TOPIC_SC_ENGLAND",
    "sc_italy": "TOPIC_SC_ITALY",
    "sc_germany": "TOPIC_SC_GERMANY",
    "vsa_hall": "TOPIC_VSA_HALL",
}


def _load_topics() -> dict[str, int]:
    topics: dict[str, int] = {}
    for key, env_name in TOPIC_ENV_KEYS.items():
        raw = os.getenv(env_name, "").strip()
        topics[key] = int(raw) if raw else 0
    return topics


class Settings:
    def __init__(self) -> None:
        self.bot_token = os.getenv("BOT_TOKEN", "").strip()
        self.admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS"))
        self.tova_admin_ids = _parse_admin_ids(
            os.getenv("TOVA_ADMIN_ID") or os.getenv("ZARIF_TG_ID")
        )
        self.admin_usernames = _parse_usernames(os.getenv("ADMIN_USERNAMES"))
        self.league_admins = {
            "cn": _parse_usernames_display(os.getenv("ADMINS_CN")),
            "lpl": _parse_usernames_display(os.getenv("ADMINS_LPL")),
            "ri": _parse_usernames_display(os.getenv("ADMINS_RI")),
            "vsa": _parse_usernames_display(os.getenv("ADMINS_VSA")),
            "tova": _parse_usernames_display(os.getenv("ADMINS_TOVA")),
        }
        self.main_chat_id = _parse_chat_id(os.getenv("MAIN_CHAT_ID"))
        self.ri_chat_id = _parse_chat_id(os.getenv("RI_CHAT_ID"), default=self.main_chat_id)
        self.vsa_chat_id = _parse_chat_id(os.getenv("VSA_CHAT_ID"), default=self.main_chat_id)
        self.topics = _load_topics()
        self.current_season = int(os.getenv("CURRENT_SEASON", "1") or 1)

        default_db = (BASE_DIR / "data" / "bot.db").as_posix()
        self.database_url = os.getenv(
            "DATABASE_URL",
            f"sqlite+aiosqlite:///{default_db}",
        )

    def require_token(self) -> str:
        if not self.bot_token or self.bot_token == "replace_with_botfather_token":
            raise RuntimeError(
                "BOT_TOKEN не задан. Скопируйте .env.example в .env и укажите токен BotFather."
            )
        return self.bot_token

    @property
    def assets_dir(self) -> Path:
        return BASE_DIR / "assets"

    @property
    def table_template_path(self) -> Path:
        return self.assets_dir / "table_template.jpg"

    def is_tova_admin(self, user_id: int, username: str | None = None) -> bool:
        if self.tova_admin_ids and user_id in self.tova_admin_ids:
            return True
        tova_names = {name.lower() for name in self.league_admins.get("tova", [])}
        if username and username.lstrip("@").lower() in tova_names:
            return True
        return False

    def is_admin(self, user_id: int, username: str | None = None) -> bool:
        if user_id in self.admin_ids:
            return True
        if username and username.lstrip("@").lower() in self.admin_usernames:
            return True
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
