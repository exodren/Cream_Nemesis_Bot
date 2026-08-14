from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config import BASE_DIR, get_settings
from services.tova_stats import PlayerStats, ScorerStats

ROWS_PER_PAGE = 14
TEXT_COLOR = (40, 40, 40)
HEADER_COLOR = (70, 55, 30)
GOLD = (197, 160, 89)
LINE_COLOR = (180, 170, 150)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    fonts_dir = BASE_DIR / "assets" / "fonts"
    candidates = [
        fonts_dir / ("Georgia-Bold.ttf" if bold else "Georgia.ttf"),
        Path(r"C:\Windows\Fonts\georgia.ttf"),
        Path(r"C:\Windows\Fonts\times.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _open_template() -> Image.Image:
    path = get_settings().table_template_path
    return Image.open(path).convert("RGB")


def _content_box(img: Image.Image) -> tuple[int, int, int, int]:
    w, h = img.size
    left = int(w * 0.10)
    right = int(w * 0.90)
    top = int(h * 0.22)
    bottom = int(h * 0.90)
    return left, top, right, bottom


def _to_bytes(img: Image.Image) -> BytesIO:
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def render_standings_pages(
    rows: list[PlayerStats],
    *,
    season: int,
    title: str = "ТАБЛИЦА TOVA",
) -> list[BytesIO]:
    if not rows:
        rows = []
    pages: list[BytesIO] = []
    total_pages = max(1, (len(rows) + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE) if rows else 1

    for page_idx in range(total_pages):
        chunk = rows[page_idx * ROWS_PER_PAGE : (page_idx + 1) * ROWS_PER_PAGE]
        img = _open_template()
        draw = ImageDraw.Draw(img)
        left, top, right, bottom = _content_box(img)
        width = right - left

        title_font = _font(36, bold=True)
        header_font = _font(22, bold=True)
        row_font = _font(20)
        small_font = _font(16)

        page_title = title if total_pages == 1 else f"{title} ({page_idx + 1}/{total_pages})"
        draw.text((left, top), page_title, font=title_font, fill=HEADER_COLOR)
        draw.text(
            (left, top + 42),
            f"Сезон {season}",
            font=small_font,
            fill=GOLD,
        )

        y = top + 78
        col_x = {
            "n": left,
            "nick": left + int(width * 0.08),
            "i": left + int(width * 0.48),
            "v": left + int(width * 0.56),
            "n2": left + int(width * 0.64),
            "p": left + int(width * 0.72),
            "g": left + int(width * 0.80),
            "pts": left + int(width * 0.92),
        }
        headers = [
            ("#", "n"),
            ("Никнейм", "nick"),
            ("И", "i"),
            ("В", "v"),
            ("Н", "n2"),
            ("П", "p"),
            ("Голы", "g"),
            ("О", "pts"),
        ]
        for label, key in headers:
            draw.text((col_x[key], y), label, font=header_font, fill=HEADER_COLOR)
        y += 32
        draw.line((left, y, right, y), fill=LINE_COLOR, width=2)
        y += 10

        if not chunk:
            draw.text((left, y + 20), "Пока нет подтверждённых матчей", font=row_font, fill=TEXT_COLOR)
        else:
            start_n = page_idx * ROWS_PER_PAGE + 1
            for offset, row in enumerate(chunk):
                n = start_n + offset
                values = {
                    "n": str(n),
                    "nick": (row.nickname[:18] + "…") if len(row.nickname) > 18 else row.nickname,
                    "i": str(row.played),
                    "v": str(row.wins),
                    "n2": str(row.draws),
                    "p": str(row.losses),
                    "g": row.goals_display,
                    "pts": str(row.points),
                }
                fill = GOLD if n <= 3 else TEXT_COLOR
                for key, val in values.items():
                    draw.text((col_x[key], y), val, font=row_font, fill=fill)
                y += 34
                if y > bottom - 20:
                    break

        pages.append(_to_bytes(img))
    return pages


def render_scorers_pages(
    rows: list[ScorerStats],
    *,
    season: int,
    title: str = "БОМБАРДИРЫ TOVA",
) -> list[BytesIO]:
    pages: list[BytesIO] = []
    total_pages = max(1, (len(rows) + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE) if rows else 1

    for page_idx in range(total_pages):
        chunk = rows[page_idx * ROWS_PER_PAGE : (page_idx + 1) * ROWS_PER_PAGE]
        img = _open_template()
        draw = ImageDraw.Draw(img)
        left, top, right, bottom = _content_box(img)
        width = right - left

        title_font = _font(36, bold=True)
        header_font = _font(22, bold=True)
        row_font = _font(20)
        small_font = _font(16)

        page_title = title if total_pages == 1 else f"{title} ({page_idx + 1}/{total_pages})"
        draw.text((left, top), page_title, font=title_font, fill=HEADER_COLOR)
        draw.text((left, top + 42), f"Сезон {season}", font=small_font, fill=GOLD)

        y = top + 78
        col_x = {
            "n": left,
            "player": left + int(width * 0.10),
            "goals": left + int(width * 0.55),
            "nick": left + int(width * 0.68),
        }
        for label, key in (
            ("N", "n"),
            ("Игрок", "player"),
            ("Голы", "goals"),
            ("Никнейм", "nick"),
        ):
            draw.text((col_x[key], y), label, font=header_font, fill=HEADER_COLOR)
        y += 32
        draw.line((left, y, right, y), fill=LINE_COLOR, width=2)
        y += 10

        if not chunk:
            draw.text((left, y + 20), "Пока нет голов в сезоне", font=row_font, fill=TEXT_COLOR)
        else:
            start_n = page_idx * ROWS_PER_PAGE + 1
            for offset, row in enumerate(chunk):
                n = start_n + offset
                player = row.player_name if len(row.player_name) <= 22 else row.player_name[:21] + "…"
                nick = row.nickname if len(row.nickname) <= 16 else row.nickname[:15] + "…"
                fill = GOLD if n <= 3 else TEXT_COLOR
                draw.text((col_x["n"], y), str(n), font=row_font, fill=fill)
                draw.text((col_x["player"], y), player, font=row_font, fill=fill)
                draw.text((col_x["goals"], y), str(row.goals), font=row_font, fill=fill)
                draw.text((col_x["nick"], y), nick, font=row_font, fill=fill)
                y += 34
                if y > bottom - 20:
                    break

        pages.append(_to_bytes(img))
    return pages
