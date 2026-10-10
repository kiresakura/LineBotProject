"""本機示範模式：重播範例對話並檢查關鍵回覆"""

from pathlib import Path

import pytest

import database
import demo

EXAMPLE_CHAT = Path(__file__).resolve().parent.parent / 'examples' / 'demo-chat.txt'


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


def test_replay_example_chat(capsys):
    assert demo.main([str(EXAMPLE_CHAT)]) == 0

    output = capsys.readouterr().out
    assert '🤖 ✅ 你已成為第一位管理員！' in output
    assert '🤖 ✅ 代登記成功' in output
    assert '🤖 ❌ 此指令僅限幹部使用' in output
    assert '🤖 📋 成員名冊 第 1/1 頁，共 3 人' in output
    assert '   3. 小華 ↔ 夜影刺客' in output
    assert '   舊遊戲名稱：風之旅人' in output
    assert '🤖 👑 幹部名單（共 1 人）' in output


def test_db_option_keeps_data(tmp_path, capsys):
    db_path = tmp_path / 'demo.db'

    demo.main(['--db', str(db_path), str(EXAMPLE_CHAT)])

    assert db_path.exists()
    assert database.get_all_members()['total'] == 3
