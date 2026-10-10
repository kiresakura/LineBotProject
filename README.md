# LINE Customer Service Bot Template

[![CI](https://github.com/kiresakura/LineBotProject/actions/workflows/ci.yml/badge.svg)](https://github.com/kiresakura/LineBotProject/actions/workflows/ci.yml)

**A LINE Official Account bot for small businesses: it answers common questions from a YAML file, knows your opening hours, and hands anything it can't answer to a human.**

[繁體中文說明](README.zh-TW.md)

> This is a template / showcase version built around a **fictional** café (小島咖啡). Replace the two YAML files with your own content, or have it customized for your shop, cram school, or community. There is no public running instance.

## 30-second demo (no LINE account needed)

```bash
git clone https://github.com/kiresakura/LineBotProject.git
cd LineBotProject
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m support_bot.demo
```

The demo replays [`examples/demo-shop.txt`](examples/demo-shop.txt) through the same code the webhook uses (local SQLite, simulated clock). Excerpt of the real output:

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

Try your own messages with `python -m support_bot.demo --interactive`, or the group roster module with `python -m support_bot.demo examples/demo-group.txt`.

## Who it's for

- **Shops, cafés, salons** – answer opening hours, location, parking, and payment questions instantly; send the menu link or current promotion by keyword.
- **Cram schools and studios** – class times, fees, and enrollment FAQs; questions about a specific student go to staff.
- **Community organizers** – the optional group roster lets members register a name and officers manage the list inside the LINE group.

## Features

| | What it does | Where to change it |
|---|---|---|
| **FAQ auto-reply** | Matches keywords (longest/most matches win), synonyms (`毛小孩` → `寵物`), and messages that closely resemble a listed question | `config/faq.yaml` |
| **Hours and rules** | Weekly opening hours (several periods per day, overnight periods), closed dates, fixed replies for keywords such as `菜單` or `優惠` | `config/rules.yaml` |
| **Human handoff** | Unanswered questions get "已通知專人" (or the after-hours message), are saved to a pending list, and trigger a notification | `config/rules.yaml`, `HANDOFF_NOTIFIER` |
| **Admin commands** | `/待處理` lists pending questions, `/完成 <id>` closes one; only for LINE user IDs in `ADMIN_USER_IDS`, only in one-on-one chat | `ADMIN_USER_IDS` |
| **Group roster** (optional) | Members link their LINE name to a registered name; officers search, list, and manage members | `ROSTER_ENABLED=true` |
| **AI answers** (optional, off) | Any OpenAI-compatible API answers from the FAQ only and must cite the FAQ entries it used; otherwise the question goes to a human | `AI_ENABLED=true` |

Notifications are a small interface: the default writes a log line (visible in your hosting platform's logs); `HANDOFF_NOTIFIER=line_push` pushes the request to every admin's LINE account instead. LINE Notify was discontinued on 2025-03-31, and push messages are the usual replacement – they count toward your official account's monthly message quota.

### Security and reliability

- Requests to `/callback` are rejected with HTTP 400 unless `X-Line-Signature` matches the HMAC-SHA256 of the body under your channel secret.
- Each `webhookEventId` is processed once, so LINE redeliveries don't produce duplicate replies or duplicate handoffs. If the bot fails before it has produced a reply (including a worker timeout), the event is released so a redelivery can retry it.
- All secrets and settings come from environment variables; the app refuses to start when the LINE credentials are missing, a YAML file is invalid, or the notifier or AI settings are incomplete.
- In group chats the bot only reacts to roster commands, so it never floods a group with FAQ answers or handoff messages.

## How a message is handled

```text
one-on-one chat:  admin command → roster command (if enabled) → keyword reply → FAQ → AI (if enabled) → hand off to a human
group / room:     roster command (if enabled) → otherwise no reply
```

## Customize it

1. **Edit `config/faq.yaml`** – each entry has an `id`, the `question`, `keywords`, and the `answer`; add customer phrasings under `synonyms`; mark small talk such as greetings `standalone: true` so "hello, I want to cancel my order" is not answered with a greeting.
2. **Edit `config/rules.yaml`** – `business_hours`, `closed_dates`, the handoff and after-hours replies, and `keyword_replies`.
3. **Check your changes offline** – `python -m support_bot.demo --interactive` uses the same files (or pass `--faq` / `--rules` to try another copy). Bad YAML stops the app at startup with the file name and the problem.

Typical customizations on request: your own FAQ and tone, a rich menu, a reply-to-customer command, a dashboard for the pending list, or another notification channel.

## Deploy your own

### 1. Create the LINE channel

1. Create a LINE Official Account and enable the Messaging API for it (LINE Official Account Manager → Settings → Messaging API). The channel then appears in the [LINE Developers Console](https://developers.line.biz/console/).
2. In the console, open the channel:
   - **Basic settings** → **Channel secret** → `LINE_CHANNEL_SECRET`; **Your user ID** → put it in `ADMIN_USER_IDS`
   - **Messaging API** → issue a **Channel access token (long-lived)** → `LINE_CHANNEL_ACCESS_TOKEN`
3. In LINE Official Account Manager, turn off the built-in auto-reply messages so they don't answer alongside the bot (and allow group chats if you use the roster).

### 2. Run the server

**Docker (any VPS):**

```bash
cp .env.example .env        # fill in the LINE values
docker compose up -d --build                        # SQLite, stored in the bot-data volume
docker compose --profile postgres up -d --build     # or with PostgreSQL: set DATABASE_URL=postgresql://bot:bot@postgres:5432/bot in .env
```

The bot listens on port 8000; put it behind HTTPS (for example a reverse proxy), because LINE only calls `https://` webhooks. With the `postgres` profile the bot may restart a few times on the first start until the database is ready (`restart: unless-stopped`).

**Render:** New → Web Service → connect your copy of this repository → choose the Docker runtime (it builds the `Dockerfile`) → add the environment variables → deploy. Render's filesystem is ephemeral unless you attach a disk, so use a PostgreSQL database (`DATABASE_URL`) to keep the pending list and roster.

**Railway:** New Project → Deploy from GitHub repo. `railway.toml` sets the gunicorn start command and the `/health` check. Add a PostgreSQL database, set `DATABASE_URL` to `${{Postgres.DATABASE_URL}}`, and add the LINE variables.

### 3. Connect the webhook

In the console's **Messaging API** tab, set **Webhook URL** to `https://<your-domain>/callback`, click **Verify**, and turn on **Use webhook**. Then message your official account.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `LINE_CHANNEL_SECRET` | – (required) | Verifies `X-Line-Signature` |
| `LINE_CHANNEL_ACCESS_TOKEN` | – (required) | Sends replies, reads display names, pushes notifications |
| `DATABASE_URL` | `sqlite:///bot.db` | `postgresql://…` or `sqlite:///file.db`; the Docker image uses `/app/data/bot.db` |
| `ADMIN_USER_IDS` | empty | Comma-separated LINE user IDs allowed to run admin commands |
| `HANDOFF_NOTIFIER` | `log` | `log` or `line_push` (needs `ADMIN_USER_IDS`) |
| `FAQ_FILE`, `RULES_FILE` | `config/faq.yaml`, `config/rules.yaml` | Content files |
| `ROSTER_ENABLED` | `false` | Turns on the group roster commands |
| `AI_ENABLED` | `false` | Turns on AI answers; customer messages are then sent to the API below |
| `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL` | `https://api.openai.com/v1`, empty, empty | OpenAI-compatible endpoint; `AI_MODEL` is required when AI is on |
| `PORT` | 5000 (`python -m support_bot.web`), 8000 (Docker) | Listening port |

See [`.env.example`](.env.example) for the same list with comments.

## Group roster module

With `ROSTER_ENABLED=true` the original roster commands work in groups and one-on-one chats: `/登記 <name>`, `/修改`, `/查詢`, `/我是誰`, `/幹部`, `/說明`, `/選單`, and for officers `/名冊 [page|全部]`, `/代登記`, `/刪除`, `/設定管理員`. Admins in `ADMIN_USER_IDS` are always officers; when the whitelist is empty, the first registered member who sends `/設定管理員` becomes the first officer. Each deployment keeps one roster (members are not separated by group).

## Architecture

```text
LINE platform ── POST /callback ──▶ web.py      verify signature, skip redelivered events, call the LINE API
                                      │
demo.py (terminal) ─────────────────▶ bot.py      admin commands → roster → keyword reply → FAQ → AI → handoff
                                      ├── rules.py / faq.py    read config/*.yaml, opening hours, matching
                                      ├── ai.py                optional OpenAI-compatible client (standard library only)
                                      ├── handoff.py           notifiers: log, LINE push
                                      ├── roster.py            optional group roster commands (+ roster_messages.py)
                                      └── database.py          SQLite or PostgreSQL: pending list, processed events, roster
```

## Development

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

The 173 tests run offline in about a second, with no LINE account, keys, network, or database server: FAQ matching, opening hours (including overnight periods and closed dates), the full reply pipeline, handoff and notifiers, admin whitelist, roster commands, webhook signature checks and duplicate events, the AI path with a fake model, and both demo scripts. GitHub Actions runs `ruff` and `pytest` on Python 3.11 and 3.12, runs the same tests against PostgreSQL 17 (set `TEST_DATABASE_URL` to do this locally), and builds the Docker image and checks `/health` on the running container.

Tech stack: Python 3.11+, Flask, line-bot-sdk v3, PyYAML, gunicorn, SQLite or PostgreSQL (psycopg2).

---

Customization: https://www.tasker.com.tw/workroom/crimson
