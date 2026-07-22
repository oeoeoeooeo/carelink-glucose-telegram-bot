#!/bin/sh
# CareLink watchdog：raw_dump.json 超過 STALE_SEC 沒更新，就重啟 com.carelink.browser 保活服務。
# Watchdog: if raw_dump.json goes stale for more than STALE_SEC, restart the keepalive service.
#
# 背景 / Why：CareLink 會不定期強制登出（sso/logout），保活瀏覽器的自動重新授權
# 偶爾會卡死在半路，一卡就一直沒資料；重啟保活服務讓新的 context 重走授權即可自癒
# （實測 2-4 分鐘內恢復，不需手動登入）。
# CareLink occasionally force-logs-out the session and the automatic re-auth can stall;
# restarting the keepalive service re-authorizes from storage_state (~2-4 min, no manual login).
#
# 由 com.carelink.watchdog（launchd，每 600 秒）執行；健康時完全不輸出。
# Run by launchd every 600 s; completely silent when healthy.

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DUMP="$PROJECT_DIR/raw_dump.json"
STAMP="$PROJECT_DIR/.watchdog_last_kick"
STALE_SEC=1800      # 資料超過 30 分鐘沒更新視為卡死 / stale threshold
COOLDOWN_SEC=900    # 兩次重啟至少間隔 15 分鐘，留時間讓重新授權跑完 / min gap between restarts

now=$(date +%s)
mtime=$(stat -f %m "$DUMP" 2>/dev/null || echo 0)
age=$((now - mtime))
[ "$age" -le "$STALE_SEC" ] && exit 0

last_kick=$(cat "$STAMP" 2>/dev/null || echo 0)
[ $((now - last_kick)) -le "$COOLDOWN_SEC" ] && exit 0

echo "$(date '+%Y-%m-%d %H:%M:%S') raw_dump.json 已 ${age}s 未更新 → kickstart com.carelink.browser"
echo "$now" > "$STAMP"
launchctl kickstart -k "gui/$(id -u)/com.carelink.browser"
