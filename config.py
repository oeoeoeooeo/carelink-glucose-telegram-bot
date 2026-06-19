"""集中管理設定，全部從 .env 讀取（含預設值）。"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _get(name, default=None):
    v = os.getenv(name)
    return v if v not in (None, "") else default


def _abspath(value, default_name):
    p = Path(value) if value else BASE_DIR / default_name
    return str(p if p.is_absolute() else BASE_DIR / p)


# --- Telegram ---
TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = _get("TELEGRAM_CHAT_ID", "")

# --- CareLink（網頁版 client1：用瀏覽器 cookie 的 token）---
CARELINK_TOKEN = _get("CARELINK_TOKEN", "")          # auth_tmp_token cookie 值
CARELINK_COUNTRY = _get("CARELINK_COUNTRY", "")      # application_country cookie 值（兩碼國碼）
# （舊版手機 API client2 用的 token 檔，已不採用，保留相容）
CARELINK_TOKEN_FILE = _abspath(_get("CARELINK_TOKEN_FILE"), "logindata.json")

# --- 血糖門檻 (mg/dL) ---
LOW_THRESHOLD = int(_get("LOW_THRESHOLD", "70"))
HIGH_THRESHOLD = int(_get("HIGH_THRESHOLD", "180"))

# --- 頻率 ---
POLL_INTERVAL_SEC = int(_get("POLL_INTERVAL_SEC", "300"))
SUMMARY_INTERVAL_HOURS = float(_get("SUMMARY_INTERVAL_HOURS", "3"))
DAY_START_HOUR = int(_get("DAY_START_HOUR", "7"))
DAY_END_HOUR = int(_get("DAY_END_HOUR", "23"))
REALERT_MINUTES = int(_get("REALERT_MINUTES", "30"))
STALE_MINUTES = int(_get("STALE_MINUTES", "30"))
CHART_HOURS = int(_get("CHART_HOURS", "12"))

# --- Google Sheets（選填）---
GOOGLE_SHEET_ID = _get("GOOGLE_SHEET_ID", "")
GOOGLE_SA_FILE = _abspath(_get("GOOGLE_SA_FILE"), "service_account.json")
