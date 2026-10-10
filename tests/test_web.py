"""Webhook 端點：X-Line-Signature 驗證與事件處理（LINE API 呼叫以替身取代）"""

import base64
import hashlib
import hmac
import importlib
import json
import sys

import pytest

CHANNEL_SECRET = 'test-channel-secret'


def sign(body: str, secret: str = CHANNEL_SECRET) -> str:
    """依 LINE 規格計算簽章：base64(HMAC-SHA256(channel secret, body))"""
    digest = hmac.new(secret.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(digest).decode('utf-8')


def text_event_body(text: str, user_id: str = 'U1') -> str:
    return json.dumps({
        'destination': 'Ubot',
        'events': [{
            'type': 'message',
            'mode': 'active',
            'timestamp': 1700000000000,
            'webhookEventId': '01TESTEVENT',
            'deliveryContext': {'isRedelivery': False},
            'replyToken': 'reply-token-1',
            'source': {'type': 'group', 'groupId': 'Cgroup', 'userId': user_id},
            'message': {'id': '1', 'type': 'text', 'text': text, 'quoteToken': 'q1'},
        }],
    }, ensure_ascii=False)


EMPTY_BODY = json.dumps({'destination': 'Ubot', 'events': []})


def import_app():
    sys.modules.pop('support_bot.web', None)
    return importlib.import_module('support_bot.web')


@pytest.fixture
def app_module(monkeypatch, tmp_path):
    monkeypatch.setenv('LINE_CHANNEL_SECRET', CHANNEL_SECRET)
    monkeypatch.setenv('LINE_CHANNEL_ACCESS_TOKEN', 'test-access-token')
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path / "roster.db"}')
    module = import_app()
    yield module
    sys.modules.pop('support_bot.web', None)


@pytest.fixture
def replies(app_module, monkeypatch):
    """以替身取代 LINE API：固定顯示名稱，並收集原本要送出的回覆"""
    sent = []
    monkeypatch.setattr(app_module, 'get_user_display_name', lambda user_id, source: '小明')
    monkeypatch.setattr(app_module, 'send_reply', lambda token, message: sent.append((token, message)))
    return sent


def post_callback(app_module, body, signature=None):
    headers = {} if signature is None else {'X-Line-Signature': signature}
    return app_module.app.test_client().post('/callback', data=body, headers=headers)


def test_app_requires_line_credentials(monkeypatch):
    monkeypatch.delenv('LINE_CHANNEL_SECRET', raising=False)
    monkeypatch.delenv('LINE_CHANNEL_ACCESS_TOKEN', raising=False)
    monkeypatch.setattr('dotenv.load_dotenv', lambda *args, **kwargs: False)

    with pytest.raises(ValueError):
        import_app()


def test_health_check(app_module):
    response = app_module.app.test_client().get('/health')

    assert response.status_code == 200
    assert response.get_data(as_text=True) == 'OK'


def test_callback_accepts_valid_signature(app_module):
    assert post_callback(app_module, EMPTY_BODY, sign(EMPTY_BODY)).status_code == 200


def test_callback_rejects_missing_signature(app_module):
    assert post_callback(app_module, EMPTY_BODY).status_code == 400


def test_callback_rejects_signature_from_another_secret(app_module):
    signature = sign(EMPTY_BODY, secret='someone-elses-secret')

    assert post_callback(app_module, EMPTY_BODY, signature).status_code == 400


def test_callback_rejects_tampered_body(app_module, replies):
    original = text_event_body('/我是誰')
    tampered = text_event_body('/刪除 光之勇者')

    response = post_callback(app_module, tampered, sign(original))

    assert response.status_code == 400
    assert replies == []


def test_signed_text_event_is_processed_and_replied(app_module, replies):
    body = text_event_body('/登記 光之勇者')

    response = post_callback(app_module, body, sign(body))

    assert response.status_code == 200
    [(token, message)] = replies
    assert token == 'reply-token-1'
    assert message.text.startswith('✅ 登記成功！')
    assert app_module.db.get_member_by_user_id('U1')['game_name'] == '光之勇者'


def test_plain_chat_is_recorded_without_reply(app_module, replies):
    body = text_event_body('大家好', user_id='U2')

    response = post_callback(app_module, body, sign(body))

    assert response.status_code == 200
    assert replies == []
    assert app_module.db.register_by_admin('小明')['success'] is True
