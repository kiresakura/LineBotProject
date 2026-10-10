# LINE Group Roster Bot

[![CI](https://github.com/kiresakura/LineBotProject/actions/workflows/ci.yml/badge.svg)](https://github.com/kiresakura/LineBotProject/actions/workflows/ci.yml)

**Keeps a member roster for a LINE group:** members link their LINE name to an in-game character name with a chat command, and officers can look up, register, and remove members without leaving LINE.

[繁體中文說明](README.zh-TW.md)

> **Status:** there is no public running instance of this bot. It was built for an online game guild's LINE group and is no longer running there. This repository is the deployable source: try it offline in demo mode, or follow the deployment steps to run your own copy.

## Features

- **Self-service registration** – `/登記 <name>` links your LINE account to a game character name (max 100 characters, one per person, names must be unique); `/修改` changes it; `/我是誰` shows your record.
- **Search** – `/查詢 <keyword>` matches part of a LINE name or game name.
- **Officer-only roster** – `/名冊` shows 20 members per page with previous/next buttons; `/名冊 全部` lists everyone as plain text.
- **Officer tools** – `/代登記` registers someone who has posted in the group (optionally as an officer), `/刪除` removes a member, `/設定管理員` promotes a member.
- **Bootstrap** – while there are no officers, the first registered member who sends `/設定管理員` becomes the first officer.
- **Name sync** – when a registered member changes their LINE display name, the roster picks it up on their next message.
- **Rich replies** – Flex Message cards and quick-reply buttons; `/選單` opens a button menu.
- **Signed webhooks only** – requests to `/callback` are rejected with HTTP 400 unless `X-Line-Signature` matches the HMAC-SHA256 of the body under the channel secret.

## Commands

The bot replies only to messages starting with `/`; everything else is ignored (but remembered for `/代登記`).

| Command | Who | What it does |
|---|---|---|
| `/登記 <game name>` | everyone | Register yourself |
| `/修改 <new game name>` | everyone | Change your game name |
| `/查詢 <keyword>` | everyone | Search by LINE name or game name |
| `/我是誰` | everyone | Show your own record |
| `/幹部` (`/幹部名單`) | everyone | List officers |
| `/說明` (`/help`, `/幫助`) | everyone | Command help |
| `/選單` (`/menu`, `/功能`) | everyone | Button menu |
| `/名冊 [page \| 全部]` | officers | Show the roster |
| `/代登記 <LINE name> [game name] [幹部]` | officers | Register a member who has posted in the group; without a game name their LINE name is used; `幹部` (or `管理員`, `admin`) also makes them an officer |
| `/刪除 <name>` | officers | Remove a member by game name or LINE name |
| `/設定管理員 <name>` | officers | Make a member an officer (exact game name, then exact LINE name, then partial match) |

## Try it offline (demo mode)

No LINE account, keys, or PostgreSQL needed. `demo.py` sends simulated group messages through the same command handlers the webhook uses and stores data in a throwaway SQLite file.

```bash
git clone https://github.com/kiresakura/LineBotProject.git
cd LineBotProject
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python demo.py examples/demo-chat.txt   # replay a scripted group chat
python demo.py                          # or type lines like: 小明: /登記 光之勇者
```

Each line is `<name>: <message>`; leave out the name to keep talking as the previous speaker. Add `--db roster.db` to keep the data between runs. Excerpt of the replay:

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

## Architecture

```text
LINE platform ── POST /callback ──▶ app.py        Flask: verify signature, look up display name, send reply
                                      │
demo.py (terminal) ──────────────────▶ handlers.py   parse commands, check permissions (no LINE API calls)
                                      ├──▶ database.py   roster storage: PostgreSQL in production, SQLite for demo/tests
                                      └──▶ messages.py   build Flex / text replies
```

| File | Role |
|---|---|
| `app.py` | Flask app with `/callback` (LINE webhook) and `/health`; the only module that calls the LINE Messaging API |
| `handlers.py` | Command parsing, routing, and permission checks; returns a LINE message object or `None` |
| `database.py` | Roster queries; `DATABASE_URL` selects PostgreSQL (`postgresql://…`) or SQLite (`sqlite:///file.db`) |
| `messages.py` | Flex Message / quick-reply builders |
| `demo.py` | Offline terminal demo |

Each deployment keeps one roster: members are not separated by group, so run one deployment per community.

## Deploy your own

### 1. Create a LINE Messaging API channel

1. Create a LINE Official Account and enable the Messaging API for it (LINE Official Account Manager → Settings → Messaging API). This creates a channel you can manage in the [LINE Developers Console](https://developers.line.biz/console/).
2. In the console, open the channel:
   - **Basic settings** → **Channel secret** → `LINE_CHANNEL_SECRET`
   - **Messaging API** → issue a **Channel access token (long-lived)** → `LINE_CHANNEL_ACCESS_TOKEN`
3. In LINE Official Account Manager, allow the account to join group chats and turn off auto-reply messages.

### 2. Deploy the web service

Any host that runs a Python web process and offers PostgreSQL works. The repo includes a `Procfile` and `railway.toml` (gunicorn, `/health` check) for [Railway](https://railway.app/):

1. **New Project** → **Deploy from GitHub repo** → pick your copy of this repository.
2. Add a PostgreSQL database to the project. In the bot service's **Variables**, set `DATABASE_URL` to the database's connection URL (on Railway, the reference `${{Postgres.DATABASE_URL}}`), plus `LINE_CHANNEL_SECRET` and `LINE_CHANNEL_ACCESS_TOKEN`.
3. Deploy. Tables are created on startup and `GET /health` returns `OK`.

### 3. Connect the webhook

1. In the console's **Messaging API** tab, set **Webhook URL** to `https://<your-domain>/callback`, click **Verify**, and turn on **Use webhook**.
2. Invite the bot's account into your LINE group and send `/說明`.

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `LINE_CHANNEL_SECRET` | yes | Verifies `X-Line-Signature`; the app refuses to start without it |
| `LINE_CHANNEL_ACCESS_TOKEN` | yes | Sends replies and looks up display names; the app refuses to start without it |
| `DATABASE_URL` | yes | `postgresql://…` in production, or `sqlite:///roster.db` for local runs |
| `PORT` | no | Port for `python app.py` (default 5000) |

See [`.env.example`](.env.example). To test against real LINE from your machine, copy it to `.env`, fill it in, run `python app.py`, and expose port 5000 with a tunnel such as `ngrok http 5000`.

## Development

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

The 67 tests run offline in about a second, with no LINE account, keys, or database server. They cover roster storage (against SQLite), command parsing and permissions, the demo replay, and the webhook: valid, missing, and wrong-secret signatures, a tampered body, and a signed message event processed end to end with the LINE API stubbed. GitHub Actions runs `ruff check .` and `pytest` on Python 3.11 and 3.12 for every push and pull request.

## Tech stack

Python 3.11+, Flask, line-bot-sdk v3, PostgreSQL (psycopg2), gunicorn; SQLite for the demo and tests.
