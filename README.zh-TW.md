# LINE 群組成員名冊機器人

[![CI](https://github.com/kiresakura/LineBotProject/actions/workflows/ci.yml/badge.svg)](https://github.com/kiresakura/LineBotProject/actions/workflows/ci.yml)

**幫 LINE 群組管理成員名冊：** 成員用一行指令把 LINE 名稱和遊戲角色名稱綁在一起，幹部不必離開 LINE 就能查詢、代登記、刪除成員。

[English](README.md)

> **狀態：** 目前沒有公開執行中的實例。這個機器人原本為一個線上遊戲公會的 LINE 群組打造，現已停止運作；本 repo 是可自行部署的原始碼——可以先用示範模式離線試玩，或照下方步驟部署自己的版本。

## 功能

- **自助登記**：`/登記 <名稱>` 綁定 LINE 帳號與遊戲角色名稱（最多 100 字、每人一筆、名稱不可重複）；`/修改` 更改名稱；`/我是誰` 查看自己的資料。
- **查詢**：`/查詢 <關鍵字>` 以部分比對搜尋 LINE 名稱或遊戲名稱。
- **名冊僅限幹部**：`/名冊` 每頁 20 人，附上一頁／下一頁按鈕；`/名冊 全部` 以純文字列出所有人。
- **幹部工具**：`/代登記` 幫在群組發過言的人登記（可同時設為幹部）、`/刪除` 移除成員、`/設定管理員` 新增幹部。
- **第一位幹部**：還沒有任何幹部時，第一個傳 `/設定管理員` 的已登記成員會成為幹部。
- **名稱同步**：已登記成員改了 LINE 顯示名稱，下一次發言時名冊會自動更新。
- **圖文回覆**：Flex Message 卡片與 Quick Reply 按鈕；`/選單` 開啟按鈕選單。
- **只接受簽章正確的 Webhook**：`/callback` 收到的請求，`X-Line-Signature` 必須等於以 channel secret 對內容計算的 HMAC-SHA256，否則回 HTTP 400。

## 指令

機器人只回應 `/` 開頭的訊息；其他訊息不回覆，但會記下發言者供 `/代登記` 使用。

| 指令 | 對象 | 說明 |
|---|---|---|
| `/登記 <遊戲名稱>` | 所有人 | 登記自己 |
| `/修改 <新遊戲名稱>` | 所有人 | 修改自己的遊戲名稱 |
| `/查詢 <關鍵字>` | 所有人 | 以 LINE 名稱或遊戲名稱搜尋 |
| `/我是誰` | 所有人 | 查看自己的資料 |
| `/幹部`（`/幹部名單`） | 所有人 | 查看幹部名單 |
| `/說明`（`/help`、`/幫助`） | 所有人 | 指令說明 |
| `/選單`（`/menu`、`/功能`） | 所有人 | 按鈕選單 |
| `/名冊 [頁碼 \| 全部]` | 幹部 | 查看名冊 |
| `/代登記 <LINE名稱> [遊戲名稱] [幹部]` | 幹部 | 幫在群組發過言的成員登記；省略遊戲名稱時使用其 LINE 名稱；加上 `幹部`（或 `管理員`、`admin`）同時設為幹部 |
| `/刪除 <名稱>` | 幹部 | 依遊戲名稱或 LINE 名稱刪除成員 |
| `/設定管理員 <名稱>` | 幹部 | 把成員設為幹部（依序比對：遊戲名稱、LINE 名稱、部分比對） |

## 離線試玩（示範模式）

不需要 LINE 帳號、金鑰或 PostgreSQL。`demo.py` 把模擬的群組訊息送進與 Webhook 相同的指令處理程式，資料存在用完即刪的 SQLite 檔。

```bash
git clone https://github.com/kiresakura/LineBotProject.git
cd LineBotProject
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python demo.py examples/demo-chat.txt   # 重播一段群組對話
python demo.py                          # 或自己輸入，例如：小明: /登記 光之勇者
```

每行格式為「名稱: 訊息」，省略名稱時沿用上一位發言者；加上 `--db roster.db` 可保留資料。重播節錄：

```text
小明: /設定管理員
🤖 ✅ 你已成為第一位管理員！

   現在可以使用管理員指令了
   [查看名冊] [查看說明]

小華: 大家好，我是新來的
小明: /代登記 小華 夜影刺客
🤖 ✅ 代登記成功

   已為「小華」登記
   遊戲名稱：夜影刺客
   [查看名冊]

小明: /名冊
🤖 📋 成員名冊 第 1/1 頁，共 3 人
   1. 小明 ↔ 光之勇者
   2. 阿美 ↔ 風之旅人
   3. 小華 ↔ 夜影刺客
```

## 架構

```text
LINE 平台 ── POST /callback ──▶ app.py        Flask：驗證簽章、取得顯示名稱、送出回覆
                                  │
demo.py（終端機）────────────────▶ handlers.py   解析指令、檢查權限（不呼叫 LINE API）
                                  ├──▶ database.py   名冊存取：正式環境 PostgreSQL，示範與測試用 SQLite
                                  └──▶ messages.py   組出 Flex／文字回覆
```

| 檔案 | 角色 |
|---|---|
| `app.py` | Flask 應用，提供 `/callback`（LINE Webhook）與 `/health`；唯一呼叫 LINE Messaging API 的模組 |
| `handlers.py` | 指令解析、路由與權限檢查；回傳 LINE 訊息物件或 `None` |
| `database.py` | 名冊查詢；`DATABASE_URL` 決定使用 PostgreSQL（`postgresql://…`）或 SQLite（`sqlite:///檔名.db`） |
| `messages.py` | Flex Message／Quick Reply 產生器 |
| `demo.py` | 離線終端機示範 |

每個部署只有一份名冊，不會依群組分開；一個社群部署一份。

## 部署自己的版本

### 1. 建立 LINE Messaging API channel

1. 建立 LINE 官方帳號並啟用 Messaging API（LINE Official Account Manager → 設定 → Messaging API），之後即可在 [LINE Developers Console](https://developers.line.biz/console/) 管理這個 channel。
2. 在 Console 開啟該 channel：
   - **Basic settings** → **Channel secret** → `LINE_CHANNEL_SECRET`
   - **Messaging API** → 發行 **Channel access token (long-lived)** → `LINE_CHANNEL_ACCESS_TOKEN`
3. 在 LINE Official Account Manager 允許帳號加入群組，並關閉自動回應訊息。

### 2. 部署網站服務

任何能執行 Python 網站程序並提供 PostgreSQL 的平台都可以。repo 內附 [Railway](https://railway.app/) 用的 `Procfile` 與 `railway.toml`（gunicorn、`/health` 健康檢查）：

1. **New Project** → **Deploy from GitHub repo** → 選擇你的 repo。
2. 在專案中新增 PostgreSQL；到機器人服務的 **Variables** 設定 `DATABASE_URL` 為資料庫連線網址（Railway 可用參照 `${{Postgres.DATABASE_URL}}`），以及 `LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN`。
3. 部署。啟動時會自動建立資料表，`GET /health` 回傳 `OK`。

### 3. 連接 Webhook

1. 回到 Console 的 **Messaging API** 分頁，把 **Webhook URL** 設為 `https://<你的網域>/callback`，按 **Verify**，並開啟 **Use webhook**。
2. 把機器人帳號邀進 LINE 群組，傳 `/說明` 試試。

### 環境變數

| 變數 | 必填 | 說明 |
|---|---|---|
| `LINE_CHANNEL_SECRET` | 是 | 驗證 `X-Line-Signature`；未設定時程式拒絕啟動 |
| `LINE_CHANNEL_ACCESS_TOKEN` | 是 | 送出回覆、查詢顯示名稱；未設定時程式拒絕啟動 |
| `DATABASE_URL` | 是 | 正式環境用 `postgresql://…`；本機可用 `sqlite:///roster.db` |
| `PORT` | 否 | `python app.py` 的連接埠（預設 5000） |

範本見 [`.env.example`](.env.example)。要在自己電腦接真正的 LINE：複製成 `.env` 並填入、執行 `python app.py`，再用 `ngrok http 5000` 之類的通道把 5000 埠公開。

## 開發

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

67 個測試全部離線執行，約一秒跑完，不需要 LINE 帳號、金鑰或資料庫伺服器。涵蓋名冊存取（以 SQLite 執行）、指令解析與權限、示範重播，以及 Webhook：正確／缺少／用錯 secret 的簽章、被竄改的內容，和一個簽章正確的訊息事件從頭到尾的處理（LINE API 以替身取代）。GitHub Actions 會在每次 push 與 pull request 時，於 Python 3.11 與 3.12 執行 `ruff check .` 與 `pytest`。

## 技術

Python 3.11+、Flask、line-bot-sdk v3、PostgreSQL（psycopg2）、gunicorn；示範與測試使用 SQLite。
