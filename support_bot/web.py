"""
LINE Webhook 伺服器：驗證 X-Line-Signature，把文字訊息交給 SupportBot 並回覆
這是唯一呼叫 LINE Messaging API 的模組

啟動：gunicorn 'support_bot.web:create_app()'（本機也可以 python -m support_bot.web）
"""

import logging
import os
import time

from dotenv import load_dotenv
from flask import Flask, abort, request
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from support_bot import database as db
from support_bot.bot import build_bot
from support_bot.settings import Settings

logger = logging.getLogger(__name__)


class LineApi:
    """Messaging API 呼叫（測試時換成替身）"""

    def __init__(self, access_token: str):
        self.configuration = Configuration(access_token=access_token)

    def display_name(self, source) -> str:
        """取得發言者的顯示名稱；群組與多人聊天室要用對應的 API"""
        try:
            with ApiClient(self.configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                if source.type == 'group':
                    profile = line_bot_api.get_group_member_profile(group_id=source.group_id, user_id=source.user_id)
                elif source.type == 'room':
                    profile = line_bot_api.get_room_member_profile(room_id=source.room_id, user_id=source.user_id)
                else:
                    profile = line_bot_api.get_profile(user_id=source.user_id)
                return profile.display_name
        except Exception as e:
            logger.warning('無法取得使用者名稱: %s', e)
            return '未知使用者'

    def reply(self, reply_token: str, message) -> None:
        with ApiClient(self.configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=[message])
            )

    def push(self, user_id: str, message) -> None:
        with ApiClient(self.configuration) as api_client:
            MessagingApi(api_client).push_message(
                PushMessageRequest(to=user_id, messages=[message])
            )


def create_app(settings: Settings = None, line_api=None) -> Flask:
    """建立 Flask 應用程式；缺少必要設定時丟出 ValueError，避免帶著錯誤設定上線"""
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    settings = settings or Settings.from_env()
    if not settings.line_channel_secret or not settings.line_channel_access_token:
        raise ValueError("請設定 LINE_CHANNEL_SECRET 和 LINE_CHANNEL_ACCESS_TOKEN 環境變數")

    line_api = line_api or LineApi(settings.line_channel_access_token)
    bot = build_bot(settings, push=line_api.push)
    db.init_db()

    handler = WebhookHandler(settings.line_channel_secret)
    app = Flask(__name__)

    @app.route('/health', methods=['GET'])
    def health_check():
        """健康檢查端點"""
        return 'OK', 200

    @app.route('/callback', methods=['POST'])
    def callback():
        """LINE Webhook 回調端點：簽章不符一律回 400"""
        signature = request.headers.get('X-Line-Signature', '')
        body = request.get_data(as_text=True)

        try:
            handler.handle(body, signature)
        except InvalidSignatureError:
            abort(400)

        return 'OK'

    @handler.add(MessageEvent, message=TextMessageContent)
    def handle_message(event: MessageEvent):
        """處理文字訊息；同一個 webhookEventId 只處理一次（LINE 重送時不重複回覆、不重複轉真人）"""
        if not db.mark_event_processed(event.webhook_event_id, int(time.time())):
            logger.info('略過已處理的事件 %s', event.webhook_event_id)
            return

        # 產生回覆（含轉真人）途中失敗才釋放事件，讓 LINE 重送時再處理一次；
        # 用 finally 讓 gunicorn 逾時（SystemExit）也會釋放。回覆已產生後才失敗則不釋放，避免重複轉真人
        handled = False
        try:
            source = event.source
            display_name = line_api.display_name(source)
            reply_message = bot.reply(source.user_id, display_name, event.message.text, chat_type=source.type)
            handled = True
        finally:
            if not handled:
                db.forget_event(event.webhook_event_id)

        if reply_message:
            line_api.reply(event.reply_token, reply_message)

    return app


def main():
    """本機啟動：python -m support_bot.web（先由 create_app() 讀 .env，.env 裡的 PORT 才會生效）"""
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)


if __name__ == '__main__':
    main()
