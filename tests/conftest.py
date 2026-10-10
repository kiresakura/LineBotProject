import os

import pytest

from support_bot import database

TABLES = ['members', 'pending_users', 'handoff_requests', 'processed_events']


@pytest.fixture
def db(monkeypatch, tmp_path):
    """
    每個測試使用全新的資料庫，不需要網路
    預設為暫存的 SQLite 檔；設定 TEST_DATABASE_URL（postgresql://…）時改用該 PostgreSQL，測試前先清掉資料表
    """
    test_database_url = os.environ.get('TEST_DATABASE_URL')
    if test_database_url:
        monkeypatch.setenv('DATABASE_URL', test_database_url)
        with database.get_db_cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {', '.join(TABLES)}")
    else:
        monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path / "roster.db"}')
    database.init_db()
    return database
