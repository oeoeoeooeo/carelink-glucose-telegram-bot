#!/bin/bash
# 依你目前的專案路徑產生並安裝兩個 launchd 服務（瀏覽器保活 + Telegram bot）。
# Generates & installs the two launchd services using your own project path.
set -e

# 專案根目錄 = 這個腳本的上一層
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$PROJECT_DIR/venv/bin/python"
AGENTS="$HOME/Library/LaunchAgents"
UID_NUM="$(id -u)"

if [ ! -x "$PYTHON" ]; then
  echo "找不到 venv 的 python：$PYTHON"
  echo "請先在專案根目錄建立 venv：python3.12 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi
if [ ! -f "$PROJECT_DIR/carelink_state.json" ]; then
  echo "⚠️ 找不到 carelink_state.json，請先執行：python carelink_web.py login（仍會繼續安裝服務）"
fi

mkdir -p "$AGENTS"

make_plist() {
  # $1=label  $2=plist路徑  $3...=ProgramArguments（python 之後的參數）
  local label="$1"; local out="$2"; shift 2
  local args=""
  for a in "$PYTHON" "$@"; do
    args="$args        <string>$a</string>\n"
  done
  cat > "$out" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$label</string>
    <key>ProgramArguments</key>
    <array>
$(printf "%b" "$args")    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ThrottleInterval</key><integer>30</integer>
    <key>StandardOutPath</key><string>$PROJECT_DIR/${label##*.}.log</string>
    <key>StandardErrorPath</key><string>$PROJECT_DIR/${label##*.}.err.log</string>
</dict>
</plist>
EOF
  echo "已產生 $out"
}

make_plist "com.carelink.browser" "$AGENTS/com.carelink.browser.plist" "$PROJECT_DIR/carelink_web.py" keep 240
make_plist "com.carelink.bot"     "$AGENTS/com.carelink.bot.plist"     "$PROJECT_DIR/bot.py"

# 看門狗：raw_dump.json 超過 30 分鐘沒更新就自動重啟保活服務（每 600 秒檢查一次）
# Watchdog: auto-restarts the keepalive service if raw_dump.json goes stale for 30+ min
cat > "$AGENTS/com.carelink.watchdog.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.carelink.watchdog</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>$PROJECT_DIR/watchdog.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>StartInterval</key><integer>600</integer>
    <key>RunAtLoad</key><true/>
    <key>StandardOutPath</key><string>$PROJECT_DIR/watchdog.log</string>
    <key>StandardErrorPath</key><string>$PROJECT_DIR/watchdog.log</string>
</dict>
</plist>
EOF
echo "已產生 $AGENTS/com.carelink.watchdog.plist"

for svc in com.carelink.browser com.carelink.bot com.carelink.watchdog; do
  launchctl bootout "gui/$UID_NUM/$svc" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_NUM" "$AGENTS/$svc.plist"
  echo "已啟動 $svc"
done

echo ""
echo "完成。確認狀態（中間欄 0 = 正常）："
launchctl list | grep carelink || echo "（還沒出現，稍等幾秒再 launchctl list | grep carelink）"
