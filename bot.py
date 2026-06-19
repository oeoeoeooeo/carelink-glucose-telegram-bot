"""CareLink 血糖通知 bot 主程式（網頁自動化版）。

資料來自 carelink_web.fetch_raw()（Playwright 開 headless Chrome、重用存好的登入狀態，
攔截 carelink.minimed.eu 的 connect/data）。

功能：
  • 每 POLL_INTERVAL_SEC 抓一次血糖，超出門檻即時警報、回到範圍報平安
  • 每 SUMMARY_INTERVAL_HOURS（白天時段）發一次摘要 + 趨勢圖
  • 每筆寫進 Google Sheets（選填）
  • 指令：/now /chart /status /id /dump /help

⚠️ 非官方工具，僅供輔助參考，不可取代 Medtronic 原廠 App 與裝置本身的警報。
"""
import asyncio
import io
import json
import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

import carelink_web
import config
import sheets
from chart import render_chart

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("carelink_bot")

async def fetch_data():
    """讀取常駐瀏覽器（keep 模式）寫好的最新原始資料 dict；沒有就回 None。"""
    return await asyncio.to_thread(carelink_web.read_dump)


class State:
    """記錄警報狀態，避免每 5 分鐘狂洗版。"""

    def __init__(self):
        self.condition = "in_range"   # in_range | low | high
        self.last_alert_at = None
        self.last_reading_ts = None
        self.stale_warned = False


state = State()


# ---------- 共用工具 ----------
def fmt_reading(r) -> str:
    flag = ""
    if r.sg < config.LOW_THRESHOLD:
        flag = "  ⚠️ 偏低"
    elif r.sg > config.HIGH_THRESHOLD:
        flag = "  ⚠️ 偏高"
    t = r.timestamp.strftime("%m/%d %H:%M") if r.timestamp else "時間未知"
    return f"*{r.sg}* mg/dL {r.arrow}{flag}\n🕒 {t}"


def build_summary(reading, hist) -> str:
    lines = ["📊 *血糖摘要*"]
    if reading:
        lines.append(fmt_reading(reading))
    if hist:
        ys = [s for _, s in hist]
        in_range = sum(1 for y in ys if config.LOW_THRESHOLD <= y <= config.HIGH_THRESHOLD)
        tir = round(100 * in_range / len(ys))
        lines.append(f"\n近 {config.CHART_HOURS} 小時（{len(ys)} 筆）")
        lines.append(f"• 範圍內：{tir}%")
        lines.append(f"• 平均：{round(sum(ys) / len(ys))} mg/dL")
        lines.append(f"• 最低 / 最高：{min(ys)} / {max(ys)}")
    else:
        lines.append("（沒有可用的歷史資料）")
    return "\n".join(lines)


def recent_history(raw):
    return carelink_web.history_points(raw, hours=config.CHART_HOURS)


async def push(context, text=None, photo=None, caption=None):
    """主動推播到設定好的群組。"""
    chat_id = config.TELEGRAM_CHAT_ID
    if not chat_id:
        log.warning("尚未設定 TELEGRAM_CHAT_ID，無法主動推播。")
        return
    if photo is not None:
        await context.bot.send_photo(chat_id, photo=photo, caption=caption,
                                     parse_mode=ParseMode.MARKDOWN)
    else:
        await context.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN)


# ---------- 定時工作 ----------
async def poll_job(context: ContextTypes.DEFAULT_TYPE):
    raw = await fetch_data()
    if not raw:
        log.warning("本次抓取失敗（可能 session 過期或網路問題）。")
        return
    reading = carelink_web.parse_current(raw)
    if reading is None:
        log.info("本次沒有有效血糖讀數。")
        return

    await asyncio.to_thread(sheets.log_reading, reading)

    now = datetime.now()
    state.last_reading_ts = reading.timestamp or now

    # 資料逾時（感測器/上傳中斷）
    if reading.timestamp:
        age = now - reading.timestamp
        if age > timedelta(minutes=config.STALE_MINUTES):
            if not state.stale_warned:
                await push(context,
                           f"⚠️ *資料逾時*\n最後一筆血糖在 {reading.timestamp.strftime('%m/%d %H:%M')}"
                           f"（已 {int(age.total_seconds() // 60)} 分鐘沒更新），可能上傳中斷或感測器離線。")
                state.stale_warned = True
            return
    state.stale_warned = False

    if reading.sg < config.LOW_THRESHOLD:
        cond = "low"
    elif reading.sg > config.HIGH_THRESHOLD:
        cond = "high"
    else:
        cond = "in_range"

    if cond != state.condition:
        if cond == "low":
            await push(context, f"🔴 *低血糖警報*\n{fmt_reading(reading)}")
            state.last_alert_at = now
        elif cond == "high":
            await push(context, f"🟠 *高血糖警報*\n{fmt_reading(reading)}")
            state.last_alert_at = now
        else:
            await push(context, f"✅ *血糖回到範圍*\n{fmt_reading(reading)}")
            state.last_alert_at = None
        state.condition = cond
    elif cond in ("low", "high") and state.last_alert_at and \
            (now - state.last_alert_at) >= timedelta(minutes=config.REALERT_MINUTES):
        label = "低血糖" if cond == "low" else "高血糖"
        emoji = "🔴" if cond == "low" else "🟠"
        await push(context, f"{emoji} *{label}持續中*\n{fmt_reading(reading)}")
        state.last_alert_at = now


async def summary_job(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    if not (config.DAY_START_HOUR <= now.hour < config.DAY_END_HOUR):
        return
    raw = await fetch_data()
    if not raw:
        log.warning("摘要抓取失敗。")
        return
    reading = carelink_web.parse_current(raw)
    hist = recent_history(raw)
    text = build_summary(reading, hist)
    png = render_chart(hist, title=f"近 {config.CHART_HOURS} 小時血糖")
    if png:
        await push(context, photo=png, caption=text)
    else:
        await push(context, text=text)


# ---------- 指令 ----------
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "CareLink 血糖通知 bot 指令：\n"
        "/now － 目前血糖\n"
        "/chart － 趨勢圖\n"
        "/status － bot 狀態\n"
        "/id － 取得這個聊天的 chat_id\n"
        "/dump － 匯出原始資料（除錯用）\n\n"
        "⚠️ 本工具為非官方輔助，數據可能延遲或失準，請以原廠 App 與裝置警報為準。"
    )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"這個聊天的 chat_id：{update.effective_chat.id}\n把它填進 .env 的 TELEGRAM_CHAT_ID。"
    )


async def cmd_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("查詢中…")
    raw = await fetch_data()
    reading = carelink_web.parse_current(raw) if raw else None
    if reading is None:
        await update.message.reply_text("目前抓不到有效血糖讀數（可能 session 過期，需重跑登入）。")
        return
    await update.message.reply_text(fmt_reading(reading), parse_mode=ParseMode.MARKDOWN)


async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("產生趨勢圖中…")
    raw = await fetch_data()
    if not raw:
        await update.message.reply_text("抓資料失敗。")
        return
    reading = carelink_web.parse_current(raw)
    hist = recent_history(raw)
    png = render_chart(hist, title=f"近 {config.CHART_HOURS} 小時血糖")
    if png:
        await update.message.reply_photo(photo=png, caption=build_summary(reading, hist),
                                         parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("目前沒有足夠資料可以畫圖。")


_COND_LABEL = {"in_range": "範圍內", "low": "偏低", "high": "偏高"}


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last = state.last_reading_ts.strftime("%m/%d %H:%M") if state.last_reading_ts else "尚未抓到"
    cond = _COND_LABEL.get(state.condition, state.condition)
    txt = (
        "🤖 CareLink Bot 狀態\n"
        f"• 門檻：低 < {config.LOW_THRESHOLD} / 高 > {config.HIGH_THRESHOLD} mg/dL\n"
        f"• 輪詢：每 {config.POLL_INTERVAL_SEC // 60} 分鐘\n"
        f"• 摘要：每 {config.SUMMARY_INTERVAL_HOURS} 小時"
        f"（{config.DAY_START_HOUR}:00–{config.DAY_END_HOUR}:00）\n"
        f"• 目前區間：{cond}\n"
        f"• 最後讀數：{last}\n"
        f"• Google Sheets：{'已設定' if config.GOOGLE_SHEET_ID else '未設定'}"
    )
    await update.message.reply_text(txt)


async def cmd_dump(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = await fetch_data()
    if not raw:
        await update.message.reply_text("抓資料失敗。")
        return
    bio = io.BytesIO(json.dumps(raw, ensure_ascii=False, indent=2, default=str).encode("utf-8"))
    bio.name = "raw_dump.json"
    await update.message.reply_document(document=bio,
                                        caption="原始資料；若解析有誤把這個檔給開發者校正。")


async def on_error(update, context):
    """全域錯誤處理：記下例外，避免單一指令/工作崩潰沒人理。"""
    log.error("處理 update 時發生例外：%s", context.error, exc_info=context.error)


def build_application():
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], cmd_help))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("now", cmd_now))
    app.add_handler(CommandHandler("chart", cmd_chart))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("dump", cmd_dump))
    app.add_error_handler(on_error)

    jq = app.job_queue
    jq.run_repeating(poll_job, interval=config.POLL_INTERVAL_SEC, first=10)
    jq.run_repeating(summary_job, interval=int(config.SUMMARY_INTERVAL_HOURS * 3600), first=120)
    return app


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("缺少 TELEGRAM_BOT_TOKEN，請先設定 .env（參考 .env.example）。")
    if not config.TELEGRAM_CHAT_ID:
        log.warning("尚未設定 TELEGRAM_CHAT_ID，主動警報/摘要不會發出。"
                    "請先用 /id 指令取得 chat_id 並填入 .env。")
    app = build_application()
    log.info("CareLink Bot 啟動，開始輪詢…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
