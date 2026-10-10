FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DATABASE_URL=sqlite:////app/data/bot.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY support_bot ./support_bot
COPY config ./config

# 以非 root 使用者執行；SQLite 資料放在 /app/data（docker compose 會掛成 volume）
RUN useradd --create-home bot && mkdir -p /app/data && chown bot /app/data
USER bot

EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn 'support_bot.web:create_app()' --bind 0.0.0.0:${PORT}"]
