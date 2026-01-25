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
