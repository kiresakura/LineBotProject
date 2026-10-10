"""DATABASE_URL 讀取時機的回歸測試"""

from support_bot import database as db


def test_get_connection_reads_database_url_at_call_time(monkeypatch):
    # web.py 在 import database 之後才執行 load_dotenv()，
    # 所以必須在連線當下讀環境變數，.env 裡的 DATABASE_URL 才會生效
    captured = {}

    def fake_connect(dsn, **kwargs):
        captured['dsn'] = dsn
        return object()

    monkeypatch.setenv('DATABASE_URL', 'postgresql://example/roster')
    monkeypatch.setattr(db.psycopg2, 'connect', fake_connect)

    db.get_connection()

    assert captured['dsn'] == 'postgresql://example/roster'
