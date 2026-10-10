"""指令解析與路由（不需要 LINE 帳號或網路）"""

import pytest
from linebot.v3.messaging import FlexMessage, TextMessage

from support_bot.roster import (
    handle_text,
    parse_command,
    parse_register_for_args,
    parse_roster_args,
    process_command,
)


@pytest.mark.parametrize('text, expected', [
    ('/登記 光之勇者', ('/登記', '光之勇者')),
    ('  /HELP  ', ('/help', '')),
    ('/代登記 小明   勇者123 幹部', ('/代登記', '小明   勇者123 幹部')),
    ('大家好', None),
    ('', None),
])
def test_parse_command(text, expected):
    assert parse_command(text) == expected


@pytest.mark.parametrize('args, expected', [
    ('', (False, 1)),
    ('2', (False, 2)),
    (' 3 ', (False, 3)),
    ('abc', (False, 1)),
    ('全部', (True, 1)),
    ('all', (True, 1)),
])
def test_parse_roster_args(args, expected):
    assert parse_roster_args(args) == expected


@pytest.mark.parametrize('args, expected', [
    ('小明', ('小明', None, False)),
    ('小明 幹部', ('小明', None, True)),
    ('小明 admin', ('小明', None, True)),
    ('小明 勇者123', ('小明', '勇者123', False)),
    ('小明 勇者123 幹部', ('小明', '勇者123', True)),
    ('小明 勇者123 其他', ('小明', '勇者123', False)),
    ('', None),
])
def test_parse_register_for_args(args, expected):
    assert parse_register_for_args(args) == expected


def make_admin(db, user_id='U-admin', name='會長', game_name='公會長'):
    db.register_member(user_id, name, game_name)
    db.set_admin(game_name)
    return user_id


def test_non_command_and_unknown_command_get_no_reply(db):
    assert process_command('U1', '小明', '早安') is None
    assert process_command('U1', '小明', '/不存在的指令') is None


def test_command_without_args_shows_input_prompt(db):
    reply = process_command('U1', '小明', '/登記')

    assert isinstance(reply, FlexMessage)
    assert reply.alt_text == '請輸入你的遊戲角色名稱'


def test_register_command_replies_with_quick_actions(db):
    reply = process_command('U1', '小明', '/登記 光之勇者')

    assert isinstance(reply, TextMessage)
    assert reply.text.startswith('✅ 登記成功！')
    assert [item.action.text for item in reply.quick_reply.items] == ['/名冊', '/我是誰']
    assert db.get_member_by_user_id('U1')['game_name'] == '光之勇者'


def test_register_command_rejects_overlong_name(db):
    reply = process_command('U1', '小明', '/登記 ' + '長' * 101)

    assert reply.text.startswith('❌ 遊戲名稱過長')
    assert db.get_member_by_user_id('U1') is None


def test_update_command(db):
    process_command('U1', '小明', '/登記 光之勇者')

    reply = process_command('U1', '小明', '/修改 暗黑騎士')

    assert reply.text.startswith('✅ 修改成功！')
    assert db.get_member_by_user_id('U1')['game_name'] == '暗黑騎士'


def test_search_command_returns_flex_result(db):
    db.register_member('U1', '小明', '光之勇者')

    reply = process_command('U2', '小華', '/查詢 勇者')

    assert isinstance(reply, FlexMessage)
    assert '找到 1 筆結果' in str(reply.contents.to_dict())


def test_admin_only_commands_are_denied_for_members(db):
    db.register_member('U1', '小明', '光之勇者')
    make_admin(db)

    for text in ['/名冊', '/刪除 光之勇者', '/代登記 小華', '/設定管理員 光之勇者']:
        reply = process_command('U1', '小明', text)
        assert reply.text.startswith('❌ 此指令僅限'), text

    assert db.get_member_by_user_id('U1') is not None


def test_first_registered_user_can_become_admin(db):
    unregistered = process_command('U1', '小明', '/設定管理員')
    assert unregistered.text.startswith('❌ 請先登記')

    process_command('U1', '小明', '/登記 光之勇者')
    reply = process_command('U1', '小明', '/設定管理員')

    assert reply.text.startswith('✅ 你已成為第一位管理員！')
    assert db.is_admin('U1')


def test_admin_can_view_roster_pages_and_full_list(db):
    admin_id = make_admin(db)
    for i in range(24):
        db.register_member(f'U{i}', f'成員{i}', f'角色{i}')

    page_two = process_command(admin_id, '會長', '/名冊 2')
    everyone = process_command(admin_id, '會長', '/名冊 全部')

    assert page_two.alt_text == '成員名冊 - 第 2/2 頁，共 25 人'
    assert isinstance(everyone, TextMessage)
    assert everyone.text.startswith('📋 成員名冊（全部 25 人）')
    assert everyone.text.count('↔') == 25


def test_admin_can_delete_and_register_for_others(db):
    admin_id = make_admin(db)
    db.register_member('U1', '小明', '光之勇者')
    db.record_pending_user('U2', '小華')

    deleted = process_command(admin_id, '會長', '/刪除 光之勇者')
    registered = process_command(admin_id, '會長', '/代登記 小華 夜影刺客 幹部')

    assert deleted.text.startswith('✅ 刪除成功')
    assert db.get_member_by_user_id('U1') is None
    assert registered.text.startswith('✅ 代登記成功')
    assert db.is_admin('U2')


def test_admin_list_command(db):
    assert process_command('U1', '小明', '/幹部').text == '❌ 目前沒有設定任何幹部'

    make_admin(db)

    assert process_command('U1', '小明', '/幹部').text == '👑 幹部名單（共 1 人）\n\n1. 會長 ↔ 公會長'


def test_handle_text_records_speaker_for_register_for(db):
    admin_id = make_admin(db)

    assert handle_text('U2', '小華', '大家好') is None
    reply = handle_text(admin_id, '會長', '/代登記 小華')

    assert reply.text.startswith('✅ 代登記成功')
    assert db.get_member_by_user_id('U2')['game_name'] == '小華'


def test_handle_text_syncs_changed_display_name(db):
    db.register_member('U1', '小明', '光之勇者')

    handle_text('U1', '小明改名了', '早安')

    assert db.get_member_by_user_id('U1')['line_display_name'] == '小明改名了'
