"""名冊資料層的增刪查邏輯（以 SQLite 執行同一份 SQL）"""


def test_register_member_success(db):
    result = db.register_member('U1', '小明', '光之勇者')

    assert result['success'] is True
    member = db.get_member_by_user_id('U1')
    assert member['line_display_name'] == '小明'
    assert member['game_name'] == '光之勇者'
    assert not member['is_admin']


def test_register_member_rejects_second_registration(db):
    db.register_member('U1', '小明', '光之勇者')

    result = db.register_member('U1', '小明', '夜影刺客')

    assert result['success'] is False
    assert '光之勇者' in result['message']
    assert db.get_member_by_user_id('U1')['game_name'] == '光之勇者'


def test_register_member_rejects_taken_game_name(db):
    db.register_member('U1', '小明', '光之勇者')

    result = db.register_member('U2', '小華', '光之勇者')

    assert result['success'] is False
    assert db.get_member_by_user_id('U2') is None


def test_update_game_name_requires_registration(db):
    result = db.update_game_name('U1', '暗黑騎士')

    assert result['success'] is False
    assert '尚未登記' in result['message']


def test_update_game_name_success(db):
    db.register_member('U1', '小明', '光之勇者')

    result = db.update_game_name('U1', '暗黑騎士')

    assert result['success'] is True
    assert '光之勇者' in result['message']
    assert db.get_member_by_user_id('U1')['game_name'] == '暗黑騎士'


def test_update_game_name_rejects_name_used_by_someone_else(db):
    db.register_member('U1', '小明', '光之勇者')
    db.register_member('U2', '小華', '夜影刺客')

    result = db.update_game_name('U1', '夜影刺客')

    assert result['success'] is False
    assert db.get_member_by_user_id('U1')['game_name'] == '光之勇者'


def test_search_member_matches_partial_line_or_game_name(db):
    db.register_member('U1', '小明', 'Brave Hero')
    db.register_member('U2', '小華', '夜影刺客')
    db.register_member('U3', '阿美', '風之旅人')

    assert [m['game_name'] for m in db.search_member('hero')] == ['Brave Hero']
    assert [m['line_display_name'] for m in db.search_member('華')] == ['小華']
    assert db.search_member('不存在') == []


def test_get_all_members_paginates_and_clamps_page(db):
    for i in range(25):
        db.register_member(f'U{i}', f'成員{i}', f'角色{i}')

    first = db.get_all_members(page=1)
    second = db.get_all_members(page=2)
    too_far = db.get_all_members(page=99)

    assert first['total'] == 25
    assert first['total_pages'] == 2
    assert len(first['members']) == 20
    assert [m['game_name'] for m in second['members']] == [f'角色{i}' for i in range(20, 25)]
    assert too_far['page'] == 2


def test_get_all_members_on_empty_roster(db):
    data = db.get_all_members()

    assert data == {'members': [], 'total': 0, 'page': 1, 'total_pages': 1}


def test_delete_member_by_game_name_or_line_name(db):
    db.register_member('U1', '小明', '光之勇者')
    db.register_member('U2', '小華', '夜影刺客')

    assert db.delete_member('光之勇者')['success'] is True
    assert db.delete_member('小華')['success'] is True
    assert db.get_all_members()['total'] == 0


def test_delete_member_not_found(db):
    result = db.delete_member('沒有這個人')

    assert result['success'] is False
    assert '沒有這個人' in result['message']


def test_set_admin_by_exact_and_fuzzy_name(db):
    db.register_member('U1', '小明', '光之勇者')
    db.register_member('U2', '小華', '夜影刺客')
    db.register_member('U3', '阿美', '風之旅人')

    assert db.set_admin('光之勇者')['success'] is True
    assert db.set_admin('小華')['success'] is True
    assert db.set_admin('旅人')['success'] is True
    assert db.is_admin('U1') and db.is_admin('U2') and db.is_admin('U3')
    assert db.get_admin_count() == 3


def test_set_admin_rejects_existing_admin_and_unknown_member(db):
    db.register_member('U1', '小明', '光之勇者')
    db.set_admin('光之勇者')

    assert '已經是幹部' in db.set_admin('光之勇者')['message']
    assert db.set_admin('路人')['success'] is False


def test_is_admin_is_false_for_unregistered_user(db):
    assert not db.is_admin('U-unknown')


def test_get_all_admins_lists_only_admins(db):
    db.register_member('U1', '小明', '光之勇者')
    db.register_member('U2', '小華', '夜影刺客')
    db.set_admin('小華')

    assert db.get_all_admins() == [{'line_display_name': '小華', 'game_name': '夜影刺客'}]


def test_register_by_admin_requires_user_to_have_spoken(db):
    result = db.register_by_admin('小華', '夜影刺客')

    assert result['success'] is False
    assert '發過訊息' in result['message']


def test_register_by_admin_defaults_game_name_to_line_name(db):
    db.record_pending_user('U2', '小華')

    result = db.register_by_admin('小華')

    assert result['success'] is True
    assert db.get_member_by_user_id('U2')['game_name'] == '小華'


def test_register_by_admin_with_game_name_and_admin_flag(db):
    db.record_pending_user('U2', '小華')

    result = db.register_by_admin('華', '夜影刺客', set_as_admin=True)

    assert result['success'] is True
    member = db.get_member_by_user_id('U2')
    assert member['game_name'] == '夜影刺客'
    assert member['is_admin']


def test_register_by_admin_promotes_existing_member(db):
    db.record_pending_user('U2', '小華')
    db.register_member('U2', '小華', '夜影刺客')

    assert db.register_by_admin('小華', set_as_admin=True)['success'] is True
    assert db.is_admin('U2')
    assert '已經是幹部' in db.register_by_admin('小華', set_as_admin=True)['message']
    assert '已經登記過了' in db.register_by_admin('小華')['message']


def test_register_by_admin_rejects_taken_game_name(db):
    db.register_member('U1', '小明', '光之勇者')
    db.record_pending_user('U2', '小華')

    result = db.register_by_admin('小華', '光之勇者')

    assert result['success'] is False
    assert db.get_member_by_user_id('U2') is None


def test_record_pending_user_updates_display_name(db):
    db.record_pending_user('U2', '小華')
    db.record_pending_user('U2', '小華改名')

    assert db.register_by_admin('小華改名')['success'] is True


def test_sync_display_name_only_updates_changed_registered_members(db):
    db.register_member('U1', '小明', '光之勇者')

    assert db.sync_display_name('U1', '小明') is False
    assert db.sync_display_name('U1', '新名字') is True
    assert db.get_member_by_user_id('U1')['line_display_name'] == '新名字'
    assert db.sync_display_name('U-unknown', '路人') is False
