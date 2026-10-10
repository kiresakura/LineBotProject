"""本機示範模式：重播範例對話並檢查關鍵回覆"""

from pathlib import Path

import pytest

from support_bot import database, demo

EXAMPLES = Path(__file__).resolve().parent.parent / 'examples'


@pytest.fixture(autouse=True)
def restore_database_url(monkeypatch):
    # demo.main() 會改寫 DATABASE_URL，測試結束後由 monkeypatch 還原
    monkeypatch.delenv('DATABASE_URL', raising=False)


@pytest.mark.parametrize('line, expected', [
    ('阿美: /登記 風之旅人', ('阿美', '/登記 風之旅人')),
    ('/查詢 a:b', ('小明', '/查詢 a:b')),
    ('沒有名稱的訊息', ('小明', '沒有名稱的訊息')),
])
def test_split_speaker(line, expected):
    assert demo.split_speaker(line, '小明') == expected


def test_default_replay_is_the_shop_conversation(capsys):
    assert demo.main([]) == 0

    output = capsys.readouterr().out
    assert '🕑 2026-10-13（二）14:00，營業中' in output
    assert '🤖 週二至週日 10:00–20:00' in output                       # FAQ 關鍵字
    assert '🤖 歡迎！寵物請使用牽繩' in output                          # 相似詞「毛小孩」
    assert '🤖 📋 菜單：https://example.com/menu' in output            # 固定關鍵字
    assert '🔔 通知管理員（log）：轉真人 #1｜王小姐：週末可以包場辦生日派對嗎？' in output
    assert '🤖 這個問題我先幫您轉給店員，已通知專人' in output
    assert '🕑 2026-10-13（二）22:30，非營業時間' in output
    assert '🤖 目前是非營業時間' in output
    assert '陳先生: /待處理\n🤖 ❌ 此指令僅限管理員使用' in output
    assert '🤖 📋 待處理 2 筆（由舊到新）' in output
    assert '🤖 ✅ 已將 #1 標記為完成' in output


def test_replay_group_roster_example(capsys):
    assert demo.main([str(EXAMPLES / 'demo-group.txt')]) == 0

    output = capsys.readouterr().out
    assert '── 群組聊天 ──' in output
    assert '🤖 ✅ 你已成為第一位管理員！' in output
    assert '🤖 ✅ 代登記成功' in output
    assert '🤖 ❌ 此指令僅限幹部使用' in output
    assert '🤖 📋 成員名冊 第 1/1 頁，共 3 人' in output
    assert '   3. 小華 ↔ 夜影刺客' in output
    assert '   舊遊戲名稱：風之旅人' in output
    assert '🤖 👑 幹部名單（共 1 人）' in output
    # 群組裡的一般聊天不會觸發轉真人
    assert '轉真人' not in output


def test_db_option_keeps_data(tmp_path, capsys):
    db_path = tmp_path / 'demo.db'

    demo.main(['--db', str(db_path), str(EXAMPLES / 'demo-group.txt')])

    assert db_path.exists()
    assert database.get_all_members()['total'] == 3


def test_unknown_directive_is_reported(tmp_path):
    script = tmp_path / 'chat.txt'
    script.write_text('@weather sunny\n', encoding='utf-8')

    with pytest.raises(ValueError, match='@weather'):
        demo.main([str(script)])
