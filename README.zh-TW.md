# LINE 客服機器人範本

[![CI](https://github.com/kiresakura/LineBotProject/actions/workflows/ci.yml/badge.svg)](https://github.com/kiresakura/LineBotProject/actions/workflows/ci.yml)

**給中小店家的 LINE 官方帳號機器人：依 YAML 裡的問答自動回覆常見問題、知道你的營業時間，答不出來就轉給真人。**

[English](README.md)

> 這是範本／展示版，以**虛構**的「小島咖啡」為例。把兩個 YAML 換成你的內容即可使用，也可以依店家、補習班或社群的需求客製。目前沒有公開執行中的實例。

## 30 秒示範（不需要 LINE 帳號）

```bash
git clone https://github.com/kiresakura/LineBotProject.git
cd LineBotProject
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m support_bot.demo
```

示範會把 [`examples/demo-shop.txt`](examples/demo-shop.txt) 的對話送進與 Webhook 相同的程式（本機 SQLite、模擬時間）。實際輸出節錄：

```text
🕑 2026-10-13（二）14:00，營業中

王小姐: 請問營業到幾點？
🤖 週二至週日 10:00–20:00，週一公休；臨時公休會另外公告。

王小姐: 可以帶毛小孩嗎？
🤖 歡迎！寵物請使用牽繩或提籠，店內備有寵物水碗。

王小姐: 週末可以包場辦生日派對嗎？
🔔 通知管理員（log）：轉真人 #1｜王小姐：週末可以包場辦生日派對嗎？
🤖 這個問題我先幫您轉給店員，已通知專人，會盡快回覆您 🙏

🕑 2026-10-13（二）22:30，非營業時間

陳先生: 我昨天掉了一把傘在店裡
🔔 通知管理員（log）：轉真人 #2｜陳先生：我昨天掉了一把傘在店裡
🤖 目前是非營業時間（週二至週日 10:00–20:00）。
   您的訊息已記錄，店員會在營業時間回覆您 🙏

店長: /待處理
🤖 📋 待處理 2 筆（由舊到新）
   #1 10/13 14:00 王小姐
      週末可以包場辦生日派對嗎？
```

想自己輸入訊息：`python -m support_bot.demo --interactive`；看群組名冊模組：`python -m support_bot.demo examples/demo-group.txt`。

## 適合誰

- **店家、咖啡廳、美髮美甲**：營業時間、地址、停車、付款方式即時回答；輸入關鍵字就送出菜單連結或當期活動。
- **補習班、工作室**：上課時間、費用、報名等常見問題；涉及個別學生的問題轉給櫃台。
- **社群經營者**：選配的群組名冊，讓成員在 LINE 群組裡登記名稱、幹部管理名單。

## 功能

| | 做什麼 | 改哪裡 |
|---|---|---|
| **FAQ 自動回覆** | 關鍵字比對（命中字數多者優先）、相似詞（「毛小孩」→「寵物」）、與問題原文相近的訊息 | `config/faq.yaml` |
| **營業時間與規則** | 每週營業時段（一天多段、可跨午夜）、臨時公休日、「菜單」「優惠」等關鍵字的固定回覆 | `config/rules.yaml` |
| **答不出來轉真人** | 回覆「已通知專人」（非營業時間改回營業時間說明），記錄到待處理清單並通知管理員 | `config/rules.yaml`、`HANDOFF_NOTIFIER` |
| **管理指令** | `/待處理` 列出待處理問題、`/完成 編號` 結案；只限 `ADMIN_USER_IDS` 白名單，只能在一對一聊天使用 | `ADMIN_USER_IDS` |
| **群組名冊**（選配） | 成員把 LINE 名稱與登記名稱綁定；幹部可查詢、列出、管理成員 | `ROSTER_ENABLED=true` |
| **AI 回答**（選配，預設關閉） | 任何 OpenAI 相容 API；只根據 FAQ 回答並標註出處，無法根據 FAQ 回答就轉真人 | `AI_ENABLED=true` |

通知管道是一個小介面：預設寫一行 log（部署平台的 log 頁面就看得到）；設 `HANDOFF_NOTIFIER=line_push` 改成推播到每位管理員的 LINE。LINE Notify 已於 2025-03-31 停止服務，push message 是常見的替代做法，會計入官方帳號每月的訊息則數。

### 安全與可靠

- `/callback` 的 `X-Line-Signature` 必須等於以 channel secret 對內容計算的 HMAC-SHA256，否則回 HTTP 400。
- 同一個 `webhookEventId` 只處理一次，LINE 重送時不會重複回覆或重複轉真人；若在產生回覆之前就失敗（含 worker 逾時），會釋放紀錄讓重送再試一次。
- 金鑰與設定一律走環境變數；缺少 LINE 憑證、YAML 格式錯誤，或通知／AI 設定不完整時，程式拒絕啟動。
- 在群組裡只回應名冊指令，不會用 FAQ 或轉真人訊息洗版。

## 訊息處理順序

```text
一對一聊天：管理指令 → 名冊指令（有開啟時）→ 固定關鍵字 → FAQ → AI（有開啟時）→ 轉真人
群組／多人聊天室：名冊指令（有開啟時）→ 其他訊息不回覆
```

## 客製方式

1. **改 `config/faq.yaml`**：每筆有 `id`、`question`、`keywords`、`answer`；顧客的其他說法加到 `synonyms`；問候、道謝這類閒聊加上 `standalone: true`，「您好，我想取消訂單」才不會只得到一句問候。
2. **改 `config/rules.yaml`**：`business_hours`、`closed_dates`、轉真人與非營業時間的回覆、`keyword_replies`。
3. **離線確認**：`python -m support_bot.demo --interactive` 會讀同一份設定（也可以用 `--faq`、`--rules` 指定另一份）。YAML 寫錯時程式在啟動階段就會停下並指出檔名與問題。

常見的客製需求：你的 FAQ 與口吻、圖文選單、從機器人直接回覆顧客、待處理清單後台、其他通知管道。

## 自行部署

### 1. 建立 LINE channel

1. 建立 LINE 官方帳號並啟用 Messaging API（LINE Official Account Manager → 設定 → Messaging API），之後就能在 [LINE Developers Console](https://developers.line.biz/console/) 管理這個 channel。
2. 在 Console 開啟該 channel：
   - **Basic settings** → **Channel secret** → `LINE_CHANNEL_SECRET`；**Your user ID** → 填進 `ADMIN_USER_IDS`
   - **Messaging API** → 發行 **Channel access token (long-lived)** → `LINE_CHANNEL_ACCESS_TOKEN`
3. 在 LINE Official Account Manager 關閉內建的自動回應訊息，避免和機器人同時回覆（使用名冊時另外允許加入群組）。

### 2. 啟動伺服器

**Docker（任何 VPS）：**

```bash
cp .env.example .env        # 填入 LINE 的值
docker compose up -d --build                        # SQLite，資料存在 bot-data volume
docker compose --profile postgres up -d --build     # 或搭配 PostgreSQL：.env 設 DATABASE_URL=postgresql://bot:bot@postgres:5432/bot
```

服務監聽 8000 埠；LINE 只會呼叫 `https://` 的 Webhook，前面要接 HTTPS（例如反向代理）。使用 `postgres` profile 時，第一次啟動可能會在資料庫就緒前自動重啟幾次（`restart: unless-stopped`）。

**Render：** New → Web Service → 連結你的 repository → 選 Docker runtime（會用 `Dockerfile` 建置）→ 加入環境變數 → 部署。Render 的檔案系統在沒有掛載磁碟時不會保留，請使用 PostgreSQL（`DATABASE_URL`）保存待處理清單與名冊。

**Railway：** New Project → Deploy from GitHub repo。`railway.toml` 已設定 gunicorn 啟動指令與 `/health` 健康檢查。新增 PostgreSQL，將 `DATABASE_URL` 設為 `${{Postgres.DATABASE_URL}}`，再加入 LINE 的變數。

### 3. 設定 Webhook

在 Console 的 **Messaging API** 分頁把 **Webhook URL** 設為 `https://<你的網域>/callback`，按 **Verify**，並開啟 **Use webhook**。接著傳訊息給你的官方帳號即可。

### 環境變數

| 變數 | 預設 | 說明 |
|---|---|---|
| `LINE_CHANNEL_SECRET` | 無（必填） | 驗證 `X-Line-Signature` |
| `LINE_CHANNEL_ACCESS_TOKEN` | 無（必填） | 回覆訊息、取得顯示名稱、推播通知 |
| `DATABASE_URL` | `sqlite:///bot.db` | `postgresql://…` 或 `sqlite:///檔案.db`；Docker 映像使用 `/app/data/bot.db` |
| `ADMIN_USER_IDS` | 空白 | 可以使用管理指令的 LINE user ID，逗號分隔 |
| `HANDOFF_NOTIFIER` | `log` | `log` 或 `line_push`（需要 `ADMIN_USER_IDS`） |
| `FAQ_FILE`、`RULES_FILE` | `config/faq.yaml`、`config/rules.yaml` | 內容設定檔 |
| `ROSTER_ENABLED` | `false` | 開啟群組名冊指令 |
| `AI_ENABLED` | `false` | 開啟 AI 回答；開啟後顧客訊息會送到下列 API |
| `AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL` | `https://api.openai.com/v1`、空白、空白 | OpenAI 相容端點；開啟 AI 時必須設定 `AI_MODEL` |
| `PORT` | 5000（`python -m support_bot.web`）、8000（Docker） | 監聽埠 |

同樣的清單與註解見 [`.env.example`](.env.example)。

## 群組名冊模組

設定 `ROSTER_ENABLED=true` 後，原本的名冊指令可在群組與一對一聊天使用：`/登記 名稱`、`/修改`、`/查詢`、`/我是誰`、`/幹部`、`/說明`、`/選單`，以及幹部專用的 `/名冊 [頁碼|全部]`、`/代登記`、`/刪除`、`/設定管理員`。`ADMIN_USER_IDS` 裡的管理員一律具有幹部權限；白名單為空時，第一位已登記並送出 `/設定管理員` 的成員成為第一位幹部。一個部署只有一份名冊（不分群組）。

## 架構

```text
LINE 平台 ── POST /callback ──▶ web.py      驗證簽章、略過重送事件、呼叫 LINE API
                                  │
demo.py（終端機）───────────────▶ bot.py      管理指令 → 名冊 → 固定關鍵字 → FAQ → AI → 轉真人
                                  ├── rules.py / faq.py    讀取 config/*.yaml、營業時間、比對
                                  ├── ai.py                選配的 OpenAI 相容用戶端（只用標準函式庫）
                                  ├── handoff.py           通知管道：log、LINE 推播
                                  ├── roster.py            選配的群組名冊指令（＋ roster_messages.py）
                                  └── database.py          SQLite 或 PostgreSQL：待處理清單、已處理事件、名冊
```

## 開發與測試

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

173 個測試約一秒跑完，不需要 LINE 帳號、金鑰、網路或資料庫伺服器：FAQ 比對、營業時間（含跨午夜與公休日）、完整處理流程、轉真人與通知管道、管理員白名單、名冊指令、Webhook 驗簽與重送事件、以假模型測 AI 流程，以及兩份示範腳本。GitHub Actions 在 Python 3.11 與 3.12 執行 `ruff` 與 `pytest`，也對 PostgreSQL 17 跑同一套測試（本機設定 `TEST_DATABASE_URL` 即可），並建置 Docker 映像、檢查執行中容器的 `/health`。

技術棧：Python 3.11+、Flask、line-bot-sdk v3、PyYAML、gunicorn、SQLite 或 PostgreSQL（psycopg2）。

---

Customization: https://www.tasker.com.tw/workroom/crimson

## 授權

[MIT](LICENSE)
