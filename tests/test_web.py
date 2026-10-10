"""Webhook 端點：X-Line-Signature 驗證與事件處理（LINE API 呼叫以替身取代）"""

import base64
import hashlib
import hmac
import json
import time

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


@pytest.fixture(autouse=True)
def ignore_local_dotenv(monkeypatch):
    """create_app() 會讀 .env；測試不受開發者本機 .env 影響（例如其中開了 AI 而打到網路）"""
    calls = []
    monkeypatch.setattr(web, 'load_dotenv', lambda *args, **kwargs: calls.append(args) or False)
    return calls


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


def test_redelivered_event_is_processed_once(client, line_api, db):
    body = text_event_body('週末可以包場嗎？', event_id='01SAMEEVENT')

    first = post_callback(client, body, sign(body))
    second = post_callback(client, body, sign(body))

    assert (first.status_code, second.status_code) == (200, 200)
    assert len(line_api.replies) == 1
    assert len(db.list_open_handoffs()) == 1


def test_different_events_are_both_processed(client, line_api):
    for event_id in ['01EVENTA', '01EVENTB']:
        body = text_event_body('營業到幾點', event_id=event_id)
        post_callback(client, body, sign(body))

    assert len(line_api.replies) == 2


class FlakyLineApi(FakeLineApi):
    """第一次呼叫指定的方法時丟出例外，之後恢復正常"""

    def __init__(self, failing_method, error=ConnectionError('LINE API 暫時無法連線')):
        super().__init__()
        self.failing_method = failing_method
        self.error = error

    def _maybe_fail(self, method):
        if self.failing_method == method:
            self.failing_method = None
            raise self.error

    def display_name(self, source):
        self._maybe_fail('display_name')
        return super().display_name(source)

    def reply(self, reply_token, message):
        self._maybe_fail('reply')
        super().reply(reply_token, message)


def flaky_client(flaky):
    client = create_app(make_settings(), flaky).test_client()
    client.application.config['PROPAGATE_EXCEPTIONS'] = False
    return client


def test_failure_before_replying_lets_redelivery_retry(db):
    flaky = FlakyLineApi('display_name')
    client = flaky_client(flaky)
    body = text_event_body('營業到幾點', event_id='01FLAKY')

    assert post_callback(client, body, sign(body)).status_code == 500
    assert post_callback(client, body, sign(body)).status_code == 200
    assert len(flaky.replies) == 1


def test_reply_failure_does_not_repeat_handoff_on_redelivery(db):
    flaky = FlakyLineApi('reply')
    client = flaky_client(flaky)
    body = text_event_body('週末可以包場嗎？', event_id='01REPLYFAIL')

    assert post_callback(client, body, sign(body)).status_code == 500
    assert post_callback(client, body, sign(body)).status_code == 200

    assert len(db.list_open_handoffs()) == 1
    assert flaky.replies == []


def test_worker_timeout_releases_event(db):
    # gunicorn 逾時會在 worker 裡丟出 SystemExit，不是 Exception
    flaky = FlakyLineApi('display_name', error=SystemExit(1))
    client = flaky_client(flaky)
    body = text_event_body('營業到幾點', event_id='01TIMEOUT')

    with pytest.raises(SystemExit):
        post_callback(client, body, sign(body))

    assert db.mark_event_processed('01TIMEOUT', now=int(time.time())) is True


def test_mark_event_processed_prunes_old_records(db):
    assert db.mark_event_processed('old', now=1_000) is True
    assert db.mark_event_processed('old', now=2_000) is False

    # 超過保留期限的紀錄會被清掉
    assert db.mark_event_processed('new', now=1_000 + 8 * 24 * 3600) is True
    assert db.mark_event_processed('old', now=1_000 + 8 * 24 * 3600) is True


def test_create_app_loads_dotenv_before_reading_settings(db, ignore_local_dotenv, line_api):
    create_app(make_settings(), line_api)

    assert len(ignore_local_dotenv) == 1


def test_main_reads_port_after_loading_dotenv(db, monkeypatch):
    # PORT 寫在 .env 時，python -m support_bot.web 也要用它
    monkeypatch.setenv('LINE_CHANNEL_SECRET', CHANNEL_SECRET)
    monkeypatch.setenv('LINE_CHANNEL_ACCESS_TOKEN', 'test-access-token')
    monkeypatch.delenv('PORT', raising=False)
    monkeypatch.setattr(web, 'load_dotenv', lambda *args, **kwargs: monkeypatch.setenv('PORT', '5123'))
    monkeypatch.setattr(web, 'LineApi', lambda access_token: FakeLineApi())
    ran = {}
    monkeypatch.setattr(web.Flask, 'run', lambda self, host, port, debug: ran.update(host=host, port=port))

    web.main()

    assert ran == {'host': '0.0.0.0', 'port': 5123}
