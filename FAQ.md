# 常見問題 FAQ

> 醫療免責請見 [README](README.md#️-醫療免責--medical-disclaimer)。這個工具是備援提醒，不能取代原廠 App 與裝置警報。

---

### Q. 需要 VPN 嗎？/ Do I need a VPN?

**中文：** 不需要。網頁版 CareLink 登入走的是 `carelink-login.minimed.eu`（Auth0），多數地區（包含台灣）可以直接連。先前流傳「要掛歐洲 VPN」是針對另一種非官方手機 API 路線，本專案不走那條。

**EN:** No. The web login uses `carelink-login.minimed.eu` (Auth0), reachable from most regions. The "needs an EU VPN" advice applies to a different unofficial mobile‑API approach, which this project does **not** use.

---

### Q. 安全嗎？我的帳密會外洩嗎？/ Is it secure?

**中文：**
- 你的 CareLink 帳密**只**在你自己電腦的瀏覽器裡輸入，本專案不會儲存、不會傳到任何第三方。
- 登入後的權杖（cookie）存在你電腦本機的 `carelink_state.json`，**已被 `.gitignore` 排除**，不會上傳到 GitHub。
- Telegram bot token、血糖資料、病患姓名等全部列在 `.gitignore`，不會進版本控制。
- 整個系統只跑在你自己的電腦上，資料流向只有：你的電腦 → Telegram（你的群組）→（選填）你自己的 Google Sheets。

**EN:** Your CareLink credentials are only entered in your own browser and never stored or sent anywhere by this project. Login tokens live in a local `carelink_state.json` that is git‑ignored. Bot token, glucose data and patient names are all git‑ignored. Everything runs on your own machine.

---

### Q. 要花錢嗎？/ Does it cost anything?

不用。Telegram、Python、瀏覽器自動化、Google Sheets 全是免費的。唯一「成本」是一台要一直開著的電腦。
No. Telegram, Python, browser automation and Google Sheets are all free. The only cost is leaving a computer on.

---

### Q. 登入要多久重做一次？/ How often do I re‑login?

**中文：** 平常**不用**。常駐的瀏覽器會在權杖（約 50 分鐘）過期前自動刷新，實測可長時間自動運行。只有 CareLink 的長期登入 session 整個失效時（例如很久沒用、或在別處登出帳號），才需要重跑一次 `python carelink_web.py login`。

**EN:** Normally never. The always‑open browser auto‑refreshes the ~50‑minute token. You only re‑run the login when CareLink's long‑lived session fully expires.

---

### Q. 為什麼要一直開著一個 Chrome 視窗？/ Why keep a Chrome window open?

那個視窗負責「保住登入狀態 + 自動刷新權杖」。抓資料本身是純 HTTP、很輕量，但**刷新權杖**需要一個活著的網頁來觸發。所以它會常駐一個小視窗，別關掉它。
That window keeps the session alive and triggers token refresh. Data fetching itself is lightweight HTTP, but refreshing the token needs a live page. Leave the small window open.

---

### Q. `/now` 顯示沒有讀數、`sensorState=TRANSMITTER_DISCONNECTED`？

代表 CGM 傳輸器目前離線（沒貼、充電中、超出範圍、或感測器更換期）。這是真實狀況，等它恢復連線就會有資料，不是 bug。
The CGM transmitter is offline (not worn, charging, out of range, or sensor change). Real condition — data resumes when it reconnects.

---

### Q. 支援哪些機型／地區？/ Which devices / regions?

**中文：** 凡是會把資料上傳到 CareLink、且能在 `carelink.minimed.eu` 網頁看到即時血糖的 Medtronic 系統，原則上都適用（如 MiniMed 7xxG 系列 + Guardian 感測器，用 follower／care partner 帳號）。目前實測為歐洲區 CareLink。其他區域／機型歡迎來信或開 Issue 回報。

**EN:** Any Medtronic setup that uploads to CareLink and shows live glucose on `carelink.minimed.eu` (e.g. MiniMed 7xxG + Guardian, via a follower/care‑partner account). Tested on the EU CareLink. Reports from other regions welcome.

---

### Q. 一定要關 MFA（兩步驟驗證）嗎？/ Must I disable MFA?

不用。本專案用真人在瀏覽器登入一次（含解 reCAPTCHA），所以可以保留 MFA。
No. You log in once interactively in a browser (solving reCAPTCHA), so MFA can stay on.

---

### Q. 可以跑在 Windows／樹莓派／雲端嗎？/ Windows / Raspberry Pi / cloud?

**中文：** 目前是針對 macOS（launchd + 系統 Chrome）寫的。核心是 Python + Playwright + requests，理論上可移植到 Linux／Windows，只是自動啟動（launchd 換成 systemd／工作排程器）和瀏覽器路徑要自己調。歡迎社群貢獻移植版本。

**EN:** Currently targets macOS (launchd + system Chrome). The core is Python + Playwright + requests and is portable to Linux/Windows with changes to the service manager and browser path. Contributions welcome.

---

### Q. 資料多即時？/ How fresh is the data?

CGM 大約每 5 分鐘一個新值。保活服務每 240 秒抓一次、bot 每 5 分鐘判讀一次，所以警報通常在新數值出現後幾分鐘內送達。
CGM produces a value roughly every 5 minutes; the fetcher polls every 240s and the bot every 5 minutes, so alerts arrive within a few minutes of a new reading.

---

### Q. Medtronic 改版讓它壞掉怎麼辦？/ What if Medtronic changes their site?

有可能發生——這是非官方工具的本質。若 `/now` 一直失敗或解析錯誤，請開 Issue 並附上 `/dump` 匯出的內容（**記得先移除姓名等個資**），社群可一起修。
Possible — that's the nature of an unofficial tool. If it breaks, open an issue with `/dump` output (remove personal info first) so the community can fix the parser.

---

### 還有問題？/ More questions?

來信 **oeoeoeooeo@gmail.com** 或開 [Issue](https://github.com/oeoeoeooeo/carelink-glucose-telegram-bot/issues)。
