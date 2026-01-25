import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

DATABASE_URL = os.environ.get('DATABASE_URL')


def get_connection():
    """建立資料庫連線"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


@contextmanager
def get_db_cursor():
    """資料庫游標的 context manager"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def init_db():
    """初始化資料庫，建立 members 表"""
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
