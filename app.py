import os
from flask import Flask, request, abort
from dotenv import load_dotenv

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)
from linebot.v3.exceptions import InvalidSignatureError

import database as db
from handlers import process_command

# 載入環境變數
load_dotenv()

app = Flask(__name__)

# LINE Bot 設定
channel_secret = os.environ.get('LINE_CHANNEL_SECRET')
channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')

if not channel_secret or not channel_access_token:
    raise ValueError("請設定 LINE_CHANNEL_SECRET 和 LINE_CHANNEL_ACCESS_TOKEN 環境變數")

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)


@app.route('/health', methods=['GET'])
def health_check():
    """健康檢查端點"""
    return 'OK', 200


@app.route('/callback', methods=['POST'])
def callback():
    """LINE Webhook 回調端點"""
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    """處理文字訊息"""
    text = event.message.text
    user_id = event.source.user_id

    # 取得使用者顯示名稱
    display_name = get_user_display_name(user_id, event.source)

    # 處理指令
    reply_message = process_command(user_id, display_name, text)

    if reply_message:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[reply_message]
                )
            )


def get_user_display_name(user_id: str, source) -> str:
    """取得使用者的顯示名稱"""
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            # 根據來源類型取得 profile
            source_type = source.type

            if source_type == 'group':
                profile = line_bot_api.get_group_member_profile(
                    group_id=source.group_id,
                    user_id=user_id
                )
            elif source_type == 'room':
                profile = line_bot_api.get_room_member_profile(
                    room_id=source.room_id,
                    user_id=user_id
                )
            else:
                profile = line_bot_api.get_profile(user_id=user_id)

            return profile.display_name
    except Exception as e:
        print(f"無法取得使用者名稱: {e}")
        return "未知使用者"


# 初始化資料庫
def init_app():
    """應用程式初始化"""
    try:
        db.init_db()
        print("應用程式初始化完成")
    except Exception as e:
        print(f"資料庫初始化失敗: {e}")
        raise


# 啟動時初始化
init_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
