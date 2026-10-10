"""
指令處理模組
回傳 LINE Message 物件（支援 Flex Message 和 Quick Reply）
"""

from support_bot import database as db
from support_bot.roster_messages import (
    create_menu_message,
    create_roster_message,
    create_roster_text_message,
    create_search_result_message,
    create_profile_message,
    create_help_message,
    create_success_message,
    create_error_message,
    create_input_prompt_message
)
from linebot.v3.messaging import TextMessage

ADMIN_KEYWORDS = ['幹部', '管理員', 'admin']


def parse_command(text: str):
    """
    拆出指令與參數
    回傳: (小寫指令, 參數字串)；不是指令（不以 / 開頭）時回傳 None
    """
    text = text.strip()

    if not text.startswith('/'):
        return None

    parts = text.split(maxsplit=1)
    return parts[0].lower(), (parts[1] if len(parts) > 1 else "")


def parse_roster_args(args: str):
    """
    解析 /名冊 的參數
    回傳: (是否顯示全部, 頁碼)；無法解析的頁碼視為第 1 頁
    """
    args = args.strip()
    if args in ['全部', '所有', 'all']:
        return True, 1
    try:
        return False, int(args)
    except ValueError:
        return False, 1


def parse_register_for_args(args: str):
    """
    解析 /代登記 的參數
    回傳: (LINE 名稱, 登記名稱或 None, 是否設為幹部)；沒有參數時回傳 None
    登記名稱為 None 時，資料層會改用 LINE 名稱
    """
    parts = args.split()
    if not parts:
        return None

    line_name = parts[0]
    if len(parts) == 1:
        # /代登記 小明 → 用 LINE 名稱作為登記名稱
        return line_name, None, False
    if len(parts) == 2:
        if parts[1] in ADMIN_KEYWORDS:
            # /代登記 小明 幹部 → 用 LINE 名稱作為登記名稱，設為幹部
            return line_name, None, True
        # /代登記 小明 王小明
        return line_name, parts[1], False
    # /代登記 小明 王小明 幹部
    return line_name, parts[1], parts[2] in ADMIN_KEYWORDS


def is_officer(line_user_id: str, admin_user_ids=frozenset()) -> bool:
    """白名單管理員（ADMIN_USER_IDS）或名冊中的幹部"""
    return line_user_id in admin_user_ids or bool(db.is_admin(line_user_id))


def handle_register(line_user_id: str, line_display_name: str, args: str):
    """處理 /登記 指令"""
    if not args:
        return create_input_prompt_message(
            command="登記",
            prompt="請輸入要登記的名稱（例如本名、學號或暱稱）",
            examples=["/登記 王小明", "/登記 陳小華"]
        )

    game_name = args.strip()
    if len(game_name) > 100:
        return create_error_message(
            "登記名稱過長（最多 100 字）",
            quick_actions=[
                {'label': '重新登記', 'text': '/登記'},
                {'label': '查看說明', 'text': '/說明'}
            ]
        )

    result = db.register_member(line_user_id, line_display_name, game_name)

    if result['success']:
        return create_success_message(
            title="登記成功！",
            content=f"LINE 名稱：{line_display_name}\n登記名稱：{game_name}",
            quick_actions=[
                {'label': '查看名冊', 'text': '/名冊'},
                {'label': '我的資料', 'text': '/我是誰'}
            ]
        )
    else:
        return create_error_message(
            result['message'],
            quick_actions=[
                {'label': '修改名稱', 'text': '/修改'},
                {'label': '我的資料', 'text': '/我是誰'}
            ]
        )


def handle_update(line_user_id: str, args: str):
    """處理 /修改 指令"""
    if not args:
        return create_input_prompt_message(
            command="修改",
            prompt="請輸入新的登記名稱",
            examples=["/修改 王大明", "/修改 林美美"]
        )

    new_game_name = args.strip()
    if len(new_game_name) > 100:
        return create_error_message(
            "登記名稱過長（最多 100 字）",
            quick_actions=[
                {'label': '重新修改', 'text': '/修改'},
                {'label': '我的資料', 'text': '/我是誰'}
            ]
        )

    result = db.update_game_name(line_user_id, new_game_name)

    if result['success']:
        return create_success_message(
            title="修改成功！",
            content=result['message'].replace("修改成功！\n", ""),
            quick_actions=[
                {'label': '查看名冊', 'text': '/名冊'},
                {'label': '我的資料', 'text': '/我是誰'}
            ]
        )
    else:
        return create_error_message(
            result['message'],
            quick_actions=[
                {'label': '立即登記', 'text': '/登記'},
                {'label': '查看說明', 'text': '/說明'}
            ]
        )


def handle_search(args: str):
    """處理 /查詢 指令"""
    if not args:
        return create_input_prompt_message(
            command="查詢",
            prompt="請輸入要搜尋的名稱\n可使用 LINE 名稱或登記名稱",
            examples=["/查詢 小明", "/查詢 王"]
        )

    query = args.strip()
    results = db.search_member(query)

    return create_search_result_message(query, results)


def handle_roster(line_user_id: str, args: str, admin_user_ids=frozenset()):
    """處理 /名冊 指令（僅限管理員）"""
    if not is_officer(line_user_id, admin_user_ids):
        return create_error_message(
            "此指令僅限幹部使用",
            quick_actions=[
                {'label': '我的資料', 'text': '/我是誰'},
                {'label': '查看說明', 'text': '/說明'}
            ]
        )

    show_all, page = parse_roster_args(args)

    if show_all:
        # 取得所有成員，使用純文字訊息避免 Flex Message 大小限制
        data = db.get_all_members(page=1, per_page=999999)
        return create_roster_text_message(
            members=data['members'],
            total=data['total']
        )
    else:
        data = db.get_all_members(page=page)
        return create_roster_message(
            members=data['members'],
            page=data['page'],
            total_pages=data['total_pages'],
            total=data['total'],
            show_all=False
        )


def handle_delete(line_user_id: str, args: str, admin_user_ids=frozenset()):
    """處理 /刪除 指令（僅限管理員）"""
    if not is_officer(line_user_id, admin_user_ids):
        return create_error_message(
            "此指令僅限管理員使用",
            quick_actions=[
                {'label': '查看說明', 'text': '/說明'},
                {'label': '查看名冊', 'text': '/名冊'}
            ]
        )

    if not args:
        return create_input_prompt_message(
            command="刪除成員",
            prompt="請輸入要刪除的成員名稱\n可使用 LINE 名稱或登記名稱",
            examples=["/刪除 小明", "/刪除 王小明"]
        )

    query = args.strip()
    result = db.delete_member(query)

    if result['success']:
        return create_success_message(
            title="刪除成功",
            content=result['message'].replace("已刪除成員\n", ""),
            quick_actions=[
                {'label': '查看名冊', 'text': '/名冊'}
            ]
        )
    else:
        return create_error_message(
            result['message'],
            quick_actions=[
                {'label': '查看名冊', 'text': '/名冊'},
                {'label': '搜尋成員', 'text': '/查詢'}
            ]
        )


def handle_set_admin(line_user_id: str, args: str, admin_user_ids=frozenset()):
    """處理 /設定管理員 指令（僅限管理員）"""
    admin_count = db.get_admin_count()

    # 設定了管理員白名單（ADMIN_USER_IDS）時不開放自行成為第一位幹部
    if admin_count == 0 and not admin_user_ids:
        member = db.get_member_by_user_id(line_user_id)
        if not member:
            return create_error_message(
                "請先登記後，再使用此指令成為第一位管理員",
                quick_actions=[
                    {'label': '立即登記', 'text': '/登記'}
                ]
            )

        from support_bot.database import get_db_cursor
        with get_db_cursor() as cursor:
            cursor.execute('''
                UPDATE members
                SET is_admin = TRUE, updated_at = NOW()
                WHERE line_user_id = %s
            ''', (line_user_id,))

        return create_success_message(
            title="你已成為第一位管理員！",
            content="現在可以使用管理員指令了",
            quick_actions=[
                {'label': '查看名冊', 'text': '/名冊'},
                {'label': '查看說明', 'text': '/說明'}
            ]
        )

    if not is_officer(line_user_id, admin_user_ids):
        return create_error_message(
            "此指令僅限管理員使用",
            quick_actions=[
                {'label': '查看說明', 'text': '/說明'}
            ]
        )

    if not args:
        return create_input_prompt_message(
            command="設定管理員",
            prompt="請輸入要設為幹部的成員名稱\n可使用 LINE 名稱或登記名稱",
            examples=["/設定管理員 小明", "/設定管理員 王小明"]
        )

    query = args.strip()
    result = db.set_admin(query)

    if result['success']:
        return create_success_message(
            title="設定成功",
            content=result['message'],
            quick_actions=[
                {'label': '查看名冊', 'text': '/名冊'}
            ]
        )
    else:
        return create_error_message(
            result['message'],
            quick_actions=[
                {'label': '查看名冊', 'text': '/名冊'},
                {'label': '搜尋成員', 'text': '/查詢'}
            ]
        )


def handle_whoami(line_user_id: str, line_display_name: str):
    """處理 /我是誰 指令"""
    member = db.get_member_by_user_id(line_user_id)
    return create_profile_message(member, line_display_name, member is not None)


def handle_register_for(line_user_id: str, args: str, admin_user_ids=frozenset()):
    """處理 /代登記 指令（僅限管理員）"""
    if not is_officer(line_user_id, admin_user_ids):
        return create_error_message(
            "此指令僅限幹部使用",
            quick_actions=[
                {'label': '查看說明', 'text': '/說明'}
            ]
        )

    if not args:
        return create_input_prompt_message(
            command="代登記",
            prompt="幫其他成員登記\n\n格式：\n/代登記 [LINE名稱] [登記名稱]\n/代登記 [LINE名稱] [登記名稱] 幹部\n/代登記 [LINE名稱] 幹部\n\n只輸入「幹部」時，登記名稱自動用 LINE 名稱",
            examples=[
                "/代登記 小明 王小明",
                "/代登記 小明 王小明 幹部",
                "/代登記 小明 幹部"
            ]
        )

    parsed = parse_register_for_args(args)
    if parsed is None:
        return create_error_message(
            "請輸入 LINE 名稱",
            quick_actions=[
                {'label': '查看說明', 'text': '/說明'}
            ]
        )

    line_name, game_name, set_as_admin = parsed
    result = db.register_by_admin(line_name, game_name, set_as_admin)

    if result['success']:
        return create_success_message(
            title="代登記成功",
            content=result['message'],
            quick_actions=[
                {'label': '查看名冊', 'text': '/名冊'}
            ]
        )
    else:
        return create_error_message(
            result['message'],
            quick_actions=[
                {'label': '查看名冊', 'text': '/名冊'}
            ]
        )


def handle_admin_list():
    """處理 /幹部 指令"""
    admins = db.get_all_admins()

    if not admins:
        return create_error_message(
            "目前沒有設定任何幹部",
            quick_actions=[
                {'label': '查看說明', 'text': '/說明'}
            ]
        )

    lines = [f"👑 幹部名單（共 {len(admins)} 人）", ""]
    for i, admin in enumerate(admins, start=1):
        lines.append(f"{i}. {admin['line_display_name']} ↔ {admin['game_name']}")

    return TextMessage(text="\n".join(lines))


def handle_help():
    """處理 /說明 或 /help 指令"""
    return create_help_message()


def handle_menu():
    """處理 /選單 或 /menu 指令"""
    return create_menu_message()


def handle_text(line_user_id: str, line_display_name: str, text: str, admin_user_ids=frozenset()):
    """
    處理一則文字訊息（不呼叫 LINE API，Webhook 與本機示範共用）
    回傳: LINE Message 物件，如果不是指令則回傳 None
    """
    # 自動同步 LINE 顯示名稱（如果用戶已登記且名稱有變更）
    # 並記錄用戶資訊（供代登記使用）
    try:
        db.sync_display_name(line_user_id, line_display_name)
        db.record_pending_user(line_user_id, line_display_name)
    except Exception as e:
        print(f"同步/記錄用戶失敗: {e}")

    return process_command(line_user_id, line_display_name, text, admin_user_ids)


def process_command(line_user_id: str, line_display_name: str, text: str, admin_user_ids=frozenset()):
    """
    處理使用者指令
    回傳: LINE Message 物件，如果不是指令則回傳 None
    """
    parsed = parse_command(text)
    if parsed is None:
        return None

    command, args = parsed

    # 指令路由
    if command == '/登記':
        return handle_register(line_user_id, line_display_name, args)
    elif command == '/修改':
        return handle_update(line_user_id, args)
    elif command == '/查詢':
        return handle_search(args)
    elif command == '/名冊':
        return handle_roster(line_user_id, args, admin_user_ids)
    elif command == '/刪除':
        return handle_delete(line_user_id, args, admin_user_ids)
    elif command == '/設定管理員':
        return handle_set_admin(line_user_id, args, admin_user_ids)
    elif command == '/代登記':
        return handle_register_for(line_user_id, args, admin_user_ids)
    elif command == '/我是誰':
        return handle_whoami(line_user_id, line_display_name)
    elif command in ['/說明', '/help', '/幫助']:
        return handle_help()
    elif command in ['/選單', '/menu', '/功能']:
        return handle_menu()
    elif command in ['/幹部', '/幹部名單']:
        return handle_admin_list()
    else:
        return None
