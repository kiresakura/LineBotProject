"""Webhook 端點：X-Line-Signature 驗證與事件處理（LINE API 呼叫以替身取代）"""

import base64
import hashlib
import hmac
import json

import pytest
from linebot.v3.messaging import TextMessage

from support_bot import web
from support_bot.settings import Settings
from support_bot.web import create_app

CHANNEL_SECRET = 'test-channel-secret'


def sign(body: str, secret: str = CHANNEL_SECRET) -> str:
    """依 LINE 規格計算簽章：base64(HMAC-SHA256(channel secret, body))"""
    digest = hmac.new(secret.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(digest).decode('utf-8')


def text_event_body(text: str, user_id: str = 'U1', event_id: str = '01TESTEVENT', source_type: str = 'user') -> str:
    source = {'type': source_type, 'userId': user_id}
    if source_type == 'group':
        source['groupId'] = 'Cgroup'
    return json.dumps({
        'destination': 'Ubot',
        'events': [{
            'type': 'message',
            'mode': 'active',
            'timestamp': 1700000000000,
            'webhookEventId': event_id,
            'deliveryContext': {'isRedelivery': False},
            'replyToken': 'reply-token-1',
            'source': source,
            'message': {'id': '1', 'type': 'text', 'text': text, 'quoteToken': 'q1'},
        }],
    }, ensure_ascii=False)


EMPTY_BODY = json.dumps({'destination': 'Ubot', 'events': []})


class FakeLineApi:
    """替身：固定顯示名稱，並收集原本要送出的回覆與推播"""

    def __init__(self):
        self.replies = []
        self.pushes = []

    def display_name(self, source):
        return '小明'

    def reply(self, reply_token, message):
        self.replies.append((reply_token, message))

    def push(self, user_id, message):
        self.pushes.append((user_id, message))


def make_settings(**overrides):
    values = {'line_channel_secret': CHANNEL_SECRET, 'line_channel_access_token': 'test-access-token'}
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def line_api():
    return FakeLineApi()


@pytest.fixture
def client(db, line_api):
    return create_app(make_settings(roster_enabled=True), line_api).test_client()


def post_callback(client, body, signature=None):
    headers = {} if signature is None else {'X-Line-Signature': signature}
    return client.post('/callback', data=body, headers=headers)


@pytest.mark.parametrize('missing', ['line_channel_secret', 'line_channel_access_token'])
def test_create_app_requires_line_credentials(db, missing):
    with pytest.raises(ValueError, match='LINE_CHANNEL_SECRET'):
        create_app(make_settings(**{missing: ''}), FakeLineApi())


def test_create_app_reads_settings_from_environment(db, monkeypatch, line_api):
    monkeypatch.setenv('LINE_CHANNEL_SECRET', CHANNEL_SECRET)
    monkeypatch.setenv('LINE_CHANNEL_ACCESS_TOKEN', 'test-access-token')
    client = create_app(line_api=line_api).test_client()
    body = text_event_body('營業到幾點')

    assert post_callback(client, body, sign(body)).status_code == 200
    assert line_api.replies[0][1].text.startswith('週二至週日')


def test_health_check(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.get_data(as_text=True) == 'OK'


def test_callback_accepts_valid_signature(client):
    assert post_callback(client, EMPTY_BODY, sign(EMPTY_BODY)).status_code == 200


def test_callback_rejects_missing_signature(client):
    assert post_callback(client, EMPTY_BODY).status_code == 400


def test_callback_rejects_signature_from_another_secret(client):
    signature = sign(EMPTY_BODY, secret='someone-elses-secret')

    assert post_callback(client, EMPTY_BODY, signature).status_code == 400


def test_callback_rejects_tampered_body(client, line_api):
    original = text_event_body('/我是誰')
    tampered = text_event_body('/刪除 光之勇者')

    response = post_callback(client, tampered, sign(original))

    assert response.status_code == 400
    assert line_api.replies == []


def test_signed_faq_question_gets_answer(client, line_api):
    body = text_event_body('可以帶毛小孩嗎？')

    response = post_callback(client, body, sign(body))

    assert response.status_code == 200
    [(token, message)] = line_api.replies
    assert token == 'reply-token-1'
    assert message.text.startswith('歡迎！寵物')


def test_signed_roster_command_is_processed(client, line_api, db):
    body = text_event_body('/登記 光之勇者')

    post_callback(client, body, sign(body))

    assert line_api.replies[0][1].text.startswith('✅ 登記成功！')
    assert db.get_member_by_user_id('U1')['game_name'] == '光之勇者'


def test_group_chat_without_command_gets_no_reply(client, line_api, db):
    body = text_event_body('大家好', user_id='U2', source_type='group')

    response = post_callback(client, body, sign(body))

    assert response.status_code == 200
    assert line_api.replies == []
    assert db.register_by_admin('小明')['success'] is True


def test_line_push_notifier_uses_push_api(db, line_api):
    settings = make_settings(handoff_notifier='line_push', admin_user_ids=frozenset({'Uadmin'}))
    client = create_app(settings, line_api).test_client()
    body = text_event_body('可以包場嗎')

    post_callback(client, body, sign(body))

    [(user_id, message)] = line_api.pushes
    assert user_id == 'Uadmin'
    assert message.text.startswith('🔔 轉真人 #1｜小明：可以包場嗎')


def test_line_api_push_builds_push_message_request(monkeypatch):
    sent = []

    class FakeMessagingApi:
        def __init__(self, api_client):
            pass

        def push_message(self, push_message_request):
            sent.append(push_message_request)

    monkeypatch.setattr(web, 'MessagingApi', FakeMessagingApi)

    web.LineApi('token').push('Uadmin', TextMessage(text='hi'))

    [request] = sent
    assert request.to == 'Uadmin'
    assert request.messages[0].text == 'hi'
