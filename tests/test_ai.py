"""選配 AI 回答：一律用假模型與假連線，不打網路、不需要金鑰"""

import io
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from support_bot import ai
from support_bot.ai import NO_ANSWER, AiAnswerer, OpenAICompatibleClient
from support_bot.bot import build_bot
from support_bot.faq import load_faq
from support_bot.settings import Settings

EXAMPLE_FAQ = Path(__file__).resolve().parent.parent / 'config' / 'faq.yaml'
OPEN = datetime(2026, 10, 13, 14, 0, tzinfo=ZoneInfo('Asia/Taipei'))


class FakeModel:
    """假模型：回傳固定內容，並記錄收到的訊息"""

    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.content


@pytest.fixture(scope='module')
def faq():
    return load_faq(EXAMPLE_FAQ)


def test_answer_cites_faq_sources(faq):
    model = FakeModel('週一公休，週二到週日都有營業。[source:hours]')

    reply = AiAnswerer(model, faq).answer('禮拜一有開嗎')

    assert reply == '週一公休，週二到週日都有營業。\n\n📖 出處：常見問題「營業時間是幾點到幾點？」（AI 依常見問題整理）'


def test_prompt_contains_only_faq_data_and_the_question(faq):
    model = FakeModel('可以。[source:pets]')

    AiAnswerer(model, faq).answer('可以帶兔子嗎')

    [messages] = model.calls
    assert messages[0]['role'] == 'system' and NO_ANSWER in messages[0]['content']
    assert '[pets]\n問：可以帶寵物嗎？' in messages[1]['content']
    assert messages[1]['content'].endswith('顧客的問題：可以帶兔子嗎')


@pytest.mark.parametrize('content', [
    NO_ANSWER,
    '我們有賣蛋糕。',                     # 沒有標註出處
    '我們有賣蛋糕。[source:cakes]',       # 標註了不存在的出處
    '可以。[source:pets][source:cakes]',  # 部分出處不存在
    '[source:pets]',                      # 只有出處、沒有內容
])
def test_unsupported_answers_are_rejected(faq, content):
    assert AiAnswerer(FakeModel(content), faq).answer('可以包場嗎') is None


def test_model_errors_fall_back_to_handoff(faq):
    assert AiAnswerer(FakeModel(error=TimeoutError('timeout')), faq).answer('可以包場嗎') is None


def test_empty_model_content_falls_back_to_handoff(faq):
    # 有些 API 在拒答或只回傳工具呼叫時，content 會是 null
    assert AiAnswerer(FakeModel(content=None), faq).answer('可以包場嗎') is None


def test_bot_uses_ai_after_faq_and_before_handoff(db):
    bot = build_bot(Settings(ai_enabled=True, ai_model='fake-model'), clock=lambda: OPEN)
    model = FakeModel('寵物請使用牽繩。[source:pets]')
    bot.answerer.client = model

    assert bot.reply('U1', '王小姐', '營業到幾點').text.startswith('週二至週日')   # FAQ 先回答，不呼叫 AI
    assert model.calls == []

    assert bot.reply('U1', '王小姐', '兔子可以進店嗎').text.startswith('寵物請使用牽繩。')
    assert db.list_open_handoffs() == []

    model.content = NO_ANSWER
    assert bot.reply('U1', '王小姐', '可以包場嗎').text == bot.rules.handoff_reply
    assert len(db.list_open_handoffs()) == 1


def test_ai_is_disabled_by_default():
    assert build_bot(Settings()).answerer is None


def test_ai_requires_model_name():
    with pytest.raises(ValueError, match='AI_MODEL'):
        build_bot(Settings(ai_enabled=True))


def test_client_posts_chat_completion_request(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured.update(url=request.full_url, headers=dict(request.header_items()), timeout=timeout,
                        body=json.loads(request.data))
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': '答案 [source:hours]'}}]}).encode())

    monkeypatch.setattr(ai.urllib.request, 'urlopen', fake_urlopen)
    client = OpenAICompatibleClient('https://llm.example.com/v1/', 'test-key', 'test-model', timeout=5)

    content = client.complete([{'role': 'user', 'content': '你好'}])

    assert content == '答案 [source:hours]'
    assert captured['url'] == 'https://llm.example.com/v1/chat/completions'
    assert captured['headers']['Authorization'] == 'Bearer test-key'
    assert captured['timeout'] == 5
    # 不指定 temperature 等取樣參數：有些模型只接受預設值，指定了會回 400
    assert captured['body'] == {'model': 'test-model', 'messages': [{'role': 'user', 'content': '你好'}]}


def test_client_omits_authorization_without_key(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured['headers'] = dict(request.header_items())
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': NO_ANSWER}}]}).encode())

    monkeypatch.setattr(ai.urllib.request, 'urlopen', fake_urlopen)

    OpenAICompatibleClient('http://localhost:11434/v1', '', 'local-model').complete([])

    assert 'Authorization' not in captured['headers']
