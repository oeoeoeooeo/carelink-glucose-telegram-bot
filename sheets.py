"""把每筆血糖寫進 Google Sheets（選填功能，沒設定就自動停用）。

這裡的函式都是同步阻塞的，從 async 端呼叫時請用 asyncio.to_thread 包起來。
"""
import logging
from datetime import datetime

import config

log = logging.getLogger(__name__)

_ws = None
_enabled = None  # None=還沒判斷, True/False=已判斷
HEADER = ["時間", "血糖 (mg/dL)", "趨勢", "單位"]


def _init():
    global _ws, _enabled
    if _enabled is not None:
        return _enabled
    if not config.GOOGLE_SHEET_ID:
        log.info("未設定 GOOGLE_SHEET_ID，Google Sheets 記錄停用。")
        _enabled = False
        return False
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(config.GOOGLE_SA_FILE, scopes=scopes)
        gc = gspread.authorize(creds)
        ws = gc.open_by_key(config.GOOGLE_SHEET_ID).sheet1
        if ws.row_count == 0 or not ws.acell("A1").value:
            ws.update("A1:D1", [HEADER])
        _ws = ws
        _enabled = True
        log.info("Google Sheets 記錄已啟用。")
    except Exception as e:
        log.warning("Google Sheets 初始化失敗，停用：%s", e)
        _enabled = False
    return _enabled


def log_reading(reading):
    if reading is None or not _init():
        return
    try:
        ts = reading.timestamp or datetime.now()
        _ws.append_row(
            [ts.strftime("%Y-%m-%d %H:%M:%S"), reading.sg, reading.trend, reading.units],
            value_input_option="USER_ENTERED",
        )
    except Exception as e:
        log.warning("寫入 Google Sheets 失敗：%s", e)
