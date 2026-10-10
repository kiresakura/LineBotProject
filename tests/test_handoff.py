"""轉真人：待處理清單的資料層與通知管道（不呼叫 LINE API）"""

import logging

from support_bot.handoff import LinePushNotifier, LogNotifier


def test_create_and_list_open_handoffs(db):
    first = db.create_handoff('U1', '王小姐', '可以包場嗎？', '2026-10-13 14:05')
    second = db.create_handoff('U2', '陳先生', '我掉了一把傘', '2026-10-13 22:30')

    assert (first['id'], first['status']) == (1, 'open')
    assert second['id'] == 2
    assert [(r['id'], r['display_name'], r['message']) for r in db.list_open_handoffs()] == [
        (1, '王小姐', '可以包場嗎？'),
        (2, '陳先生', '我掉了一把傘'),
    ]


def test_resolve_handoff_only_once(db):
    request = db.create_handoff('U1', '王小姐', '可以包場嗎？', '2026-10-13 14:05')

    assert db.resolve_handoff(request['id']) is True
    assert db.resolve_handoff(request['id']) is False
    assert db.resolve_handoff(999) is False
    assert db.list_open_handoffs() == []


def test_list_open_handoffs_respects_limit(db):
    for i in range(3):
        db.create_handoff(f'U{i}', f'客人{i}', f'問題{i}', '2026-10-13 14:00')

    assert [r['id'] for r in db.list_open_handoffs(limit=2)] == [1, 2]


REQUEST = {'id': 7, 'display_name': '王小姐', 'message': '可以包場嗎？'}


def test_log_notifier_writes_a_warning(caplog):
    with caplog.at_level(logging.WARNING, logger='support_bot.handoff'):
        LogNotifier().notify(REQUEST)

    assert caplog.messages == ['轉真人 #7｜王小姐：可以包場嗎？']


def test_line_push_notifier_pushes_to_every_admin():
    pushed = []
    notifier = LinePushNotifier(lambda user_id, message: pushed.append((user_id, message.text)), {'Uadmin2', 'Uadmin1'})

    notifier.notify(REQUEST)

    text = '🔔 轉真人 #7｜王小姐：可以包場嗎？\n\n處理完請回覆 /完成 7'
    assert pushed == [('Uadmin1', text), ('Uadmin2', text)]
