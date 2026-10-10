"""訊息處理流程：固定回覆 → FAQ → 轉真人、營業時間、管理指令白名單、群組名冊開關"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from support_bot.bot import build_bot
from support_bot.settings import Settings

TAIPEI = ZoneInfo('Asia/Taipei')
OPEN = datetime(2026, 10, 13, 14, 0, tzinfo=TAIPEI)     # 週二下午，營業中
CLOSED = datetime(2026, 10, 13, 22, 30, tzinfo=TAIPEI)  # 週二打烊後


class RecordingNotifier:
    def __init__(self, fail=False):
        self.requests = []
        self.fail = fail

    def notify(self, request):
        if self.fail:
            raise ConnectionError('通知服務暫時無法使用')
        self.requests.append(request)


def make_bot(now=OPEN, notifier=None, **settings):
    bot = build_bot(Settings(**settings), clock=lambda: now)
    bot.notifier = notifier or RecordingNotifier()
    return bot


def test_keyword_reply_comes_before_faq(db):
    assert make_bot().reply('U1', '王小姐', '你好，想看菜單').text.startswith('📋 菜單')


def test_faq_question_is_answered_without_handoff(db):
    bot = make_bot()

    assert bot.reply('U1', '王小姐', '請問營業到幾點？').text.startswith('週二至週日 10:00–20:00')
    assert bot.notifier.requests == []
    assert db.list_open_handoffs() == []


def test_unanswered_question_is_handed_off_during_business_hours(db):
    bot = make_bot()

    reply = bot.reply('U1', '王小姐', '週末可以包場嗎？')

    assert reply.text == bot.rules.handoff_reply
    [request] = db.list_open_handoffs()
    assert (request['display_name'], request['message'], request['created_at']) == (
        '王小姐', '週末可以包場嗎？', '2026-10-13 14:00'
    )
    assert bot.notifier.requests[0]['id'] == request['id']


def test_after_hours_question_gets_after_hours_reply_and_is_recorded(db):
    bot = make_bot(now=CLOSED)

    reply = bot.reply('U2', '陳先生', '我昨天掉了一把傘在店裡')

    assert reply.text == bot.rules.after_hours_reply
    assert db.list_open_handoffs()[0]['created_at'] == '2026-10-13 22:30'


def test_notifier_failure_still_replies_and_keeps_request(db):
    bot = make_bot(notifier=RecordingNotifier(fail=True))

    assert bot.reply('U1', '王小姐', '週末可以包場嗎？').text == bot.rules.handoff_reply
    assert len(db.list_open_handoffs()) == 1


def test_group_messages_are_not_answered_or_handed_off(db):
    bot = make_bot()

    assert bot.reply('U1', '王小姐', '請問營業到幾點？', chat_type='group') is None
    assert bot.reply('U1', '王小姐', '週末可以包場嗎？', chat_type='room') is None
    assert db.list_open_handoffs() == []


def test_admin_commands_are_limited_to_whitelist(db):
    bot = make_bot(admin_user_ids=frozenset({'Uowner'}))
    bot.reply('U1', '王小姐', '週末可以包場嗎？')

    assert bot.reply('U1', '王小姐', '/待處理').text == '❌ 此指令僅限管理員使用'
    assert bot.reply('U1', '王小姐', '/完成 1').text == '❌ 此指令僅限管理員使用'
    assert len(db.list_open_handoffs()) == 1


def test_admin_can_list_and_resolve_handoffs(db):
    bot = make_bot(admin_user_ids=frozenset({'Uowner'}))
    assert bot.reply('Uowner', '店長', '/待處理').text == '✅ 目前沒有待處理的訊息'
    bot.reply('U1', '王小姐', '週末可以包場嗎？')

    listing = bot.reply('Uowner', '店長', '/待處理').text

    assert listing.splitlines() == [
        '📋 待處理 1 筆（由舊到新）',
        '#1 10/13 14:00 王小姐',
        '   週末可以包場嗎？',
        '處理完請回覆 /完成 編號',
    ]
    assert bot.reply('Uowner', '店長', '/完成 #1').text == '✅ 已將 #1 標記為完成'
    assert bot.reply('Uowner', '店長', '/完成 1').text == '❌ 找不到未處理的 #1'
    assert bot.reply('Uowner', '店長', '/完成').text.startswith('❌ 請輸入編號')
    assert db.list_open_handoffs() == []


def test_admin_commands_are_ignored_in_groups(db):
    bot = make_bot(admin_user_ids=frozenset({'Uowner'}))

    assert bot.reply('Uowner', '店長', '/待處理', chat_type='group') is None


def test_roster_is_disabled_by_default(db):
    bot = make_bot()

    assert bot.reply('U1', '小明', '/登記 光之勇者', chat_type='group') is None
    assert db.get_member_by_user_id('U1') is None


def test_roster_commands_work_when_enabled(db):
    bot = make_bot(roster_enabled=True)

    assert bot.reply('U1', '小明', '/登記 光之勇者', chat_type='group').text.startswith('✅ 登記成功！')
    assert db.get_member_by_user_id('U1')['game_name'] == '光之勇者'


def test_whitelisted_admin_is_a_roster_officer(db):
    bot = make_bot(roster_enabled=True, admin_user_ids=frozenset({'Uowner'}))
    db.register_member('U1', '小明', '光之勇者')

    reply = bot.reply('Uowner', '店長', '/名冊', chat_type='group')

    assert reply.alt_text == '成員名冊 - 第 1/1 頁，共 1 人'


@pytest.mark.parametrize('settings, message', [
    ({'handoff_notifier': 'line_push'}, 'ADMIN_USER_IDS'),
    ({'handoff_notifier': 'email'}, 'log 或 line_push'),
])
def test_build_bot_rejects_invalid_notifier_settings(settings, message):
    with pytest.raises(ValueError, match=message):
        build_bot(Settings(**settings))
