import pytest

from support_bot import database


@pytest.fixture
def db(monkeypatch, tmp_path):
    """每個測試使用全新的 SQLite 檔案，不需要 PostgreSQL 或網路"""
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path / "roster.db"}')
    database.init_db()
    return database
