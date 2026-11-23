import os
import re
import json
import time
import html
import sys
import random
import hashlib
import logging
import calendar
import unicodedata
import threading
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

import requests
import feedparser
from bs4 import BeautifulSoup
from flask import Flask, jsonify

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# =========================================================
# НАСТРОЙКИ
# =========================================================

#BOT_TOKEN = "8466417819:AAHu_yTBGaCkha74-WKyk6T1U7VVLcMD-Yc"
#CHANNEL_ID = "@n_footbal_news_test"

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@n_football_news")
CHANNEL_PUBLIC_HISTORY_URL = "https://t.me/s/n_football_news"

POSTED_FILE = "posted_news.json"
PUBLISHER_MESSAGE_IDS = set()
REQUEST_TIMEOUT = 25
CHECK_LIMIT_PER_FEED = 60
SLEEP_BETWEEN_POSTS = 2 * 60
LOOP_MIN_SECONDS = 40 * 60  # минимум 40 минут между циклами
LOOP_MAX_SECONDS = 60 * 60  # максимум 60 минут между циклами
# Одноразовый ручной запуск: после указанного времени снова действует обычная пауза.
FORCE_FIRST_POST_BEFORE_UTC = datetime(2026, 11, 21, 0, 10, tzinfo=timezone.utc)
STRICT_KEYWORD_FILTER = True
MAX_POST_LENGTH = 3200
MIN_ARTICLE_TEXT_LEN = 220
MAX_ARTICLE_TEXT_LEN = 1400
MAX_SUMMARY_LEN = 2200
MAX_HASHTAGS = 8
DETAILS_FALLBACK_TEXT = "Подробности в источнике по ссылке ниже."
AUTO_DELETE_GARBAGE_POSTS = True
MIN_POSTS_PER_CYCLE = 1
MAX_POSTS_PER_CYCLE = 1
POSTED_HISTORY_LIMIT = 5000   
GENERAL_NEWS_MAX_AGE_HOURS = 48
LIVERESULT_MAX_AGE_HOURS = 8
SCHEDULE_POST_GRACE_MINUTES = 90
DAILY_SCHEDULE_HOUR_MSK = 6
DAILY_SCHEDULE_WINDOW_MINUTES = 60
SCHEDULE_POLL_SECONDS = 60
if ZoneInfo is not None:
    try:
        MSK_TZ = ZoneInfo("Europe/Moscow")
    except Exception:
        MSK_TZ = timezone(timedelta(hours=3))
else:
    MSK_TZ = timezone(timedelta(hours=3))
NEWS_DAY_TZ = MSK_TZ
ESPN_SCOREBOARD_URL_TEMPLATE = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard"

TRACKED_MATCH_LEAGUES = []
ENGLAND_FLAG = "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F"

SOCCER365_GAMES_DATA_URL = "https://soccer365.ru/?c=live&a=games_data&competition_id={competition_id}&dt=&fr=1&noads=1"
SOCCER365_ONLINE_URL = "https://soccer365.ru/online/"
TRACKED_SOCCER365_COMPETITIONS = [
    {"title": "UEFA Champions League", "flag": "🇪🇺", "competition_id": 19},
    {"title": "UEFA Europa League", "flag": "🇪🇺", "competition_id": 20},
    {"title": "UEFA Conference League", "flag": "🇪🇺", "competition_id": 2032},
    {"title": "Premier League (АПЛ)", "flag": ENGLAND_FLAG, "competition_id": 12},
    {"title": "Англия — Чемпионшип", "flag": ENGLAND_FLAG, "competition_id": 565},
    {"title": "LaLiga (Испания)", "flag": "🇪🇸", "competition_id": 16},
    {"title": "Serie A (Италия)", "flag": "🇮🇹", "competition_id": 15},
    {"title": "Италия — Серия B", "flag": "🇮🇹", "competition_id": 627},
    {"title": "РПЛ (Россия)", "flag": "🇷🇺", "competition_id": 13},
    {"title": "Fonbet Кубок России", "flag": "🇷🇺", "competition_id": 786},
    {"title": "Турция — Суперлига", "flag": "🇹🇷", "competition_id": 723},
    {"title": "Австралия — А-Лига", "flag": "🇦🇺", "competition_id": 464},
    {"title": "Saudi Pro League", "flag": "🇸🇦", "competition_id": 691},
    {"title": "Аргентина — Примера", "flag": "🇦🇷", "competition_id": 454},
    {"title": "Колумбия — Примера A", "flag": "🇨🇴", "competition_id": 544},
    {"title": "Бразилия — Серия A", "flag": "🇧🇷", "competition_id": 419},
    {"title": "MLS", "flag": "🇺🇸", "competition_id": 436},
    {"title": "Bundesliga (Германия)", "flag": "🇩🇪", "competition_id": 17},
    {"title": "Ligue 1 (Франция)", "flag": "🇫🇷", "competition_id": 18},
    {"title": "Primeira Liga (Португалия)", "flag": "🇵🇹", "competition_id": 681},
    {"title": "Eredivisie (Нидерланды)", "flag": "🇳🇱", "competition_id": 596},
    {"title": "Болгария — Первая лига", "flag": "🇧🇬", "competition_id": 532},
    {"title": "Казахстан — Премьер-лига", "flag": "🇰🇿", "competition_id": 636},
    {"title": "Кубок Украины", "flag": "🇺🇦", "competition_id": 778},
    {"title": "Швейцария — Суперлига", "flag": "🇨🇭", "competition_id": 716},
    {"title": "Южная Корея — Кей-лига 1", "flag": "🇰🇷", "competition_id": 637},
    {"title": "Юношеская лига УЕФА", "flag": "🇪🇺", "competition_id": 1019},
    {"title": "Азербайджанская Премьер-Лига", "flag": "🇦🇿", "competition_id": 477},
]

TITLE_OVERRIDES_BY_URL = {
    "https://www.flashscore.com/football/italy/serie-b/fixtures/": "Италия — Серия B",
}

LEAGUE_TITLE_OVERRIDES_BY_CODE = {
    "tur.1": "Турция — Суперлига",
    "ita.2": "Италия — Серия B",
}

TEAM_NAME_RU_MAP = {
    "arsenal": "Арсенал",
    "aston villa": "Астон Вилла",
    "atletico madrid": "Атлетико Мадрид",
    "atl. nacional": "Атлетико Насьональ",
    "atalanta": "Аталанта",
    "barcelona": "Барселона",
    "bayer leverkusen": "Байер Леверкузен",
    "bayern munich": "Бавария",
    "bodo/glimt": "Буде-Глимт",
    "brentford": "Брентфорд",
    "chelsea": "Челси",
    "club brugge u19": "Брюгге U19",
    "cska moscow": "ЦСКА Москва",
    "dynamo makhachkala": "Динамо Махачкала",
    "galatasaray": "Галатасарай",
    "inter": "Интер",
    "inter u19": "Интер U19",
    "juventus": "Ювентус",
    "liverpool": "Ливерпуль",
    "manchester city": "Манчестер Сити",
    "manchester united": "Манчестер Юнайтед",
    "milan": "Милан",
    "newcastle united": "Ньюкасл Юнайтед",
    "paris saint-germain": "Пари Сен-Жермен",
    "psg": "ПСЖ",
    "real madrid": "Реал Мадрид",
    "sporting cp": "Спортинг",
    "tottenham hotspur": "Тоттенхэм",
    "villarreal u19": "Вильярреал U19",
    "wolverhampton wanderers": "Вулверхэмптон",
    "alanyaspor": "Аланьяспор",
    "anyang": "Аньян",
    "antalyaspor": "Антальяспор",
    "araz": "Араз",
    "atl. nacional": "Атлетико Насьональ",
    "atl. nacional medellin": "Атлетико Насьональ",
    "bahia": "Баия",
    "bari": "Бари",
    "bucaramanga": "Букараманга",
    "bucheon fc 1995": "Пучхон 1995",
    "catanzaro": "Катандзаро",
    "cesena": "Чезена",
    "cremonese": "Кремонезе",
    "cucuta": "Кукута",
    "daejeon": "Тэджон",
    "defensa y justicia": "Дефенса и Хустисия",
    "dep. pasto": "Депортиво Пасто",
    "dep. riestra": "Депортиво Риестра",
    "empoli": "Эмполи",
    "eyupspor": "Эюпспор",
    "fenerbahce": "Фенербахче",
    "fiorentina": "Фиорентина",
    "gabala": "Габала",
    "gaziantep": "Газиантеп",
    "gaziantep fk": "Газиантеп",
    "gremio": "Гремио",
    "gwangju fc": "Кванджу",
    "imisli fk": "Имишли",
    "independiente": "Индепендьенте",
    "jeju sk": "Чеджу",
    "juve stabia": "Юве Стабия",
    "kapaz": "Кяпаз",
    "karvan": "Карван",
    "krasnodar": "Краснодар",
    "kyzylzhar": "Кызылжар",
    "lanus": "Ланус",
    "levante": "Леванте",
    "lugano": "Лугано",
    "melbourne city": "Мельбурн Сити",
    "neftci baku": "Нефтчи Баку",
    "norwich": "Норвич",
    "okzhetpes": "Окжетпес",
    "paris saint-germain": "Пари Сен-Жермен",
    "pescara": "Пескара",
    "pohang": "Пхохан",
    "preston": "Престон",
    "qarabag": "Карабах",
    "racing club": "Расинг Клуб",
    "rayo vallecano": "Райо Вальекано",
    "reggiana": "Реджана",
    "sabah baku": "Сабах Баку",
    "sampdoria": "Сампдория",
    "septemvri sofia": "Септември София",
    "shamakhi": "Шамахы",
    "spartak varna": "Спартак Варна",
    "sporting cp": "Спортинг",
    "st. gallen": "Санкт-Галлен",
    "sumqayit": "Сумгаит",
    "turan tovuz": "Туран Товуз",
    "venezia": "Венеция",
    "ws wanderers": "Вестерн Сидней Уондерерс",
}

RSS_FEEDS = [
    {
        "name": "Sports.ru",
        "url": "https://raw.githubusercontent.com/nazimaov/football-rss-live/main/Sports.xml",
        "emoji": "⚽"
    },
    {
        "name": "Чемпионат",
        "url": "https://raw.githubusercontent.com/nazimaov/football-rss-live/main/Championat.xml",
        "emoji": "🔥"
    },
    {
        "name": "Матч ТВ",
        "url": "https://raw.githubusercontent.com/nazimaov/football-rss-live/main/MatchTV.xml",
        "emoji": "📺"
    },
    {
        "name": "Azerisport",
        "url": "https://raw.githubusercontent.com/nazimaov/football-rss-live/main/Azerisport.xml",
        "emoji": "⚽"
    },
    {
        "name": "Euro-Football",
        "url": "https://raw.githubusercontent.com/nazimaov/football-rss-live/main/Euro-Football.xml",
        "emoji": "📰"
    },
    {
        "name": "Soccer",
        "url": "https://raw.githubusercontent.com/nazimaov/football-rss-live/main/Soccer.ru.xml",
        "emoji": "⚽"
    },
]

KEYWORDS = [
    "football", "soccer", "футбол", "матч", "гол", "забил", "трансфер",
    "uefa", "fifa", "лига чемпионов", "лига европы", "conference league",
    "premier league", "la liga", "serie a", "bundesliga", "ligue 1",
    "рпл", "апл", "серия а", "ла лига", "бундеслига",
    "real madrid", "реал", "барселона", "barcelona", "arsenal", "арсенал",
    "манчестер сити", "manchester city", "liverpool", "chelsea",
    "manchester united", "tottenham", "bayern", "psg", "juventus",
    "inter", "milan", "ronaldo", "месси", "messi", "mbappe", "haaland",
    "bellingham", "vinicius", "роналду", "мбаппе", "холанд",
    "азербайджанский футбол",
    "qarabag", "карабах", "karabakh", "neftchi", "нефтчи",
    "sabail", "сабаил", "sumqayit", "сумгаит", "zire", "зиря",
    "turan", "туран", "kapaz", "капаз", "shamakhi", "шамахы",
    "premyer liqa", "премьер-лига азербайджана", "kubok azerbaycan",
    "кубок азербайджана"
]

NON_FOOTBALL_PATTERNS = [
    r"\bформул[аы]-?\s*[1-4]\b",
    r"\bformula\b",
    r"\bавтоспорт\b",
    r"\bmotorsport\b",
    r"\bf1\b|\bf2\b|\bf3\b|\bf4\b",
    r"\bтеннис\w*\b|\btennis\w*\b",
    r"\bбаскетбол\w*\b|\bbasketball\w*\b|\bnba\b|\bнба\b",
    r"\bхоккей\w*\b|\bhockey\w*\b|\bnhl\b|\bнхл\b|\bкхл\b|\bшайб\w*\b",
    r"\bволейбол\w*\b|\bvolleyball\w*\b",
    r"\bбокс\b|\bboxing\b|\bufc\b|\bmma\b",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
]

INTRO_TEMPLATES = [
    "⚡ Главная новость футбольного дня:",
    "🔥 В футбольном мире обсуждают:",
    "📰 Свежие новости из мира футбола:",
    "⚽ Что произошло в футбольном мире:",
    "🚨 Срочная новость из футбольного мира:",
    "👀 В центре внимания футбольных новостей:",
    "📢 Футбольные новости прямо сейчас:",
    "🏟 Последние события в мире футбола:",
    "📊 В футбольной повестке сегодня:",
    "💥 Громкая новость из мира футбола:"
]

ENDING_TEMPLATES: list[str] = []

DIVIDER = "━━━━━━━━━━━━━━━━"

NOISE_PATTERNS = [
    r"подписывайтесь.*",
    r"читайте также.*",
    r"источник[:].*",
    r"материалы по теме.*",
    r"реклама.*",
    r"©.*",
    r"видео.*доступно.*",
    r"поделиться.*",
    r"комментарии.*",
    r"телеграм[- ]канал.*",
    r"новости по теме.*",
    r"подпишитесь.*",
    r"эксклюзив.*",
    r"смотрите также.*",
    r"все права защищены.*",
]

GENERIC_NEWS_TITLES = {
    "матчи",
    "футбол",
    "football",
    "sports",
    "sport",
    "live",
    "онлайн",
    "конный мир",
    "видео",
    "video",
}

LISTING_PATH_PATTERNS = [
    r"^/$",
    r"^/football/?$",
    r"^/football/match/?$",
    r"^/match/?$",
    r"^/matches/?$",
    r"^/video/?$",
    r"^/video/channel/[^/]+/?$",
    r"^/channels?/?$",
    r"^/news/?$",
]

LOW_QUALITY_TEXT_MARKERS = [
    "прямой эфир",
    "смотреть онлайн",
    "live results",
    "результаты матчей",
    "каналы матч тв",
    "телеканала",
    "статистика матчей",
    "video channel",
]

GARBAGE_TITLE_PATTERNS = [
    r"^матчи$",
    r"^футбол$",
    r"^новости$",
    r"^главная$",
    r"^конный мир$",
    r"^трансляции и видео$",
    r"^матч-центр$",
    r"^телепрограмма$",
]

TAG_MAPPING = [
    ("реал", "#РеалМадрид"),
    ("real madrid", "#РеалМадрид"),
    ("барселона", "#Барселона"),
    ("barcelona", "#Барселона"),
    ("arsenal", "#Арсенал"),
    ("арсенал", "#Арсенал"),
    ("манчестер сити", "#МанСити"),
    ("manchester city", "#МанСити"),
    ("лига чемпионов", "#ЛигаЧемпионов"),
    ("champions league", "#ЛигаЧемпионов"),
    ("трансфер", "#Трансферы"),
    ("transfer", "#Трансферы"),
    ("карабах", "#Карабах"),
    ("qarabag", "#Карабах"),
    ("нефтчи", "#Нефтчи"),
    ("neftchi", "#Нефтчи"),
    ("азербайджан", "#АзербайджанФутбол"),
    ("azerbaijan", "#АзербайджанФутбол"),
]

BASE_HASHTAGS = [
    "#Футбол",
    "#НовостиФутбола",
    "#Football",
]


# =========================================================
# ЛОГИ
# =========================================================
class RepairMojibakeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original_msg = record.msg
        original_args = record.args
        try:
            if isinstance(record.msg, str):
                record.msg = repair_mojibake(record.msg)
            if isinstance(record.args, tuple):
                record.args = tuple(
                    repair_mojibake(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    key: repair_mojibake(value) if isinstance(value, str) else value
                    for key, value in record.args.items()
                }
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

for _handler in logging.getLogger().handlers:
    _handler.setFormatter(RepairMojibakeFormatter("%(asctime)s | %(levelname)s | %(message)s"))


# =========================================================
# ХРАНЕНИЕ ОПУБЛИКОВАННОГО
# =========================================================
def load_posted() -> Dict[str, Any]:
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("ids", [])
                    data.setdefault("fingerprints", [])
                    data.setdefault("links", [])
                    data.setdefault("title_keys", [])
                    data.setdefault("link_keys", [])
                    data.setdefault("titles", [])
                    data.setdefault("moderation_titles", [])
                    data.setdefault("publisher_message_ids", [])
                    data.setdefault("daily_schedule_dates", [])
                    data.setdefault("daily_schedule_pinned_message_id", None)
                    return data
                if isinstance(data, list):
                    return {
                        "ids": data,
                        "fingerprints": [],
                        "links": [],
                        "title_keys": [],
                        "link_keys": [],
                        "titles": [],
                        "moderation_titles": [],
                        "publisher_message_ids": [],
                        "daily_schedule_dates": [],
                        "daily_schedule_pinned_message_id": None,
                    }
        except Exception as e:
            logging.warning(f"Не удалось прочитать {POSTED_FILE}: {e}")
    return {
        "ids": [],
        "fingerprints": [],
        "links": [],
        "title_keys": [],
        "link_keys": [],
        "titles": [],
        "moderation_titles": [],
        "publisher_message_ids": [],
        "daily_schedule_dates": [],
        "daily_schedule_pinned_message_id": None,
    }


def trim_unique_tail(values: List[str], max_records: int) -> List[str]:
    seen = set()
    result_reversed = []
    for value in reversed(values):
        if not value or value in seen:
            continue
        seen.add(value)
        result_reversed.append(value)
        if len(result_reversed) >= max_records:
            break
    return list(reversed(result_reversed))


def save_posted(posted_data: Dict[str, Any]) -> None:
    try:
        posted_data["ids"] = trim_unique_tail(posted_data.get("ids", []), POSTED_HISTORY_LIMIT)
        posted_data["fingerprints"] = trim_unique_tail(posted_data.get("fingerprints", []), POSTED_HISTORY_LIMIT)
        posted_data["links"] = trim_unique_tail(posted_data.get("links", []), POSTED_HISTORY_LIMIT)
        posted_data["title_keys"] = trim_unique_tail(posted_data.get("title_keys", []), POSTED_HISTORY_LIMIT)
        posted_data["link_keys"] = trim_unique_tail(posted_data.get("link_keys", []), POSTED_HISTORY_LIMIT)
        posted_data["titles"] = trim_unique_tail(posted_data.get("titles", []), POSTED_HISTORY_LIMIT)
        posted_data["moderation_titles"] = trim_unique_tail(posted_data.get("moderation_titles", []), POSTED_HISTORY_LIMIT)
        posted_data["publisher_message_ids"] = trim_unique_tail(posted_data.get("publisher_message_ids", []), POSTED_HISTORY_LIMIT)
        posted_data["daily_schedule_dates"] = trim_unique_tail(posted_data.get("daily_schedule_dates", []), 120)
        
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(posted_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Не удалось сохранить {POSTED_FILE}: {e}")


# =========================================================
# TELEGRAM
# =========================================================
def telegram_request(method: str, data: Dict[str, Any]) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        response = requests.post(url, data=data, timeout=REQUEST_TIMEOUT)
        logging.info(f"{method} => {response.status_code}")
        if not response.ok:
            logging.error(f"Telegram error: {response.text}")
        return response.ok
    except Exception as e:
        logging.error(f"Ошибка запроса к Telegram: {e}")
        return False
def telegram_request_json(method: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        response = requests.post(url, data=data, timeout=REQUEST_TIMEOUT)
        logging.info(f"{method} => {response.status_code}")
        if not response.ok:
            logging.error(f"Telegram error: {response.text}")
            return None
        payload = response.json()
        if not payload.get("ok"):
            logging.error(f"Telegram API response not ok: {payload}")
            return None
        return payload
    except Exception as e:
        logging.error(f"Ошибка запроса к Telegram: {e}")
        return None


def send_text_to_telegram(text: str) -> bool:
    return telegram_request(
        "sendMessage",
        {
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
    )


def send_text_to_telegram_with_message_id(text: str) -> Optional[int]:
    payload = telegram_request_json(
        "sendMessage",
        {
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
    )
    if not payload:
        return None
    result = payload.get("result", {})
    return result.get("message_id")


def send_photo_to_telegram(photo_url: str, caption: str) -> bool:
    return telegram_request(
        "sendPhoto",
        {
            "chat_id": CHANNEL_ID,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
    )


def send_photo_to_telegram_with_message_id(photo_url: str, caption: str) -> Optional[int]:
    payload = telegram_request_json(
        "sendPhoto",
        {
            "chat_id": CHANNEL_ID,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
    )
    if not payload:
        return None
    result = payload.get("result", {})
    return result.get("message_id")


def delete_channel_message(message_id: int) -> bool:
    return telegram_request(
        "deleteMessage",
        {
            "chat_id": CHANNEL_ID,
            "message_id": message_id
        }
    )


def get_telegram_updates(offset: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
    """Получает новые публикации канала для фоновой модерации."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    data = {
        "timeout": 20,
        "allowed_updates": json.dumps(["channel_post", "edited_channel_post"]),
    }
    if offset is not None:
        data["offset"] = offset
    try:
        response = requests.post(url, data=data, timeout=30)
        if not response.ok:
            logging.error(f"getUpdates => {response.status_code}: {response.text}")
            return None
        payload = response.json()
        if not payload.get("ok"):
            logging.error(f"getUpdates response not ok: {payload}")
            return None
        return payload.get("result", [])
    except Exception as e:
        logging.error(f"Ошибка получения обновлений Telegram: {e}")
        return None


def is_target_channel(chat: Dict[str, Any]) -> bool:
    configured = normalize_spaces(CHANNEL_ID).lower()
    username = normalize_spaces(chat.get("username", "")).lower()
    if configured.startswith("@"):
        return username == configured[1:]
    return str(chat.get("id", "")) == configured


def extract_post_title(message: Dict[str, Any]) -> str:
    raw_text = message.get("text") or message.get("caption") or ""
    return extract_title_from_text(raw_text)


def extract_post_image_key(message: Dict[str, Any]) -> str:
    """Возвращает устойчивый идентификатор изображения/медиа поста."""
    photos = message.get("photo") or []
    if isinstance(photos, list) and photos:
        photo = photos[-1] if isinstance(photos[-1], dict) else {}
        file_key = photo.get("file_unique_id") or photo.get("file_id")
        if file_key:
            return f"photo:{file_key}"

    for media_type in ("video", "animation", "document"):
        media = message.get(media_type) or {}
        if isinstance(media, dict):
            file_key = media.get("file_unique_id") or media.get("file_id")
            if file_key:
                return f"{media_type}:{file_key}"
    return ""


def extract_title_from_text(raw_text: str) -> str:
    soup = BeautifulSoup(raw_text or "", "html.parser")
    plain_text = soup.get_text("\n", strip=True)
    for line in plain_text.splitlines():
        candidate = re.sub(r"^[^\wА-Яа-яЁё]+", "", line.strip()).strip()
        if len(candidate) >= 3:
            return candidate[:300]
    return ""


def fetch_recent_channel_titles() -> List[str]:
    """Берёт недавние заголовки из публичной ленты канала.

    Render не хранит файлы после перезапуска, поэтому это защищает от
    повторной публикации уже вышедших новостей даже после нового деплоя.
    """
    try:
        response = requests.get(CHANNEL_PUBLIC_HISTORY_URL, headers=get_headers(), timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        titles = []
        for node in soup.select(".tgme_widget_message_text"):
            title = extract_title_from_text(node.get_text("\n", strip=True))
            if len(title) >= 20:
                titles.append(title)
        logging.info(f"Прочитано заголовков из канала для антидублей: {len(titles)}")
        return titles
    except Exception as e:
        logging.warning(f"Не удалось прочитать историю канала: {e}")
        return []


def moderator_loop() -> None:
    """Удаляет дубли, опубликованные вручную или прошедшие из другого источника."""
    PUBLISHER_MESSAGE_IDS.update(load_posted().get("publisher_message_ids", []))
    # Фиксируем границу старых обновлений до начала публикаций.
    initial_updates = get_telegram_updates(-1)
    offset: Optional[int] = None
    if initial_updates:
        update_ids = [u.get("update_id") for u in initial_updates if isinstance(u.get("update_id"), int)]
        if update_ids:
            offset = max(update_ids) + 1

    while True:
        updates = get_telegram_updates(offset)
        if updates is None:
            time.sleep(30)
            continue

        for update in updates:
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                offset = update_id + 1

            message = update.get("channel_post") or update.get("edited_channel_post")
            if not message or not is_target_channel(message.get("chat", {})):
                continue

            message_id = message.get("message_id")
            if message_id is None:
                continue

            title = extract_post_title(message)
            if len(title) < 20:
                continue
            image_key = extract_post_image_key(message)

            posted_data = load_posted()
            known_titles = list(posted_data.get("titles", []))
            known_titles.extend(posted_data.get("moderation_titles", []))
            known_image_keys = set(posted_data.get("image_keys", []))
            known_image_keys.update(posted_data.get("moderation_image_keys", []))
            exact_known_title_keys = {build_title_key(item) for item in known_titles}
            is_own_message = str(message_id) in PUBLISHER_MESSAGE_IDS
            # Свой пост пропускаем только если это именно тот заголовок,
            # который только что записал издатель. Переформулированный дубль
            # собственного поста всё равно должен пройти модерацию.
            if is_own_message and build_title_key(title) in exact_known_title_keys:
                if image_key and image_key not in known_image_keys:
                    posted_data.setdefault("moderation_image_keys", []).append(image_key)
                    save_posted(posted_data)
                continue
            if image_key and image_key in known_image_keys:
                if delete_channel_message(message_id):
                    logging.warning(f"Модератор удалил дубль по изображению: {title[:120]}")
                continue
            raw_post_text = message.get("text") or message.get("caption") or ""
            if is_incomplete_news_post(title, "", raw_post_text):
                if delete_channel_message(message_id):
                    logging.warning(f"Модератор удалил неполный анонс: {title[:120]}")
                continue
            if is_similar_news_title(title, known_titles):
                if delete_channel_message(message_id):
                    logging.warning(f"Модератор удалил дубль: {title[:120]}")
                continue

            posted_data.setdefault("moderation_titles", []).append(title)
            if image_key:
                posted_data.setdefault("moderation_image_keys", []).append(image_key)
            save_posted(posted_data)

def pin_channel_message(message_id: int) -> bool:
    return telegram_request(
        "pinChatMessage",
        {
            "chat_id": CHANNEL_ID,
            "message_id": message_id,
            "disable_notification": True
        }
    )


def unpin_channel_message(message_id: int) -> bool:
    return telegram_request(
        "unpinChatMessage",
        {
            "chat_id": CHANNEL_ID,
            "message_id": message_id
        }
    )


def unpin_current_channel_message() -> bool:
    return telegram_request(
        "unpinChatMessage",
        {
            "chat_id": CHANNEL_ID
        }
    )


# =========================================================
# БАЗОВЫЕ УТИЛИТЫ
# =========================================================
def get_headers() -> Dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "ru-RU,ru;q=0.95,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def repair_mojibake(text: str) -> str:
    text = text or ""
    if not text:
        return ""
    # Detect common mojibake markers.
    if not re.search(r"[РС]", text):
        return text
    bad_score = text.count("Р") + text.count("С")
    for source_enc in ("cp1251",):
        try:
            fixed = text.encode(source_enc).decode("utf-8")
            fixed_bad_score = fixed.count("Р") + fixed.count("С")
            if fixed and fixed_bad_score < bad_score:
                return fixed
        except Exception:
            continue
    return text


def normalize_team_key(name: str) -> str:
    value = normalize_spaces(name).lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^\w\s/.-]", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def transliterate_token_to_ru(token: str) -> str:
    token = token or ""
    if not token:
        return token
    if re.search(r"[А-Яа-яЁё]", token):
        return token
    if not re.search(r"[A-Za-z]", token):
        return token
    if re.fullmatch(r"[A-Z]{2,}", token):
        return token

    source = token.lower()
    source = unicodedata.normalize("NFKD", source)
    source = "".join(ch for ch in source if not unicodedata.combining(ch))

    digraphs = [
        ("shch", "щ"), ("sch", "щ"), ("ch", "ч"), ("sh", "ш"),
        ("zh", "ж"), ("kh", "х"), ("ts", "ц"), ("ya", "я"),
        ("yo", "ё"), ("yu", "ю"), ("ye", "е"), ("th", "т"),
        ("ph", "ф"), ("ck", "к"), ("qu", "кв")
    ]
    for old, new in digraphs:
        source = source.replace(old, new)

    single_map = {
        "a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф",
        "g": "г", "h": "х", "i": "и", "j": "й", "k": "к", "l": "л",
        "m": "м", "n": "н", "o": "о", "p": "п", "q": "к", "r": "р",
        "s": "с", "t": "т", "u": "у", "v": "в", "w": "в", "x": "кс",
        "y": "и", "z": "з",
    }

    result = []
    for ch in source:
        result.append(single_map.get(ch, ch))
    out = "".join(result)

    if token and token[0].isupper() and out:
        out = out[0].upper() + out[1:]
    return out


def localize_team_name(name: str) -> str:
    text = repair_mojibake(normalize_spaces(name))
    if not text:
        return text

    mapped = TEAM_NAME_RU_MAP.get(normalize_team_key(text))
    if mapped:
        return mapped

    # For unknown clubs keep original name to avoid incorrect transliterations.
    return text


def html_escape(text: str) -> str:
    return html.escape(text or "")


def strip_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    return normalize_spaces(soup.get_text(" ", strip=True))


def truncate_smart(text: str, max_len: int) -> str:
    text = normalize_spaces(text)
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "..."


def split_sentences(text: str) -> List[str]:
    text = normalize_spaces(text)
    if not text:
        return []
    parts = re.split(r'(?<=[.!?…])\s+', text)
    return [p.strip() for p in parts if p.strip()]


def is_sentence_fragment(text: str) -> bool:
    """Определяет фразу, которая не должна начинать новый блок."""
    normalized = normalize_spaces(text).lower()
    return bool(re.match(
        r"^(где|когда|котор(?:ый|ая|ое|ые)|что|кто|которых|"
        r"а|и|но|также|при этом|поскольку|потому что|чтобы|если)\b",
        normalized,
        flags=re.IGNORECASE,
    ))


def remove_noise_lines(text: str) -> str:
    if not text:
        return ""

    lines = re.split(r'[\n\r]+', text)
    cleaned = []

    for line in lines:
        line = normalize_spaces(line)
        if not line:
            continue
        if len(line) < 25:
            continue

        bad = False
        for pattern in NOISE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                bad = True
                break

        if not bad:
            cleaned.append(line)

    return "\n".join(cleaned)


def hash_text(text: str) -> str:
    return hashlib.md5(normalize_spaces(text).lower().encode("utf-8")).hexdigest()


# =========================================================
# ФИЛЬТРЫ И ДУБЛИ
# =========================================================
def is_relevant_news(title: str, summary: str) -> bool:
    text = f"{title} {strip_html(summary)}".lower()

    for pattern in NON_FOOTBALL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return False

    if not STRICT_KEYWORD_FILTER:
        return True
    return any(keyword in text for keyword in KEYWORDS)


def is_generic_news_title(title: str) -> bool:
    normalized = normalize_title_for_fingerprint(title)
    if not normalized:
        return True
    if normalized in GENERIC_NEWS_TITLES:
        return True
    words = normalized.split()
    if len(words) <= 2 and any(marker in normalized for marker in {"канал", "эфир", "трансляц", "tv", "тв"}):
        return True
    return False


def is_listing_like_url(url: str) -> bool:
    canonical = canonicalize_url(url)
    if not canonical:
        return True
    parsed = urlparse(canonical)
    path = (parsed.path or "/").lower().rstrip("/")
    if not path:
        path = "/"
    for pattern in LISTING_PATH_PATTERNS:
        if re.match(pattern, path, re.IGNORECASE):
            return True
    return False


def looks_like_article_url(url: str) -> bool:
    canonical = canonicalize_url(url)
    if not canonical:
        return False
    parsed = urlparse(canonical)
    path = (parsed.path or "").lower()
    if not path:
        return False
    if re.search(r"/article/\d+/\d+", path):
        return True
    if re.search(r"/news-\d+.*\.html$", path):
        return True
    if re.search(r"/\d{8,}[-_a-z0-9]*\.html$", path):
        return True
    if path.endswith(".html"):
        return True
    return False


def looks_like_low_quality_article_text(text: str) -> bool:
    clean = normalize_spaces(text).lower()
    if not clean:
        return True

    words = re.findall(r"\w+", clean, flags=re.UNICODE)
    if len(words) < 30:
        return True

    punctuation_count = len(re.findall(r"[.!?]", clean))
    marker_hits = sum(1 for marker in LOW_QUALITY_TEXT_MARKERS if marker in clean)
    if marker_hits >= 2:
        return True
    if punctuation_count == 0 and len(clean) > 120:
        return True
    return False


def is_valid_news_entry(title: str, link: str) -> bool:
    if is_generic_news_title(title):
        return False
    if is_listing_like_url(link):
        return False
    if not looks_like_article_url(link):
        return False
    return True


def is_garbage_title(title: str) -> bool:
    normalized = normalize_title_for_fingerprint(title)
    if not normalized:
        return True
    for pattern in GARBAGE_TITLE_PATTERNS:
        if re.match(pattern, normalized, re.IGNORECASE):
            return True
    return False


INCOMPLETE_NEWS_PATTERNS = (
    # Анонс обещает конкретный факт, но оставляет сам факт за ссылкой.
    r"\bчитать\s+дальше\b",
    r"\bрассказал[аи]?\s*,?\s*кого\b",
    r"\bрассказал[аи]?\s*,?\s*что\s+именно\b",
    r"\bкого\s+из\s+одноклубник",
    r"\bкого\s+он\s+(?:хотел|мог|пригласил)",
    r"\bназвал[аи]?\s+(?:одного|двух|тр[её]х|четыр[её]х|пять|\d+)\s+(?:игрок|футболист)",
)


def is_incomplete_news_post(title: str, article_text: str, post_text: str) -> bool:
    """Отбрасывает тизеры, где обещана конкретика, но её нет в посте."""
    combined = normalize_spaces(strip_html(f"{title} {article_text} {post_text}")).lower()
    return any(re.search(pattern, combined, flags=re.IGNORECASE) for pattern in INCOMPLETE_NEWS_PATTERNS)


def is_post_without_facts(entry: Any, article_text: Optional[str]) -> bool:
    """True, если в посте нет ничего, кроме заголовка: «Коротко» повторяет его,
    а «Деталей» и «Почему важно» нет."""
    title = normalize_spaces(entry.get("title", ""))
    summary = make_rich_summary(entry.get("summary", ""), article_text or "")
    lead, details, insight = build_post_story(title, summary)
    if insight:
        return False
    if normalize_spaces(details).lower() != normalize_spaces(DETAILS_FALLBACK_TEXT).lower():
        return False
    return normalize_title_for_fingerprint(lead) == normalize_title_for_fingerprint(title)


def should_auto_delete_post(title: str, link: str, article_text: str, post_text: str) -> bool:
    if not AUTO_DELETE_GARBAGE_POSTS:
        return False
    if is_garbage_title(title):
        return True
    if is_incomplete_news_post(title, article_text, post_text):
        return True
    if not is_valid_news_entry(title, link):
        return True
    article_clean = normalize_spaces(article_text)
    if article_clean and len(article_clean) >= 80 and looks_like_low_quality_article_text(article_clean):
        return True
    normalized_post = normalize_spaces(strip_html(post_text)).lower()
    if len(normalized_post) < 140:
        return True
    return False


def normalize_title_for_fingerprint(title: str) -> str:
    title = normalize_spaces(title).lower()
    title = re.sub(r"[^\w\sа-яё-]", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def canonicalize_url(url: str) -> str:
    url = normalize_spaces(url)
    if not url:
        return ""

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url

    filtered_query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower.startswith("utm_") or key_lower in {"fbclid", "gclid", "yclid", "_openstat"}:
            continue
        filtered_query.append((key, value))

    clean_path = re.sub(r"/+$", "", parsed.path or "/") or "/"
    clean_query = urlencode(sorted(filtered_query))
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            clean_path,
            "",
            clean_query,
            "",
        )
    )


def normalize_rss_feed_url(url: str) -> str:
    normalized = normalize_spaces(url)
    if not normalized:
        return ""

    parsed = urlparse(normalized)
    if parsed.netloc.lower() != "github.com":
        return normalized

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 5 and parts[2].lower() == "blob":
        owner, repo = parts[0], parts[1]
        branch = parts[3]
        file_path = "/".join(parts[4:])
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"

    return normalized


def build_news_id(entry: Any) -> str:
    raw_id = normalize_spaces(str(entry.get("id") or entry.get("guid") or ""))
    link = canonicalize_url(entry.get("link", ""))
    title = normalize_title_for_fingerprint(entry.get("title", ""))
    base = "||".join(part for part in [raw_id, link, title] if part)

    if not base:
        base = normalize_spaces(str(entry))

    return hash_text(base)


def build_fingerprint(title: str, source_name: str = "", link: str = "") -> str:
    base = f"{normalize_title_for_fingerprint(title)}|{source_name.lower()}|{canonicalize_url(link)}"
    return hash_text(base)


def build_title_key(title: str) -> str:
    normalized = normalize_title_for_fingerprint(title)
    normalized = re.sub(r"\b(?:live|онлайн|обновляется)\b", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return hash_text(normalized)


TITLE_DEDUP_STOPWORDS = {
    "и", "в", "во", "на", "по", "из", "за", "для", "над", "после", "до",
    "не", "это", "как", "что", "кто", "его", "ее", "их", "у", "о", "об",
    "матч", "матче", "тура", "туре", "сезона", "сезоне", "чемпионата",
    "кубка", "лиги", "лиге", "футбольный", "футбольного", "новости",
}


def title_dedup_tokens(title: str) -> set[str]:
    normalized = normalize_title_for_fingerprint(title)
    tokens = set()
    for token in re.findall(r"[a-zа-яё0-9]+", normalized, flags=re.IGNORECASE):
        if len(token) < 4 or token in TITLE_DEDUP_STOPWORDS:
            continue
        # Убираем окончания слов: «Атлетиком» и «Атлетик» должны
        # считаться одной командой при сравнении заголовков.
        stem = token[:6] if len(token) >= 6 else token
        tokens.add(stem)
    return tokens


def is_similar_news_title(title: str, previous_titles: List[str]) -> bool:
    current = title_dedup_tokens(title)
    if len(current) < 2:
        return False

    for previous_title in previous_titles:
        previous = title_dedup_tokens(previous_title)
        common = current & previous
        union = current | previous
        # Для коротких спортивных заголовков двух совпавших сущностей
        # (например, названий команд) достаточно, если пересечение заметное.
        if len(common) >= 2 and len(common) / max(1, len(union)) >= 0.30:
            return True
    return False


def build_link_key(url: str) -> str:
    canonical = canonicalize_url(url)
    if not canonical:
        return ""

    parsed = urlparse(canonical)
    numeric_tokens = re.findall(r"\d{8,}", parsed.path or "")
    if numeric_tokens:
        article_id = max(numeric_tokens, key=len)
        return f"{parsed.netloc}|{article_id}"
    return canonical


def is_liveresult_source(source_name: str) -> bool:
    normalized = normalize_spaces(source_name).lower()
    return normalized in {"liveresult", "rss.app"}


def parse_entry_datetime(entry: Any) -> Optional[datetime]:
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
            except Exception:
                continue

    for field in ("published", "updated", "created", "pubDate"):
        raw_value = normalize_spaces(str(entry.get(field, "")))
        if not raw_value:
            continue
        try:
            dt = parsedate_to_datetime(raw_value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue

    return None


def is_entry_too_old(entry: Any, source_name: str, now_utc: datetime) -> bool:
    published_dt = parse_entry_datetime(entry)
    if not published_dt:
        return False

    max_age_hours = LIVERESULT_MAX_AGE_HOURS if is_liveresult_source(source_name) else GENERAL_NEWS_MAX_AGE_HOURS
    return now_utc - published_dt > timedelta(hours=max_age_hours)


def is_entry_from_today(entry: Any, target_date, day_tz) -> bool:
    published_dt = parse_entry_datetime(entry)
    if not published_dt:
        return False
    return published_dt.astimezone(day_tz).date() == target_date


def extract_relative_match_time(text: str, now_local: datetime) -> Optional[datetime]:
    match = re.search(r"\b(сегодня|завтра)\s*(?:в)?\s*(\d{1,2})[:.](\d{2})\b", text, re.IGNORECASE)
    if not match:
        return None

    word, hours, minutes = match.groups()
    hour_int = int(hours)
    minute_int = int(minutes)
    if hour_int > 23 or minute_int > 59:
        return None

    day_offset = 1 if word.lower() == "завтра" else 0
    return now_local.replace(hour=hour_int, minute=minute_int, second=0, microsecond=0) + timedelta(days=day_offset)


def is_past_schedule_news(entry: Any, source_name: str, now_local: datetime) -> bool:
    if not is_liveresult_source(source_name):
        return False

    title = entry.get("title", "")
    summary = strip_html(entry.get("summary", ""))
    combined = normalize_spaces(f"{title} {summary}".lower())

    if "сегодня" not in combined and "завтра" not in combined:
        return False

    scheduled_dt = extract_relative_match_time(combined, now_local)
    if not scheduled_dt:
        return False

    return scheduled_dt + timedelta(minutes=SCHEDULE_POST_GRACE_MINUTES) < now_local


# =========================================================
# ТЕМАТИКА И ПОСТ
# =========================================================
def choose_topic_emoji(title: str, summary: str, content: str) -> str:
    text = f"{title} {summary} {content}".lower()

    if any(word in text for word in ["гол", "забил", "хет-трик", "hat-trick", "goal", "scored"]):
        return "🥅"
    if any(word in text for word in ["трансфер", "подписал", "контракт", "transfer", "deal", "sign"]):
        return "💰"
    if any(word in text for word in ["травм", "поврежден", "injury", "injured", "out"]):
        return "🤕"
    if any(word in text for word in ["лига чемпионов", "champions league", "uefa"]):
        return "🏆"
    if any(word in text for word in ["тренер", "coach", "manager", "уволен", "sacked"]):
        return "🧠"
    if any(word in text for word in ["карабах", "qarabag", "азербайджан", "neftchi", "нефтчи"]):
        return "🇦🇿"
    if any(word in text for word in ["реал", "барселона", "манчестер сити", "arsenal", "real madrid"]):
        return "⭐"
    return "📢"


def build_hashtags(title: str, text: str) -> str:
    combined = f"{title} {text}".lower()
    tags = []

    for key, tag in TAG_MAPPING:
        pattern = rf"(?<!\w){re.escape(key.lower())}(?!\w)"
        if re.search(pattern, combined, re.IGNORECASE) and tag not in tags:
            tags.append(tag)

    for tag in BASE_HASHTAGS:
        if tag not in tags:
            tags.append(tag)

    return " ".join(tags[:MAX_HASHTAGS])


def take_best_sentences(text: str, max_sentences: int = 4, max_len: int = 650) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return truncate_smart(text, max_len)

    preferred = []
    total = 0

    for sentence in sentences:
        sentence = normalize_spaces(sentence)
        if len(sentence) < 40:
            continue
        if re.search(r"(подписывайтесь|читайте также|реклама|источник)", sentence, re.IGNORECASE):
            continue
        if total + len(sentence) + 1 > max_len:
            break
        preferred.append(sentence)
        total += len(sentence) + 1
        if len(preferred) >= max_sentences:
            break

    if not preferred:
        return truncate_smart(text, max_len)

    return " ".join(preferred)


def make_rich_summary(rss_summary: str, article_text: str) -> str:
    rss_clean = strip_html(rss_summary)
    article_clean = normalize_spaces(article_text or "")

    if article_clean and len(article_clean) >= MIN_ARTICLE_TEXT_LEN:
        summary = take_best_sentences(article_clean, max_sentences=6, max_len=MAX_SUMMARY_LEN)
    else:
        summary = take_best_sentences(rss_clean, max_sentences=5, max_len=MAX_SUMMARY_LEN)

    return truncate_smart(summary, MAX_SUMMARY_LEN)


def sanitize_post_sentence(text: str, title: str) -> str:
    clean = normalize_spaces(text)
    if not clean:
        return ""

    # Убираем префиксы вида "25 марта 2026 11:04" / "25.03.2026 11:04" / "11:04".
    clean = re.sub(r"^\d{1,2}\s+[а-яё]+\s+\d{4}\s+\d{1,2}[:.]\d{2}\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s+\d{1,2}[:.]\d{2}\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^\d{1,2}[:.]\d{2}\s*", "", clean, flags=re.IGNORECASE)
    clean = clean.strip(" -–—:;,.")

    title_norm = normalize_title_for_fingerprint(title)
    clean_norm = normalize_title_for_fingerprint(clean)
    if title_norm and (clean_norm == title_norm or clean_norm.startswith(f"{title_norm} ")):
        return ""

    return clean


def build_safe_fallback_story(title: str, rss_summary: str) -> Tuple[str, str, str]:
    summary_clean = strip_html(rss_summary)
    for sentence in split_sentences(summary_clean):
        candidate = sanitize_post_sentence(sentence, title)
        if len(candidate) >= 35:
            return truncate_smart(candidate, 240), DETAILS_FALLBACK_TEXT, ""
    return truncate_smart(normalize_spaces(title), 240), DETAILS_FALLBACK_TEXT, ""


def build_post_story(title: str, summary: str) -> Tuple[str, str, str]:
    def sentence_key(text: str) -> str:
        normalized = normalize_spaces(text).lower()
        normalized = re.sub(r"[^\w\sа-яё-]", " ", normalized, flags=re.IGNORECASE)
        return normalize_spaces(normalized)

    raw_sentences = split_sentences(summary)
    sentences: List[str] = []
    seen_keys = set()
    for sentence in raw_sentences:
        cleaned_sentence = sanitize_post_sentence(sentence, title)
        if sentences and is_sentence_fragment(cleaned_sentence):
            # Не выносим придаточное предложение в отдельные «Детали».
            sentences[-1] = normalize_spaces(f"{sentences[-1]} {cleaned_sentence}")
            continue
        key = sentence_key(cleaned_sentence)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        sentences.append(cleaned_sentence)

    if not sentences:
        return build_safe_fallback_story(title, summary)

    # Распределяем предложения: первое в Коротко, следующие в Детали
    # Сначала сохраняем целое предложение. Сокращение допускается только
    # на позднем этапе, если весь пост действительно не помещается.
    lead = truncate_smart(sentences[0], 520)

    details_source = " ".join(sentences[1:4]) if len(sentences) > 1 else ""
    if not details_source:
        # Не режем одно предложение по запятым: так придаточные вроде
        # «где ...» ошибочно превращались в отдельный блок «Детали».
        clauses = [normalize_spaces(part) for part in re.split(r"[;:]\s+", sentences[0]) if normalize_spaces(part)]
        if len(clauses) >= 3:
            candidate_details = " ".join(clauses[2:])
            if not is_sentence_fragment(candidate_details):
                lead = truncate_smart(" ".join(clauses[:2]), 520)
                details_source = candidate_details
        elif len(clauses) == 2:
            if not is_sentence_fragment(clauses[1]):
                lead = truncate_smart(clauses[0], 520)
                details_source = clauses[1]
        elif len(sentences[0]) > 420:
            # Для очень длинной единственной фразы переносим хвост в Детали.
            lead_cut = sentences[0][:240]
            if " " in lead_cut:
                lead_cut = lead_cut.rsplit(" ", 1)[0]
            lead = lead_cut + "..."
            details_source = normalize_spaces(sentences[0][len(lead_cut):])

    if not details_source:
        details_source = DETAILS_FALLBACK_TEXT
    details = truncate_smart(details_source, 420)
    if sentence_key(details) == sentence_key(lead):
        details = DETAILS_FALLBACK_TEXT
    if len(sentence_key(lead)) < 20:
        return build_safe_fallback_story(title, summary)

    insight = ""
    if len(sentences) >= 4:
        insight = truncate_smart(sentences[3], 280)
    elif len(sentences) >= 3:
        insight = truncate_smart(sentences[2], 280)

    insight_key = sentence_key(insight)
    details_key = sentence_key(details)
    if insight_key in {sentence_key(lead), details_key} or (insight_key and insight_key in details_key):
        insight = ""

    return lead, details, insight


def format_post(
    entry: Any,
    source_name: str,
    source_emoji: str,
    article_text: Optional[str] = None
) -> str:
    raw_title = normalize_spaces(entry.get("title", "Без заголовка"))
    raw_summary = entry.get("summary", "")
    link = entry.get("link", "")

    summary = make_rich_summary(raw_summary, article_text or "")
    lead, details, insight = build_post_story(raw_title, summary)
    if len(normalize_spaces(lead)) < 35:
        lead, details, insight = build_safe_fallback_story(raw_title, raw_summary)
    has_real_details = normalize_spaces(details).lower() != normalize_spaces(DETAILS_FALLBACK_TEXT).lower()
    intro = random.choice(INTRO_TEMPLATES)
    topic_emoji = choose_topic_emoji(raw_title, raw_summary, article_text or "")
    hashtags = build_hashtags(raw_title, f"{raw_summary} {article_text or ''}")
    parts = [
        f"{source_emoji} {topic_emoji} <b>{html_escape(raw_title)}</b>",
        "",
        f"<i>{html_escape(intro)}</i>",
        "",
        "⚡ <b>Коротко:</b>",
        html_escape(lead),
    ]

    if has_real_details:
        parts.extend(["", "🧩 <b>Детали:</b>", html_escape(details)])

    if insight:
        parts.extend(["", "💡 <b>Почему важно:</b>", html_escape(insight)])

    parts.extend([
        "",
        "━━━━━━━━━━━━━━━━",
        "",
        f"📌 Источник: <b>{html_escape(source_name)}</b>",
        f"🔗 <a href=\"{html_escape(link)}\">Читать полностью</a>"
    ])

    hashtag_line = html_escape(hashtags) if hashtags else ""
    if hashtags:
        parts.extend(["", hashtag_line])

    text = "\n".join(parts)

    # Сохраняем структуру поста: сначала убираем менее важные блоки, потом сокращаем детали.
    while len(text) > MAX_POST_LENGTH and hashtags:
        hashtags = ""
        parts = [line for line in parts if line != hashtag_line]
        text = "\n".join(parts)

    if len(text) > MAX_POST_LENGTH and insight:
        insight = ""
        parts = [
            f"{source_emoji} {topic_emoji} <b>{html_escape(raw_title)}</b>",
            "",
            f"<i>{html_escape(intro)}</i>",
            "",
            "⚡ <b>Коротко:</b>",
            html_escape(lead),
            "",
            "━━━━━━━━━━━━━━━━",
            "",
            f"📌 Источник: <b>{html_escape(source_name)}</b>",
            f"🔗 <a href=\"{html_escape(link)}\">Читать полностью</a>"
        ]
        if has_real_details:
            parts[6:6] = ["", "🧩 <b>Детали:</b>", html_escape(details)]
        if hashtags:
            parts.extend(["", html_escape(hashtags)])
        text = "\n".join(parts)

    if len(text) > MAX_POST_LENGTH:
        details = truncate_smart(details, 900)
        parts = [
            f"{source_emoji} {topic_emoji} <b>{html_escape(raw_title)}</b>",
            "",
            f"<i>{html_escape(intro)}</i>",
            "",
            "⚡ <b>Коротко:</b>",
            html_escape(lead),
            "",
            "━━━━━━━━━━━━━━━━",
            "",
            f"📌 Источник: <b>{html_escape(source_name)}</b>",
            f"🔗 <a href=\"{html_escape(link)}\">Читать полностью</a>"
        ]
        if has_real_details:
            parts[6:6] = ["", "🧩 <b>Детали:</b>", html_escape(details)]
        if hashtags:
            parts.extend(["", html_escape(hashtags)])
        text = "\n".join(parts)

    if len(text) > MAX_POST_LENGTH:
        lead = truncate_smart(lead, 700)
        parts = [
            f"{source_emoji} {topic_emoji} <b>{html_escape(raw_title)}</b>",
            "",
            f"<i>{html_escape(intro)}</i>",
            "",
            "⚡ <b>Коротко:</b>",
            html_escape(lead),
            "",
            "━━━━━━━━━━━━━━━━",
            "",
            f"📌 Источник: <b>{html_escape(source_name)}</b>",
            f"🔗 <a href=\"{html_escape(link)}\">Читать полностью</a>"
        ]
        if has_real_details:
            parts[6:6] = ["", "🧩 <b>Детали:</b>", html_escape(details)]
        text = "\n".join(parts)

    if len(text) > MAX_POST_LENGTH:
        text = truncate_smart(text, MAX_POST_LENGTH)
    
    return text


# =========================================================
# КАРТИНКИ ИЗ RSS
# =========================================================
def extract_image_from_entry(entry: Any) -> Optional[str]:
    media_content = entry.get("media_content")
    if media_content and isinstance(media_content, list):
        for item in media_content:
            url = item.get("url")
            if url:
                return url

    media_thumbnail = entry.get("media_thumbnail")
    if media_thumbnail and isinstance(media_thumbnail, list):
        for item in media_thumbnail:
            url = item.get("url")
            if url:
                return url

    enclosures = entry.get("enclosures")
    if enclosures and isinstance(enclosures, list):
        for item in enclosures:
            href = item.get("href")
            item_type = (item.get("type") or "").lower()
            if href and "image" in item_type:
                return href

    links = entry.get("links", [])
    for link in links:
        href = link.get("href")
        item_type = (link.get("type") or "").lower()
        if href and "image" in item_type:
            return href

    summary = entry.get("summary", "")
    if summary:
        soup = BeautifulSoup(summary, "html.parser")
        img = soup.find("img")
        if img and img.get("src"):
            return img["src"]

    return None


# =========================================================
# ЗАГРУЗКА И ПАРСИНГ СТАТЬИ
# =========================================================
def fetch_page(url: str) -> Optional[str]:
    if not url:
        return None

    try:
        response = requests.get(url, headers=get_headers(), timeout=REQUEST_TIMEOUT)
        if response.ok and response.text:
            return response.text
        logging.warning(f"Не удалось открыть статью: {url} | {response.status_code}")
    except Exception as e:
        logging.warning(f"Ошибка загрузки статьи {url}: {e}")

    return None


def extract_meta_image(soup: BeautifulSoup, page_url: str) -> Optional[str]:
    meta_candidates = [
        ("meta", {"property": "og:image"}, "content"),
        ("meta", {"name": "og:image"}, "content"),
        ("meta", {"property": "twitter:image"}, "content"),
        ("meta", {"name": "twitter:image"}, "content"),
    ]

    for tag_name, attrs, attr_key in meta_candidates:
        tag = soup.find(tag_name, attrs=attrs)
        if tag and tag.get(attr_key):
            return urljoin(page_url, tag.get(attr_key))

    return None


def extract_article_image_from_html(page_html: str, page_url: str) -> Optional[str]:
    soup = BeautifulSoup(page_html, "html.parser")

    meta_img = extract_meta_image(soup, page_url)
    if meta_img:
        return meta_img

    selectors = [
        "article img",
        ".article img",
        ".article__content img",
        ".news-item img",
        ".content img",
        ".story img",
        ".post img",
        ".entry-content img",
        "main img"
    ]

    for selector in selectors:
        img = soup.select_one(selector)
        if img:
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            if src:
                return urljoin(page_url, src)

    return None


def extract_text_by_selectors(soup: BeautifulSoup, selectors: List[str]) -> str:
    chunks = []

    for selector in selectors:
        nodes = soup.select(selector)
        if not nodes:
            continue

        for node in nodes:
            text = normalize_spaces(node.get_text(" ", strip=True))
            if len(text) >= 100:
                chunks.append(text)

        if chunks:
            break

    return "\n".join(chunks)


def extract_article_text(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")

    for tag in soup(["script", "style", "noscript", "iframe", "form", "svg", "header", "footer"]):
        tag.decompose()

    selectors_priority = [
        ["article"],
        [".article", ".article__content", ".article-content", ".content", ".entry-content", ".post-content"],
        [".news-item", ".news-item__content", ".story", ".story__content", ".content__article"],
        ["main"]
    ]

    article_text = ""
    for selectors in selectors_priority:
        article_text = extract_text_by_selectors(soup, selectors)
        if len(article_text) >= 260:
            break

    if len(article_text) < 260:
        paragraphs = []
        for p in soup.find_all("p"):
            txt = normalize_spaces(p.get_text(" ", strip=True))
            if len(txt) >= 65:
                paragraphs.append(txt)
        article_text = "\n".join(paragraphs)

    article_text = remove_noise_lines(article_text)
    article_text = normalize_spaces(article_text)
    article_text = truncate_smart(article_text, MAX_ARTICLE_TEXT_LEN)

    return article_text


def get_full_article_content(link: str) -> Dict[str, Optional[str]]:
    result = {
        "text": None,
        "image": None
    }

    page_html = fetch_page(link)
    if not page_html:
        return result

    text = extract_article_text(page_html)
    image = extract_article_image_from_html(page_html, link)

    if text:
        result["text"] = text
    if image:
        result["image"] = image

    return result


def parse_espn_event_datetime(raw_date: str) -> Optional[datetime]:
    if not raw_date:
        return None
    try:
        dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        return dt.astimezone(MSK_TZ)
    except Exception:
        return None


def fetch_league_matches_for_date(league_code: str, target_date: datetime.date) -> Tuple[str, List[Dict[str, str]]]:
    url = ESPN_SCOREBOARD_URL_TEMPLATE.format(league_code=league_code)
    params = {"dates": target_date.strftime("%Y%m%d")}
    response = requests.get(url, params=params, headers=get_headers(), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()

    leagues = data.get("leagues", [])
    league_name = leagues[0].get("name") if leagues else league_code
    events = data.get("events", [])
    matches: List[Dict[str, str]] = []

    for event in events:
        comp = (event.get("competitions") or [{}])[0]
        competitors = comp.get("competitors") or []
        home = ""
        away = ""

        for team_info in competitors:
            team_name = ((team_info.get("team") or {}).get("displayName") or "").strip()
            if not team_name:
                continue
            if team_info.get("homeAway") == "home":
                home = team_name
            elif team_info.get("homeAway") == "away":
                away = team_name

        if not home or not away:
            continue

        kickoff_msk = parse_espn_event_datetime(event.get("date", ""))
        kickoff_str = kickoff_msk.strftime("%H:%M") if kickoff_msk else "??:??"
        status = ((event.get("status") or {}).get("type") or {}).get("shortDetail") or "Scheduled"

        matches.append(
            {
                "kickoff": kickoff_str,
                "home": home,
                "away": away,
                "status": status,
            }
        )

    matches.sort(key=lambda x: x["kickoff"])
    return league_name, matches


def fetch_soccer365_matches_for_date(competition_id: int, target_date: datetime.date) -> List[Dict[str, str]]:
    url = SOCCER365_GAMES_DATA_URL.format(competition_id=competition_id)
    headers = get_headers()
    headers["X-Requested-With"] = "XMLHttpRequest"
    html_data = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT).text
    soup = BeautifulSoup(html_data, "html.parser")

    matches: List[Dict[str, str]] = []
    for game in soup.select("div.game_block"):
        status_span = game.select_one("div.status span")
        if not status_span:
            continue
        status_text = normalize_spaces(status_span.get_text(" ", strip=True))
        dt_match = re.search(r"(\d{1,2})\.(\d{1,2}),\s*(\d{1,2}):(\d{2})", status_text)
        if not dt_match:
            continue

        day, month, hour, minute = map(int, dt_match.groups())
        if day != target_date.day or month != target_date.month:
            continue

        # soccer365: ht = home team, at = away team
        home_node = game.select_one("div.result div.ht div.name span")
        away_node = game.select_one("div.result div.at div.name span")
        home = normalize_spaces(home_node.get_text(" ", strip=True)) if home_node else ""
        away = normalize_spaces(away_node.get_text(" ", strip=True)) if away_node else ""
        if not home or not away:
            continue

        kickoff_str = f"{hour:02d}:{minute:02d}"
        matches.append(
            {
                "kickoff": kickoff_str,
                "home": home,
                "away": away,
                "status": "Scheduled",
            }
        )

    matches.sort(key=lambda x: x["kickoff"])
    return matches


def fetch_soccer365_online_matches_today(target_date: datetime.date) -> Dict[int, List[Dict[str, str]]]:
    headers = get_headers()
    html_data = requests.get(SOCCER365_ONLINE_URL, headers=headers, timeout=REQUEST_TIMEOUT).text
    soup = BeautifulSoup(html_data, "html.parser")

    by_competition: Dict[int, List[Dict[str, str]]] = {}
    for block in soup.select("div.live_comptt_bd[id^='cmp']"):
        block_id = block.get("id", "")
        m = re.search(r"cmp(\d+)", block_id)
        if not m:
            continue
        competition_id = int(m.group(1))
        matches: List[Dict[str, str]] = []

        for game in block.select("div.game_block"):
            status_span = game.select_one("div.status span")
            if not status_span:
                continue
            status_text = normalize_spaces(status_span.get_text(" ", strip=True))
            # On /online page soccer365 may include upcoming games after midnight
            # formatted with date (e.g. "23.03, 00:45"). Keep only target day.
            datetime_match = re.search(r"(\d{1,2})\.(\d{1,2})(?:\.\d{2,4})?,\s*(\d{1,2}):(\d{2})", status_text)
            if datetime_match:
                day, month, hour, minute = map(int, datetime_match.groups())
                if day != target_date.day or month != target_date.month:
                    continue
            else:
                time_match = re.search(r"(\d{1,2}):(\d{2})", status_text)
                if not time_match:
                    continue
                hour, minute = map(int, time_match.groups())
            kickoff_str = f"{hour:02d}:{minute:02d}"

            home_node = game.select_one("div.result div.ht div.name")
            away_node = game.select_one("div.result div.at div.name")
            home = normalize_spaces(home_node.get_text(" ", strip=True)) if home_node else ""
            away = normalize_spaces(away_node.get_text(" ", strip=True)) if away_node else ""
            if not home or not away:
                continue

            matches.append(
                {
                    "kickoff": kickoff_str,
                    "home": home,
                    "away": away,
                    "status": "Scheduled",
                }
            )

        if matches:
            matches.sort(key=lambda x: x["kickoff"])
            by_competition[competition_id] = matches

    return by_competition


def build_daily_schedule_post(target_date: datetime.date) -> str:
    header = f"\U0001F5D3 <b>\u041C\u0430\u0442\u0447\u0438 \u043D\u0430 {target_date.strftime('%d.%m.%Y')}</b> (\u041C\u0421\u041A)\n"
    parts = [header]
    total_matches = 0

    for league in TRACKED_MATCH_LEAGUES:
        display_title = LEAGUE_TITLE_OVERRIDES_BY_CODE.get(league["code"]) or repair_mojibake(league["title"])
        try:
            _, matches = fetch_league_matches_for_date(league["code"], target_date)
        except Exception as e:
            logging.warning(f"Не удалось получить расписание {display_title}: {e}")
            continue

        if not matches:
            continue

        total_matches += len(matches)
        parts.append(f"\n<b>{html_escape(display_title)}</b>")
        for match in matches:
            status_text = match["status"]
            status_suffix = ""
            if status_text and "Scheduled" not in status_text:
                status_suffix = f" ({html_escape(status_text)})"
            home_name = localize_team_name(match["home"])
            away_name = localize_team_name(match["away"])
            parts.append(
                f"• {match['kickoff']} — {html_escape(home_name)} — {html_escape(away_name)}{status_suffix}"
            )

    today_msk = datetime.now(MSK_TZ).date()
    online_today_matches: Dict[int, List[Dict[str, str]]] = {}
    if target_date == today_msk:
        try:
            online_today_matches = fetch_soccer365_online_matches_today(target_date)
        except Exception as e:
            logging.warning(f"Не удалось получить online-расписание soccer365: {e}")

    for competition in TRACKED_SOCCER365_COMPETITIONS:
        competition_id = int(competition["competition_id"])
        flag = competition.get("flag", "").strip()
        title = repair_mojibake(competition["title"])
        try:
            if target_date == today_msk and competition_id in online_today_matches:
                matches = online_today_matches.get(competition_id, [])
            else:
                matches = fetch_soccer365_matches_for_date(competition_id, target_date)
        except Exception as e:
            logging.warning(f"Не удалось получить расписание {title}: {e}")
            continue

        if not matches:
            continue

        total_matches += len(matches)
        title_with_flag = f"{flag} {title}".strip()
        parts.append(f"\n<b>{html_escape(title_with_flag)}</b>")
        for match in matches:
            status_text = match["status"]
            status_suffix = ""
            if status_text and status_text not in {"NS", "TBD", "Scheduled"}:
                status_suffix = f" ({html_escape(status_text)})"
            home_name = localize_team_name(match["home"])
            away_name = localize_team_name(match["away"])
            parts.append(
                f"• {match['kickoff']} — {html_escape(home_name)} — {html_escape(away_name)}{status_suffix}"
            )

    if total_matches == 0:
        parts.append("\nСегодня в выбранных лигах матчей не найдено.")

    parts.append(f"\n\U0001F4CA \u0412\u0441\u0435\u0433\u043E \u043C\u0430\u0442\u0447\u0435\u0439: <b>{total_matches}</b>")
    message = "\n".join(parts)

    if len(message) > 4000:
        message = truncate_smart(message, 3950)
    return message


def maybe_publish_daily_schedule(now_msk: datetime) -> None:
    if now_msk.hour != DAILY_SCHEDULE_HOUR_MSK:
        return
    if now_msk.minute >= DAILY_SCHEDULE_WINDOW_MINUTES:
        return

    today_key = now_msk.date().isoformat()
    posted_data = load_posted()
    posted_dates = set(posted_data.get("daily_schedule_dates", []))

    if today_key in posted_dates:
        return

    post_text = build_daily_schedule_post(now_msk.date())
    message_id = send_text_to_telegram_with_message_id(post_text)
    if not message_id:
        logging.error("Не удалось отправить ежедневное расписание матчей.")
        return

    previous_pinned_message_id = posted_data.get("daily_schedule_pinned_message_id")
    if isinstance(previous_pinned_message_id, int):
        if not unpin_channel_message(previous_pinned_message_id):
            if not unpin_current_channel_message():
                logging.warning(f"Не удалось открепить прошлый пост расписания: {previous_pinned_message_id}")

    if pin_channel_message(message_id):
        posted_data["daily_schedule_pinned_message_id"] = message_id
    else:
        posted_data["daily_schedule_pinned_message_id"] = None
        logging.warning(f"Не удалось закрепить новый пост расписания: {message_id}")

    posted_dates.add(today_key)
    posted_data["daily_schedule_dates"] = list(posted_dates)
    save_posted(posted_data)
    logging.info("Ежедневное расписание матчей опубликовано.")


def schedule_loop() -> None:
    """Независимо проверяет утреннее расписание, не дожидаясь новостей."""
    while True:
        try:
            maybe_publish_daily_schedule(datetime.now(MSK_TZ))
        except Exception as e:
            logging.error(f"Ошибка цикла ежедневного расписания: {e}")
        time.sleep(SCHEDULE_POLL_SECONDS)


# =========================================================
# RSS
# =========================================================
def fetch_news() -> List[Dict[str, Any]]:
    news_list = []
    seen_cycle_keys = set()
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now().astimezone()

    for feed_info in RSS_FEEDS:
        logging.info(f"Читаю источник: {feed_info['name']}")
        try:
            # Загружаем RSS через requests с заголовками
            headers = get_headers()
            feed_url = normalize_rss_feed_url(feed_info["url"])
            response = requests.get(feed_url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # Парсим полученный контент
            feed = feedparser.parse(response.content)

            if getattr(feed, "bozo", False):
                logging.warning(f"RSS может быть проблемным: {feed_info['name']}")

            entries = feed.entries[:CHECK_LIMIT_PER_FEED]

            for entry in entries:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")

                if not is_valid_news_entry(title, link):
                    logging.info(f"Пропускаю не-новостной элемент: {title[:80]}")
                    continue

                if not is_relevant_news(title, summary):
                    continue

                if is_entry_too_old(entry, feed_info["name"], now_utc):
                    logging.info(f"Пропускаю старую новость: {title[:80]}")
                    continue

                if is_past_schedule_news(entry, feed_info["name"], now_local):
                    logging.info(f"Пропускаю устаревший анонс матча: {title[:80]}")
                    continue

                news_id = build_news_id(entry)
                canonical_link = canonicalize_url(link)
                fingerprint = build_fingerprint(title, feed_info["name"], link)
                cycle_key = f"{news_id}|{fingerprint}|{canonical_link}"

                if cycle_key in seen_cycle_keys:
                    continue
                seen_cycle_keys.add(cycle_key)

                news_list.append({
                    "id": news_id,
                    "fingerprint": fingerprint,
                    "canonical_link": canonical_link,
                    "published_ts": parse_entry_datetime(entry),
                    "entry": entry,
                    "source_name": feed_info["name"],
                    "source_emoji": feed_info["emoji"],
                    "image": extract_image_from_entry(entry)
                })

        except Exception as e:
            logging.error(f"Ошибка чтения RSS {feed_info['name']}: {e}")

    news_list.sort(
        key=lambda item: item.get("published_ts") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )
    return news_list


# =========================================================
# ПУБЛИКАЦИЯ
# =========================================================
def publish_news() -> None:
    posted_data = load_posted()
    posted_ids = set(posted_data.get("ids", []))
    posted_fingerprints = set(posted_data.get("fingerprints", []))
    posted_links = set(posted_data.get("links", []))
    posted_title_keys = set(posted_data.get("title_keys", []))
    posted_link_keys = set(posted_data.get("link_keys", []))
    posted_titles = list(posted_data.get("titles", []))
    channel_titles = fetch_recent_channel_titles()

    news_items = fetch_news()
    posts_goal = random.randint(MIN_POSTS_PER_CYCLE, MAX_POSTS_PER_CYCLE)
    logging.info(f"План публикаций на цикл: {posts_goal} поста(ов)")
    new_posts = 0

    for item in news_items:
        if new_posts >= posts_goal:
            break

        news_id = item["id"]
        fingerprint = item["fingerprint"]
        canonical_link = item.get("canonical_link", "")
        entry = item["entry"]
        title = entry.get("title", "")
        title_key = build_title_key(title)
        link_key = build_link_key(canonical_link)

        if news_id in posted_ids:
            continue
        if fingerprint in posted_fingerprints:
            continue
        if canonical_link and canonical_link in posted_links:
            continue
        if title_key in posted_title_keys:
            continue
        if link_key and link_key in posted_link_keys:
            continue
        if is_similar_news_title(title, posted_titles) or is_similar_news_title(title, channel_titles):
            logging.info(f"Пропускаю смысловой дубль: {title[:120]}")
            continue

        article_text = None
        article_image = None
        link = entry.get("link", "")

        if link:
            if not is_valid_news_entry(entry.get("title", ""), link):
                logging.info(f"Пропускаю элемент с витринной ссылкой: {entry.get('title', '')[:120]}")
                continue

            full_article = get_full_article_content(link)
            article_text = full_article.get("text")
            article_image = full_article.get("image")

            if not article_text:
                logging.info(f"Нет полного текста, использую RSS-анонс: {entry.get('title', '')[:120]}")
            elif looks_like_low_quality_article_text(article_text):
                logging.info(f"Полный текст шумный, использую RSS-анонс: {entry.get('title', '')[:120]}")
                article_text = None

            # Повторно фильтруем по полному тексту, чтобы не пропускать новости
            # по другим видам спорта, которые маскируются в RSS-анонсе.
            if article_text and not is_relevant_news(entry.get("title", ""), f"{entry.get('summary', '')} {article_text}"):
                logging.info(f"Пропускаю новость после проверки полной статьи (не футбол): {entry.get('title', '')[:120]}")
                continue

        if is_post_without_facts(entry, article_text):
            logging.info(f"Пропускаю пост без фактов (только заголовок): {title[:120]}")
            continue

        post_text = format_post(
            entry=entry,
            source_name=item["source_name"],
            source_emoji=item["source_emoji"],
            article_text=article_text
        )

        # Для LiveResult приоритет отдаем изображению из статьи, а не из RSS
        if is_liveresult_source(item["source_name"]):
            final_image = article_image or item["image"]
        else:
            final_image = item["image"] or article_image
        message_id: Optional[int] = None
        success = False

        if final_image:
            message_id = send_photo_to_telegram_with_message_id(final_image, post_text)
            success = message_id is not None
            if not success:
                logging.info("Фото не отправилось, пробую обычный текст")
                message_id = send_text_to_telegram_with_message_id(post_text)
                success = message_id is not None
        else:
            message_id = send_text_to_telegram_with_message_id(post_text)
            success = message_id is not None

        if success and should_auto_delete_post(
            entry.get("title", ""),
            link,
            article_text or "",
            post_text
        ):
            if message_id is not None and delete_channel_message(message_id):
                logging.warning(f"Авто-удалён мусорный пост: {entry.get('title', '')[:120]}")
            else:
                logging.error(f"Не удалось авто-удалить мусорный пост: {entry.get('title', '')[:120]}")
            continue

        if success:
            if message_id is not None:
                PUBLISHER_MESSAGE_IDS.add(str(message_id))
            posted_ids.add(news_id)
            posted_fingerprints.add(fingerprint)
            if canonical_link:
                posted_links.add(canonical_link)
            posted_title_keys.add(title_key)
            if link_key:
                posted_link_keys.add(link_key)
            posted_titles.append(title)

            posted_data["ids"] = list(posted_ids)
            posted_data["fingerprints"] = list(posted_fingerprints)
            posted_data["links"] = list(posted_links)
            posted_data["title_keys"] = list(posted_title_keys)
            posted_data["link_keys"] = list(posted_link_keys)
            posted_data["titles"] = posted_titles
            posted_data.setdefault("publisher_message_ids", []).append(str(message_id or ""))
            save_posted(posted_data)

            new_posts += 1
            logging.info(f"Опубликовано: {entry.get('title', 'Без названия')}")
            if new_posts < posts_goal:
                time.sleep(SLEEP_BETWEEN_POSTS)

    logging.info(f"Готово. Новых постов: {new_posts}")


# =========================================================
# ЗАПУСК
# =========================================================
web_app = Flask(__name__)


@web_app.get("/health")
def health_check():
    return jsonify({"status": "ok", "service": "football-news-bot"})


def publisher_loop() -> None:
    # После перезапуска Render не публикуем сразу: иначе каждый деплой
    # превращается в лишнюю новость с интервалом в несколько минут.
    if datetime.now(timezone.utc) < FORCE_FIRST_POST_BEFORE_UTC:
        initial_wait_seconds = 60
    else:
        initial_wait_seconds = random.randint(LOOP_MIN_SECONDS, LOOP_MAX_SECONDS)
    logging.info(
        f"Первый пост после запуска — через {initial_wait_seconds // 3600} ч. "
        f"{(initial_wait_seconds % 3600) // 60} мин."
    )
    time.sleep(initial_wait_seconds)

    while True:
        try:
            publish_news()
        except Exception as e:
            logging.error(f"Глобальная ошибка: {e}")

        wait_seconds = random.randint(LOOP_MIN_SECONDS, LOOP_MAX_SECONDS)
        logging.info(
            f"Жду {wait_seconds // 3600} ч. "
            f"{(wait_seconds % 3600) // 60} мин. до следующей публикации..."
        )
        time.sleep(wait_seconds)


if __name__ == "__main__":
    threading.Thread(target=moderator_loop, name="moderator", daemon=True).start()
    threading.Thread(target=schedule_loop, name="daily-schedule", daemon=True).start()
    threading.Thread(target=publisher_loop, name="publisher", daemon=True).start()
    port = int(os.getenv("PORT", "10000"))
    web_app.run(host="0.0.0.0", port=port)
