# 安裝步驟 Setup

> 在一台 24 小時開機、有螢幕能開瀏覽器的 Mac 上做一次，約 30 分鐘。
> Do this once on an always‑on Mac. ~30 min. 指令前的 `$` 不用打。
> 先看 [README](README.md) 的醫療免責。Read the medical disclaimer first.

---

## 0. CareLink 帳號 / Account

- 建議用 **follower／care partner（追蹤者）帳號**，由主帳號在官方 App「邀請照護者」邀請你。
- **不用關 MFA、不用 VPN。** No need to disable MFA or use a VPN.

## 1. Homebrew Python 3.12

系統內建 Python 3.9（LibreSSL）連 CareLink 會有 TLS 問題，請用 Homebrew 的 3.12。

```bash
$ brew install python@3.12
$ /opt/homebrew/bin/python3.12 --version   # Python 3.12.x
```

沒有 brew 先裝：https://brew.sh

## 2. 取得程式碼、建 venv、裝相依

```bash
$ git clone https://github.com/oeoeoeooeo/carelink-glucose-telegram-bot.git
$ cd carelink-glucose-telegram-bot
$ /opt/homebrew/bin/python3.12 -m venv venv
$ source venv/bin/activate
$ pip install -r requirements.txt
$ playwright install chromium      # 備用瀏覽器；登入會優先用系統 Chrome
```

## 3. 登入 CareLink（產生 carelink_state.json）

會跳出 Chrome 視窗，**不用 VPN**：

```bash
$ source venv/bin/activate
$ python carelink_web.py login
```

1. 在跳出的 Chrome 輸入追蹤者帳密、解 reCAPTCHA，登入到看見血糖畫面。
2. 偵測到血糖後會自動存檔、關閉，並印出目前血糖。
3. 根目錄會出現 `carelink_state.json`（本機登入狀態，已被 git 忽略）。

> 之後保活服務會自動沿用並刷新，平常不用再登入。

## 4. 建立 Telegram bot

1. Telegram 找 **@BotFather** → `/newbot` → 取名 → 拿到一串 **token**。
2. 建一個群組，把你、家人、bot 都拉進去。
3. （可選）對 BotFather 設 `/setprivacy` → Disable，讓 bot 讀得到群組訊息。

## 5. 設定 .env

```bash
$ cp .env.example .env
$ open -e .env        # 填 TELEGRAM_BOT_TOKEN
```

至少填 `TELEGRAM_BOT_TOKEN`。`TELEGRAM_CHAT_ID` 先空著，下一步用 `/id` 取得。
門檻預設低 70 / 高 180，可在這裡改。

## 6. 先手動跑、拿 chat_id

開兩個終端機分頁（都先 `source venv/bin/activate`）：

```bash
# 分頁 A：保活抓資料 keep
$ python carelink_web.py keep 240
# 分頁 B：bot
$ python bot.py
```

到群組打：
- `/id` → bot 回一組 `chat_id`（群組通常是負數）。填進 `.env` 的 `TELEGRAM_CHAT_ID`，
  然後 Ctrl‑C 停掉分頁 B、再跑一次 `python bot.py`。
- `/now`（目前血糖）、`/chart`（趨勢圖）、`/status`（狀態）確認正常。

確認 OK 後 Ctrl‑C 停掉兩個分頁，進下一步常駐。

## 7.（選填）Google Sheets 記錄

1. https://console.cloud.google.com 建專案，啟用 **Google Sheets API**。
2. 建**服務帳戶**，下載 JSON 金鑰，改名 `service_account.json` 放專案根目錄。
3. 開一個試算表，把金鑰裡的 `client_email` 加入共用、給編輯權限。
4. 把試算表 ID 填進 `.env` 的 `GOOGLE_SHEET_ID`，重啟 bot。

## 8. 設定 24 小時自動執行（launchd）

用內附腳本自動產生並安裝三個服務（會用你目前的專案路徑與 venv）：

```bash
$ ./scripts/install_launchd.sh
```

它會：
- 依你的專案路徑產生 `com.carelink.browser.plist`、`com.carelink.bot.plist`、`com.carelink.watchdog.plist`
- 安裝到 `~/Library/LaunchAgents/` 並啟動
- 保活與 bot 服務都會開機自動啟動、當掉自動重啟
- **watchdog（看門狗）**每 10 分鐘檢查一次：`raw_dump.json` 超過 30 分鐘沒更新
  （CareLink 強制登出後自動重新授權偶爾會卡死），就自動重啟保活服務自癒，
  不用手動處理；觸發時會在 `watchdog.log` 留一行紀錄

確認在跑（中間欄 0 = 正常）：

```bash
$ launchctl list | grep carelink
```

日常管理 / Day‑to‑day：

```bash
# 看 log（Python log 在 .err.log）
$ tail -f keep.log
$ tail -f bot.err.log

# 改 .env 或程式後重啟
$ launchctl kickstart -k gui/$(id -u)/com.carelink.bot
$ launchctl kickstart -k gui/$(id -u)/com.carelink.browser

# 停用
$ launchctl bootout gui/$(id -u)/com.carelink.bot
$ launchctl bootout gui/$(id -u)/com.carelink.browser
$ launchctl bootout gui/$(id -u)/com.carelink.watchdog
```

> 到「系統設定 → 電池／鎖定畫面」把這台 Mac 設成**不要自動睡眠**，睡著就不會抓資料。
> keep 服務會開一個小 Chrome 視窗常駐，別關它。

---

## 出問題時 Troubleshooting

| 症狀 | 處理 |
|------|------|
| keep.log 出現「抓取失敗／token 過期」後卡住 | watchdog 30 分鐘內會自動重啟保活服務自癒（看 `watchdog.log`）；若重啟後仍失敗才需重跑 `python carelink_web.py login` |
| `/now` 無讀數、`TRANSMITTER_DISCONNECTED` | CGM 傳輸器離線，等恢復連線 |
| `/now` 數字錯誤或空白 | `/dump` 匯出，移除個資後開 Issue 給社群校正 |
| bot 沒主動發警報 | `TELEGRAM_CHAT_ID` 沒填或填錯，用 `/id` 重拿 |
| 半夜還在發摘要 | 調 `.env` 的 `DAY_START_HOUR` / `DAY_END_HOUR` |
| launchd 服務 exit 78 | 用 `install_launchd.sh` 重裝；log 看 `*.err.log` |

更多見 [FAQ.md](FAQ.md)。
