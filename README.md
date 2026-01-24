# LINE 群組成員名冊機器人

管理群組成員的 LINE 名稱與遊戲角色名稱對應。

## 功能指令

| 指令 | 說明 |
|------|------|
| `/登記 [遊戲名稱]` | 綁定 LINE 與遊戲角色名稱 |
| `/修改 [新遊戲名稱]` | 修改遊戲名稱 |
| `/查詢 [名稱]` | 搜尋成員 |
| `/名冊` | 顯示所有成員 |
| `/我是誰` | 查看自己的登記資訊 |
| `/說明` | 顯示指令說明 |

### 管理員指令
| 指令 | 說明 |
|------|------|
| `/刪除 [名稱]` | 刪除成員資料 |
| `/設定管理員 [遊戲名稱]` | 設定管理員 |

## 部署到 Railway

### 1. 建立 GitHub Repository

```bash
cd LineBotProject
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/你的帳號/你的repo.git
git push -u origin main
```

### 2. 在 Railway 建立專案

1. 前往 [Railway](https://railway.app/) 並登入
2. 點擊 **New Project**
3. 選擇 **Deploy from GitHub repo**
4. 選擇你的 repository

### 3. 新增 PostgreSQL 資料庫

1. 在專案中點擊 **New** → **Database** → **Add PostgreSQL**
2. Railway 會自動提供 `DATABASE_URL` 環境變數

### 4. 設定環境變數

在 Railway 專案中：
1. 點擊你的服務
2. 進入 **Variables** 分頁
3. 新增以下變數：
   - `LINE_CHANNEL_SECRET`
   - `LINE_CHANNEL_ACCESS_TOKEN`

### 5. 取得 Webhook URL

部署完成後，Railway 會提供一個網址，例如：
`https://你的專案.up.railway.app`

### 6. 設定 LINE Webhook

1. 前往 [LINE Developers Console](https://developers.line.biz/)
2. 選擇你的 Channel
3. 在 **Messaging API** 分頁中設定 Webhook URL：
   `https://你的專案.up.railway.app/callback`
4. 開啟 **Use webhook**
5. 關閉 **Auto-reply messages**

## 本地開發

```bash
# 安裝依賴
pip install -r requirements.txt

# 設定環境變數
cp .env.example .env
# 編輯 .env 填入你的憑證

# 啟動服務
python app.py
```

使用 ngrok 進行本地測試：
```bash
ngrok http 5000
```

## 技術棧

- Python 3.11+
- Flask
- line-bot-sdk v3
- PostgreSQL
- psycopg2-binary
