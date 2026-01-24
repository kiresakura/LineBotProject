import database as db


def handle_register(line_user_id: str, line_display_name: str, args: str) -> str:
    """處理 /登記 指令"""
    if not args:
        return "❌ 請輸入遊戲名稱\n格式：/登記 [遊戲名稱]"

    game_name = args.strip()
    if len(game_name) > 100:
        return "❌ 遊戲名稱過長（最多 100 字）"

    result = db.register_member(line_user_id, line_display_name, game_name)

    if result['success']:
        return f"✅ {result['message']}"
    else:
        return f"❌ {result['message']}"


def handle_update(line_user_id: str, args: str) -> str:
    """處理 /修改 指令"""
    if not args:
        return "❌ 請輸入新的遊戲名稱\n格式：/修改 [新遊戲名稱]"

    new_game_name = args.strip()
    if len(new_game_name) > 100:
        return "❌ 遊戲名稱過長（最多 100 字）"

    result = db.update_game_name(line_user_id, new_game_name)

    if result['success']:
        return f"✅ {result['message']}"
    else:
        return f"❌ {result['message']}"


def handle_search(args: str) -> str:
    """處理 /查詢 指令"""
    if not args:
        return "❌ 請輸入要查詢的名稱\n格式：/查詢 [LINE名稱或遊戲名稱]"

    query = args.strip()
    results = db.search_member(query)

    if not results:
        return f"📋 查無「{query}」的相關結果"

    lines = [f"📋 查詢「{query}」的結果：", ""]
    for member in results:
        lines.append(f"• {member['line_display_name']} ↔ {member['game_name']}")

    return "\n".join(lines)


def handle_roster(args: str) -> str:
    """處理 /名冊 指令"""
    page = 1
    if args:
        try:
            page = int(args.strip())
        except ValueError:
            pass

    data = db.get_all_members(page=page)

    if data['total'] == 0:
        return "📋 目前沒有任何登記資料"

    lines = [f"📋 成員名冊 (第 {data['page']}/{data['total_pages']} 頁，共 {data['total']} 人)", ""]

    start_num = (data['page'] - 1) * 20 + 1
    for i, member in enumerate(data['members'], start=start_num):
        lines.append(f"{i}. {member['line_display_name']} ↔ {member['game_name']}")

    if data['total_pages'] > 1:
        lines.append("")
        lines.append(f"輸入 /名冊 [頁數] 查看其他頁")

    return "\n".join(lines)


def handle_delete(line_user_id: str, args: str) -> str:
    """處理 /刪除 指令（僅限管理員）"""
    if not db.is_admin(line_user_id):
        return "❌ 此指令僅限管理員使用"

    if not args:
        return "❌ 請輸入要刪除的成員名稱\n格式：/刪除 [遊戲名稱或LINE名稱]"

    query = args.strip()
    result = db.delete_member(query)

    if result['success']:
        return f"✅ {result['message']}"
    else:
        return f"❌ {result['message']}"


def handle_set_admin(line_user_id: str, args: str) -> str:
    """處理 /設定管理員 指令（僅限管理員）"""
    # 檢查是否有管理員存在，如果沒有則第一個使用此指令的人成為管理員
    admin_count = db.get_admin_count()

    if admin_count == 0:
        # 沒有管理員，需要先自己登記才能成為管理員
        member = db.get_member_by_user_id(line_user_id)
        if not member:
            return "❌ 請先使用 /登記 [遊戲名稱] 登記後，再使用此指令成為第一位管理員"

        # 將自己設為管理員
        from database import get_db_cursor
        with get_db_cursor() as cursor:
            cursor.execute('''
                UPDATE members
                SET is_admin = TRUE, updated_at = NOW()
                WHERE line_user_id = %s
            ''', (line_user_id,))

        return f"✅ 你已成為第一位管理員！\n現在可以使用 /設定管理員 [遊戲名稱] 來新增其他管理員"

    # 已有管理員，檢查權限
    if not db.is_admin(line_user_id):
        return "❌ 此指令僅限管理員使用"

    if not args:
        return "❌ 請輸入要設定為管理員的遊戲名稱\n格式：/設定管理員 [遊戲名稱]"

    game_name = args.strip()
    result = db.set_admin(game_name)

    if result['success']:
        return f"✅ {result['message']}"
    else:
        return f"❌ {result['message']}"


def handle_whoami(line_user_id: str, line_display_name: str) -> str:
    """處理 /我是誰 指令"""
    member = db.get_member_by_user_id(line_user_id)

    if not member:
        return f"📋 你尚未登記\nLINE 名稱：{line_display_name}\n\n請使用 /登記 [遊戲名稱] 進行登記"

    admin_text = "（管理員）" if member['is_admin'] else ""

    return f"📋 你的登記資訊 {admin_text}\nLINE 名稱：{member['line_display_name']}\n遊戲名稱：{member['game_name']}"


def handle_help() -> str:
    """處理 /說明 或 /help 指令"""
    return """📋 指令說明

/登記 [遊戲名稱]
  綁定你的 LINE 與遊戲角色名稱

/修改 [新遊戲名稱]
  修改你的遊戲名稱

/查詢 [名稱]
  搜尋成員（可用 LINE 或遊戲名稱）

/名冊
  顯示所有已登記成員

/我是誰
  查看自己的登記資訊

/說明
  顯示此說明訊息

【管理員指令】
/刪除 [名稱] - 刪除成員
/設定管理員 [遊戲名稱] - 新增管理員"""


def process_command(line_user_id: str, line_display_name: str, text: str) -> str:
    """
    處理使用者指令
    回傳: 回覆訊息，如果不是指令則回傳 None
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
        return handle_roster(args)
    elif command == '/刪除':
        return handle_delete(line_user_id, args)
    elif command == '/設定管理員':
        return handle_set_admin(line_user_id, args)
    elif command == '/我是誰':
        return handle_whoami(line_user_id, line_display_name)
    elif command in ['/說明', '/help', '/幫助']:
        return handle_help()
    else:
        return None  # 未知指令不回覆
