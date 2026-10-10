"""
轉真人的通知管道（介面：notify(request)，request 為 handoff_requests 的一筆資料）
- LogNotifier：預設；寫一筆 WARNING log，部署平台的 log 頁面就看得到
- LinePushNotifier：用 Messaging API 的 push message 推播給管理員的 LINE 帳號
  LINE Notify 已於 2025-03-31 停止服務，這是常見的替代做法；push message 會計入官方帳號的每月訊息則數
"""

import logging

from linebot.v3.messaging import TextMessage

logger = logging.getLogger(__name__)


def describe(request: dict) -> str:
    return f"轉真人 #{request['id']}｜{request['display_name']}：{request['message']}"


class LogNotifier:
    def notify(self, request: dict) -> None:
        logger.warning(describe(request))


class LinePushNotifier:
    def __init__(self, push, admin_user_ids):
        # push(user_id, message)：實際呼叫 Messaging API 的函式，由 web.py 提供；測試時換成替身
        self.push = push
        self.admin_user_ids = sorted(admin_user_ids)

    def notify(self, request: dict) -> None:
        message = TextMessage(text=f"🔔 {describe(request)}\n\n處理完請回覆 /完成 {request['id']}")
        for user_id in self.admin_user_ids:
            self.push(user_id, message)
