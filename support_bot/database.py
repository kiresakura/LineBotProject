import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

SQLITE_URL_PREFIX = 'sqlite:///'

# 本模組的 SQL 以 PostgreSQL 撰寫；使用 SQLite（本機示範與測試）時換成等價語法
SQLITE_REWRITES = [
    ('%s', '?'),
    ('ILIKE', 'LIKE'),
    ('NOW()', 'CURRENT_TIMESTAMP'),
    ('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
]


class SQLiteCursor:
    """包裝 sqlite3 游標，執行前把 PostgreSQL 語法轉成 SQLite 語法"""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=()):
        for postgres_syntax, sqlite_syntax in SQLITE_REWRITES:
            sql = sql.replace(postgres_syntax, sqlite_syntax)
        return self._cursor.execute(sql, params)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


def dict_row_factory(cursor, row):
    """讓 SQLite 查詢結果和 RealDictCursor 一樣以欄位名稱存取"""
    return {column[0]: value for column, value in zip(cursor.description, row)}


def get_connection():
    """
    建立資料庫連線（連線時才讀 DATABASE_URL，確保 load_dotenv() 的設定生效）
    DATABASE_URL 為 sqlite:///檔案路徑 時改用本機 SQLite，不需要 PostgreSQL
    """
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith(SQLITE_URL_PREFIX):
        conn = sqlite3.connect(database_url[len(SQLITE_URL_PREFIX):])
        conn.row_factory = dict_row_factory
        return conn
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)


@contextmanager
def get_db_cursor():
    """資料庫游標的 context manager"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if isinstance(conn, sqlite3.Connection):
            cursor = SQLiteCursor(cursor)
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def init_db():
    """初始化資料庫，建立 members 表和 pending_users 表"""
    with get_db_cursor() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS members (
                id SERIAL PRIMARY KEY,
                line_user_id VARCHAR(50) UNIQUE NOT NULL,
                line_display_name VARCHAR(100),
                game_name VARCHAR(100) NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        # 建立索引以加速查詢
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_members_game_name
            ON members (game_name)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_members_line_display_name
            ON members (line_display_name)
        ''')

        # 建立 pending_users 表（記錄發過訊息但未登記的用戶）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_users (
                id SERIAL PRIMARY KEY,
                line_user_id VARCHAR(50) UNIQUE NOT NULL,
                line_display_name VARCHAR(100),
                last_seen TIMESTAMP DEFAULT NOW()
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_pending_users_display_name
            ON pending_users (line_display_name)
        ''')

        # 建立 handoff_requests 表（答不出來、轉給真人處理的訊息）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS handoff_requests (
                id SERIAL PRIMARY KEY,
                line_user_id VARCHAR(50) NOT NULL,
                display_name VARCHAR(100),
                message TEXT NOT NULL,
                status VARCHAR(10) NOT NULL DEFAULT 'open',
                created_at VARCHAR(16) NOT NULL
            )
        ''')
    print("資料庫初始化完成")


def register_member(line_user_id: str, line_display_name: str, game_name: str) -> dict:
    """
    登記新成員
    回傳: {'success': bool, 'message': str}
    """
    with get_db_cursor() as cursor:
        # 檢查是否已登記
        cursor.execute(
            'SELECT * FROM members WHERE line_user_id = %s',
            (line_user_id,)
        )
        existing = cursor.fetchone()

        if existing:
            return {
                'success': False,
                'message': f"你已經登記過了！\n目前綁定的遊戲名稱：{existing['game_name']}\n如需修改請使用 /修改 [新遊戲名稱]"
            }

        # 檢查遊戲名稱是否被使用
        cursor.execute(
            'SELECT * FROM members WHERE game_name = %s',
            (game_name,)
        )
        if cursor.fetchone():
            return {
                'success': False,
                'message': f"遊戲名稱「{game_name}」已被其他人使用！"
            }

        # 新增成員
        cursor.execute('''
            INSERT INTO members (line_user_id, line_display_name, game_name)
            VALUES (%s, %s, %s)
        ''', (line_user_id, line_display_name, game_name))

        return {
            'success': True,
            'message': f"登記成功！\nLINE 名稱：{line_display_name}\n遊戲名稱：{game_name}"
        }


def update_game_name(line_user_id: str, new_game_name: str) -> dict:
    """
    修改遊戲名稱
    回傳: {'success': bool, 'message': str}
    """
    with get_db_cursor() as cursor:
        # 檢查是否已登記
        cursor.execute(
            'SELECT * FROM members WHERE line_user_id = %s',
            (line_user_id,)
        )
        existing = cursor.fetchone()

        if not existing:
            return {
                'success': False,
                'message': "你尚未登記！請先使用 /登記 [遊戲名稱]"
            }

        # 檢查新遊戲名稱是否被使用
        cursor.execute(
            'SELECT * FROM members WHERE game_name = %s AND line_user_id != %s',
            (new_game_name, line_user_id)
        )
        if cursor.fetchone():
            return {
                'success': False,
                'message': f"遊戲名稱「{new_game_name}」已被其他人使用！"
            }

        old_name = existing['game_name']

        # 更新遊戲名稱
        cursor.execute('''
            UPDATE members
            SET game_name = %s, updated_at = NOW()
            WHERE line_user_id = %s
        ''', (new_game_name, line_user_id))

        return {
            'success': True,
            'message': f"修改成功！\n舊遊戲名稱：{old_name}\n新遊戲名稱：{new_game_name}"
        }


def search_member(query: str) -> list:
    """
    模糊搜尋成員
    回傳: 符合條件的成員列表
    """
    with get_db_cursor() as cursor:
        cursor.execute('''
            SELECT line_display_name, game_name
            FROM members
            WHERE line_display_name ILIKE %s OR game_name ILIKE %s
            ORDER BY game_name
        ''', (f'%{query}%', f'%{query}%'))
        return cursor.fetchall()


def get_all_members(page: int = 1, per_page: int = 20) -> dict:
    """
    取得所有成員（分頁）
    回傳: {'members': list, 'total': int, 'page': int, 'total_pages': int}
    """
    with get_db_cursor() as cursor:
        # 取得總數
        cursor.execute('SELECT COUNT(*) as count FROM members')
        total = cursor.fetchone()['count']

        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        page = max(1, min(page, total_pages))
        offset = (page - 1) * per_page

        # 取得分頁資料
        cursor.execute('''
            SELECT line_display_name, game_name
            FROM members
            ORDER BY id
            LIMIT %s OFFSET %s
        ''', (per_page, offset))
        members = cursor.fetchall()

        return {
            'members': members,
            'total': total,
            'page': page,
            'total_pages': total_pages
        }


def get_member_by_user_id(line_user_id: str) -> dict:
    """
    透過 LINE user ID 取得成員資料
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            'SELECT * FROM members WHERE line_user_id = %s',
            (line_user_id,)
        )
        return cursor.fetchone()


def delete_member(query: str) -> dict:
    """
    刪除成員（透過遊戲名稱或 LINE 名稱）
    回傳: {'success': bool, 'message': str}
    """
    with get_db_cursor() as cursor:
        # 尋找成員
        cursor.execute('''
            SELECT * FROM members
            WHERE game_name = %s OR line_display_name = %s
        ''', (query, query))
        member = cursor.fetchone()

        if not member:
            return {
                'success': False,
                'message': f"找不到成員「{query}」"
            }

        # 刪除成員
        cursor.execute(
            'DELETE FROM members WHERE id = %s',
            (member['id'],)
        )

        return {
            'success': True,
            'message': f"已刪除成員\nLINE 名稱：{member['line_display_name']}\n遊戲名稱：{member['game_name']}"
        }


def is_admin(line_user_id: str) -> bool:
    """
    檢查使用者是否為管理員
    """
    member = get_member_by_user_id(line_user_id)
    return member and member['is_admin']


def set_admin(query: str) -> dict:
    """
    設定管理員（透過遊戲名稱或 LINE 名稱）
    回傳: {'success': bool, 'message': str}
    """
    with get_db_cursor() as cursor:
        # 先用遊戲名稱精確搜尋
        cursor.execute(
            'SELECT * FROM members WHERE game_name = %s',
            (query,)
        )
        member = cursor.fetchone()

        # 如果找不到，用 LINE 名稱精確搜尋
        if not member:
            cursor.execute(
                'SELECT * FROM members WHERE line_display_name = %s',
                (query,)
            )
            member = cursor.fetchone()

        # 如果還是找不到，用模糊搜尋
        if not member:
            cursor.execute(
                '''SELECT * FROM members
                   WHERE game_name ILIKE %s OR line_display_name ILIKE %s
                   LIMIT 1''',
                (f'%{query}%', f'%{query}%')
            )
            member = cursor.fetchone()

        if not member:
            return {
                'success': False,
                'message': f"找不到「{query}」的成員"
            }

        if member['is_admin']:
            return {
                'success': False,
                'message': f"「{member['line_display_name']}」已經是幹部了"
            }

        # 設定為管理員
        cursor.execute('''
            UPDATE members
            SET is_admin = TRUE, updated_at = NOW()
            WHERE id = %s
        ''', (member['id'],))

        return {
            'success': True,
            'message': f"已將「{member['line_display_name']}」設為幹部\n遊戲名稱：{member['game_name']}"
        }


def get_admin_count() -> int:
    """取得管理員數量"""
    with get_db_cursor() as cursor:
        cursor.execute('SELECT COUNT(*) as count FROM members WHERE is_admin = TRUE')
        return cursor.fetchone()['count']


def get_all_admins() -> list:
    """取得所有幹部列表"""
    with get_db_cursor() as cursor:
        cursor.execute('''
            SELECT line_display_name, game_name
            FROM members
            WHERE is_admin = TRUE
            ORDER BY id
        ''')
        return cursor.fetchall()


def register_by_admin(line_display_name: str, game_name: str = None, set_as_admin: bool = False) -> dict:
    """
    管理員代為登記成員（透過 LINE 名稱）
    game_name 為 None 時，使用 LINE 名稱作為遊戲名稱
    回傳: {'success': bool, 'message': str}
    """
    with get_db_cursor() as cursor:
        # 從最近發過訊息的用戶中尋找（透過已記錄的 line_display_name）
        # 先檢查是否有這個 LINE 名稱的未登記用戶記錄
        cursor.execute(
            'SELECT * FROM pending_users WHERE line_display_name = %s ORDER BY last_seen DESC LIMIT 1',
            (line_display_name,)
        )
        pending_user = cursor.fetchone()

        if not pending_user:
            # 模糊搜尋
            cursor.execute(
                'SELECT * FROM pending_users WHERE line_display_name ILIKE %s ORDER BY last_seen DESC LIMIT 1',
                (f'%{line_display_name}%',)
            )
            pending_user = cursor.fetchone()

        if not pending_user:
            return {
                'success': False,
                'message': f"找不到「{line_display_name}」\n請確認該用戶已在群組中發過訊息"
            }

        # 如果沒有提供遊戲名稱，使用 LINE 名稱
        actual_game_name = game_name if game_name else pending_user['line_display_name']

        # 檢查是否已登記
        cursor.execute(
            'SELECT * FROM members WHERE line_user_id = %s',
            (pending_user['line_user_id'],)
        )
        existing_member = cursor.fetchone()

        if existing_member:
            # 已登記，如果是要設為幹部就直接更新
            if set_as_admin:
                if existing_member['is_admin']:
                    return {
                        'success': False,
                        'message': f"「{pending_user['line_display_name']}」已經是幹部了"
                    }
                cursor.execute('''
                    UPDATE members SET is_admin = TRUE, updated_at = NOW()
                    WHERE line_user_id = %s
                ''', (pending_user['line_user_id'],))
                return {
                    'success': True,
                    'message': f"已將「{pending_user['line_display_name']}」設為幹部\n遊戲名稱：{existing_member['game_name']}"
                }
            else:
                return {
                    'success': False,
                    'message': f"「{pending_user['line_display_name']}」已經登記過了\n遊戲名稱：{existing_member['game_name']}"
                }

        # 檢查遊戲名稱是否被使用
        cursor.execute(
            'SELECT * FROM members WHERE game_name = %s',
            (actual_game_name,)
        )
        if cursor.fetchone():
            return {
                'success': False,
                'message': f"遊戲名稱「{actual_game_name}」已被其他人使用"
            }

        # 新增成員
        cursor.execute('''
            INSERT INTO members (line_user_id, line_display_name, game_name, is_admin)
            VALUES (%s, %s, %s, %s)
        ''', (pending_user['line_user_id'], pending_user['line_display_name'], actual_game_name, set_as_admin))

        admin_text = "（已設為幹部）" if set_as_admin else ""
        return {
            'success': True,
            'message': f"已為「{pending_user['line_display_name']}」登記{admin_text}\n遊戲名稱：{actual_game_name}"
        }


def record_pending_user(line_user_id: str, line_display_name: str):
    """
    記錄發過訊息但未登記的用戶（供代登記使用）
    """
    with get_db_cursor() as cursor:
        cursor.execute('''
            INSERT INTO pending_users (line_user_id, line_display_name, last_seen)
            VALUES (%s, %s, NOW())
            ON CONFLICT (line_user_id)
            DO UPDATE SET line_display_name = %s, last_seen = NOW()
        ''', (line_user_id, line_display_name, line_display_name))


def sync_display_name(line_user_id: str, current_display_name: str) -> bool:
    """
    同步 LINE 顯示名稱（如果有變更則更新）
    回傳: 是否有更新
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            'SELECT line_display_name FROM members WHERE line_user_id = %s',
            (line_user_id,)
        )
        member = cursor.fetchone()

        if member and member['line_display_name'] != current_display_name:
            cursor.execute('''
                UPDATE members
                SET line_display_name = %s, updated_at = NOW()
                WHERE line_user_id = %s
            ''', (current_display_name, line_user_id))
            return True

        return False


def create_handoff(line_user_id: str, display_name: str, message: str, created_at: str) -> dict:
    """
    新增一筆待處理的轉真人訊息
    created_at: 店家時區的「YYYY-MM-DD HH:MM」
    回傳: 新增的資料（含編號 id）
    """
    with get_db_cursor() as cursor:
        cursor.execute('''
            INSERT INTO handoff_requests (line_user_id, display_name, message, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING *
        ''', (line_user_id, display_name, message, created_at))
        return cursor.fetchone()


def list_open_handoffs(limit: int = 20) -> list:
    """取得尚未處理的轉真人訊息（舊的在前）"""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM handoff_requests WHERE status = 'open' ORDER BY id LIMIT %s",
            (limit,)
        )
        return cursor.fetchall()


def resolve_handoff(request_id: int) -> bool:
    """
    把轉真人訊息標記為已處理
    回傳: 是否有這筆尚未處理的訊息
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            "UPDATE handoff_requests SET status = 'done' WHERE id = %s AND status = 'open'",
            (request_id,)
        )
        return cursor.rowcount == 1
