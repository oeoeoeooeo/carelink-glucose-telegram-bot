# 參與貢獻 Contributing

歡迎一起讓更多 T1D 家庭受益！ Contributions welcome — let's help more T1D families.

## 可以怎麼幫忙 / Ways to help

- 🐛 **回報問題**：開 [Issue](https://github.com/oeoeoeooeo/carelink-glucose-telegram-bot/issues)。
  若是資料解析錯誤，請附上 `/dump` 匯出的內容，**務必先移除姓名等個資**。
- 🌍 **移植**：Linux（systemd）、Windows、Raspberry Pi、Docker 版本。
- 🩺 **其他機型／地區回報**：你用的 Medtronic 機型、CareLink 區域是否可用。
- 📖 **文件／翻譯**：補強說明、其他語言。
- ✨ **功能**：更多警報邏輯、其他通知管道（LINE、Discord…）等。

## 開發須知 / Notes

- **永遠不要** commit 任何 token、cookie、`.env`、`carelink_state.json`、真實血糖或病患姓名。
  送 PR 前請確認 `git status` 沒有夾帶機敏檔（`.gitignore` 已涵蓋常見的）。
- 這是非官方、非醫療器材的工具；任何改動請保留 README 的醫療免責精神。
- Python 風格盡量與現有程式一致即可。

## 安全揭露 / Security

發現會洩漏帳密或個資的問題，請私下來信 **oeoeoeooeo@gmail.com**，不要開公開 Issue。
