"""
指令處理模組
回傳 LINE Message 物件（支援 Flex Message 和 Quick Reply）
"""

import database as db
from messages import (
    create_menu_message,
    create_roster_message,
    create_roster_text_message,
    create_search_result_message,
    create_profile_message,
    create_help_message,
    create_success_message,
    create_error_message,
    create_input_prompt_message,
    create_quick_reply
)
from linebot.v3.messaging import TextMessage


def handle_register(line_user_id: str, line_display_name: str, args: str):
    """處理 /登記 指令"""
    if not args:
        return create_input_prompt_message(
            command="登記",
            prompt="請輸入你的遊戲角色名稱",
            examples=["/登記 光之勇者", "/登記 夜影刺客"]
        )

    game_name = args.strip()
    if len(game_name) > 100:
        return create_error_message(
            "遊戲名稱過長（最多 100 字）",
            quick_actions=[
                {'label': '重新登記', 'text': '/登記'},
                {'label': '查看說明', 'text': '/說明'}
            ]
        )

    result = db.register_member(line_user_id, line_display_name, game_name)

    if result['success']:
        return create_success_message(
            title="登記成功！",
            content=f"LINE 名稱：{line_display_name}\n遊戲名稱：{game_name}",
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
            prompt="請輸入新的遊戲角色名稱",
            examples=["/修改 暗黑騎士", "/修改 風之旅人"]
        )

    new_game_name = args.strip()
    if len(new_game_name) > 100:
        return create_error_message(
            "遊戲名稱過長（最多 100 字）",
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
            prompt="請輸入要搜尋的名稱\n可使用 LINE 名稱或遊戲名稱",
            examples=["/查詢 小明", "/查詢 勇者"]
        )

    query = args.strip()
    results = db.search_member(query)

    return create_search_result_message(query, results)


def handle_roster(line_user_id: str, args: str):
    """處理 /名冊 指令（僅限管理員）"""
    if not db.is_admin(line_user_id):
        return create_error_message(
            "此指令僅限幹部使用",
            quick_actions=[
                {'label': '我的資料', 'text': '/我是誰'},
                {'label': '查看說明', 'text': '/說明'}
            ]
        )

    show_all = False
    page = 1

    if args:
        args = args.strip()
        if args in ['全部', '所有', 'all']:
            show_all = True
        else:
            try:
                page = int(args)
            except ValueError:
                pass

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


def handle_delete(line_user_id: str, args: str):
    """處理 /刪除 指令（僅限管理員）"""
    if not db.is_admin(line_user_id):
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
            prompt="請輸入要刪除的成員名稱\n可使用 LINE 名稱或遊戲名稱",
            examples=["/刪除 小明", "/刪除 勇者123"]
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


def handle_set_admin(line_user_id: str, args: str):
    """處理 /設定管理員 指令（僅限管理員）"""
    admin_count = db.get_admin_count()

    if admin_count == 0:
        member = db.get_member_by_user_id(line_user_id)
        if not member:
            return create_error_message(
                "請先登記後，再使用此指令成為第一位管理員",
                quick_actions=[
                    {'label': '立即登記', 'text': '/登記'}
                ]
            )

        from database import get_db_cursor
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

    if not db.is_admin(line_user_id):
        return create_error_message(
            "此指令僅限管理員使用",
            quick_actions=[
                {'label': '查看說明', 'text': '/說明'}
            ]
        )

    if not args:
        return create_input_prompt_message(
            command="設定管理員",
            prompt="請輸入要設為幹部的成員名稱\n可使用 LINE 名稱或遊戲名稱",
            examples=["/設定管理員 小明", "/設定管理員 勇者123"]
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


def handle_register_for(line_user_id: str, args: str):
    """處理 /代登記 指令（僅限管理員）"""
    if not db.is_admin(line_user_id):
        return create_error_message(
            "此指令僅限幹部使用",
            quick_actions=[
                {'label': '查看說明', 'text': '/說明'}
            ]
        )

    if not args:
        return create_input_prompt_message(
            command="代登記",
            prompt="幫其他成員登記\n\n格式：\n/代登記 [LINE名稱] [遊戲名稱]\n/代登記 [LINE名稱] [遊戲名稱] 幹部\n/代登記 [LINE名稱] 幹部\n\n只輸入「幹部」時，遊戲名稱自動用 LINE 名稱",
            examples=[
                "/代登記 小明 勇者123",
                "/代登記 小明 勇者123 幹部",
                "/代登記 小明 幹部"
            ]
        )

    parts = args.strip().split()
    if len(parts) < 1:
        return create_error_message(
            "請輸入 LINE 名稱",
            quick_actions=[
                {'label': '查看說明', 'text': '/說明'}
            ]
        )

    line_name = parts[0]

    # 判斷格式
    if len(parts) == 1:
        # /代登記 小明 → 用 LINE 名稱作為遊戲名稱
        game_name = None  # 會在 db 函數中用 LINE 名稱
        set_as_admin = False
    elif len(parts) == 2:
        if parts[1] in ['幹部', '管理員', 'admin']:
            # /代登記 小明 幹部 → 用 LINE 名稱作為遊戲名稱，設為幹部
            game_name = None
            set_as_admin = True
        else:
            # /代登記 小明 勇者123
            game_name = parts[1]
            set_as_admin = False
    else:
        # /代登記 小明 勇者123 幹部
        game_name = parts[1]
        set_as_admin = parts[2] in ['幹部', '管理員', 'admin']

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


def process_command(line_user_id: str, line_display_name: str, text: str):
    """
    處理使用者指令
    回傳: LINE Message 物件，如果不是指令則回傳 None
    """
    text = text.strip()

    if not text.startswith('/'):
        return None

    # 分離指令和參數
    parts = text.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    # 指令路由
    if command == '/登記':
        return handle_register(line_user_id, line_display_name, args)
    elif command == '/修改':
        return handle_update(line_user_id, args)
    elif command == '/查詢':
        return handle_search(args)
    elif command == '/名冊':
        return handle_roster(line_user_id, args)
    elif command == '/刪除':
        return handle_delete(line_user_id, args)
    elif command == '/設定管理員':
        return handle_set_admin(line_user_id, args)
    elif command == '/代登記':
        return handle_register_for(line_user_id, args)
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
