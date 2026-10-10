"""
訊息處理流程（Webhook 與本機示範共用；不直接呼叫 LINE API，回傳要回覆的 LINE 訊息物件或 None）

一對一聊天：管理指令 → 群組名冊指令（有開啟時）→ 固定關鍵字 → FAQ → AI 回答（有開啟時）→ 轉真人
群組／多人聊天室：只處理群組名冊指令，其他訊息不回覆以免洗版；管理指令只能在一對一聊天使用
"""

import logging
from datetime import datetime, timezone

from linebot.v3.messaging import TextMessage

from support_bot import database as db
from support_bot import roster
from support_bot.ai import AiAnswerer, OpenAICompatibleClient
from support_bot.faq import load_faq
from support_bot.handoff import LinePushNotifier, LogNotifier
from support_bot.rules import load_rules

logger = logging.getLogger(__name__)

PRIVATE_CHAT = 'user'
ADMIN_COMMANDS = ('/待處理', '/完成')


class SupportBot:
    def __init__(self, faq, rules, notifier, admin_user_ids=frozenset(), roster_enabled=False, answerer=None,
                 clock=None):
        self.faq = faq
        self.rules = rules
        self.notifier = notifier
        self.admin_user_ids = set(admin_user_ids)
        self.roster_enabled = roster_enabled
        self.answerer = answerer
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def reply(self, user_id: str, display_name: str, text: str, chat_type: str = PRIVATE_CHAT):
        """
        處理一則文字訊息
        chat_type: LINE 事件來源類型（user 為一對一聊天，另有 group、room）
        """
        is_private = chat_type == PRIVATE_CHAT
        command = roster.parse_command(text)

        if is_private and command and command[0] in ADMIN_COMMANDS:
            return self.admin_command(user_id, *command)

        if self.roster_enabled:
            reply = roster.handle_text(user_id, display_name, text, frozenset(self.admin_user_ids))
            if reply is not None:
                return reply

        if not is_private:
            return None

        fixed_reply = self.rules.keyword_reply(text)
        if fixed_reply:
            return TextMessage(text=fixed_reply)

        match = self.faq.match(text)
        if match:
            return TextMessage(text=match.entry.answer)

        if self.answerer:
            ai_reply = self.answerer.answer(text)
            if ai_reply:
                return TextMessage(text=ai_reply)

        return self.hand_off(user_id, display_name, text)

    def hand_off(self, user_id: str, display_name: str, text: str):
        """記錄到待處理清單、通知管理員，並依營業時間回覆顧客"""
        now = self.clock()
        request = db.create_handoff(
            user_id, display_name, text,
            now.astimezone(self.rules.timezone).strftime('%Y-%m-%d %H:%M')
        )
        try:
            self.notifier.notify(request)
        except Exception:
            # 通知失敗不影響回覆顧客，訊息仍在待處理清單
            logger.exception('轉真人通知失敗 #%s', request['id'])

        reply = self.rules.handoff_reply if self.rules.is_open(now) else self.rules.after_hours_reply
        return TextMessage(text=reply)

    def admin_command(self, user_id: str, command: str, args: str):
        """管理指令：/待處理 列出轉真人的訊息，/完成 編號 標記已處理；限 ADMIN_USER_IDS 白名單"""
        if user_id not in self.admin_user_ids:
            return TextMessage(text='❌ 此指令僅限管理員使用')

        if command == '/待處理':
            requests = db.list_open_handoffs()
            if not requests:
                return TextMessage(text='✅ 目前沒有待處理的訊息')
            lines = [f'📋 待處理 {len(requests)} 筆（由舊到新）']
            for request in requests:
                lines.append(f"#{request['id']} {request['created_at'][5:].replace('-', '/')} {request['display_name']}")
                lines.append(f"   {request['message'][:60]}")
            lines.append('處理完請回覆 /完成 編號')
            return TextMessage(text='\n'.join(lines))

        try:
            request_id = int(args.strip().lstrip('#'))
        except ValueError:
            return TextMessage(text='❌ 請輸入編號，例如：/完成 1')
        if db.resolve_handoff(request_id):
            return TextMessage(text=f'✅ 已將 #{request_id} 標記為完成')
        return TextMessage(text=f'❌ 找不到未處理的 #{request_id}')


def build_bot(settings, push=None, clock=None) -> SupportBot:
    """
    依設定建立 SupportBot；設定有誤時在啟動階段就丟出 ValueError
    push: 推播給管理員的函式（HANDOFF_NOTIFIER=line_push 時使用）
    """
    if settings.handoff_notifier == 'log':
        notifier = LogNotifier()
    elif settings.handoff_notifier == 'line_push':
        if not settings.admin_user_ids:
            raise ValueError('HANDOFF_NOTIFIER=line_push 需要設定 ADMIN_USER_IDS（接收通知的管理員）')
        notifier = LinePushNotifier(push, settings.admin_user_ids)
    else:
        raise ValueError(f'HANDOFF_NOTIFIER 只能是 log 或 line_push，收到「{settings.handoff_notifier}」')

    faq = load_faq(settings.faq_file)
    answerer = None
    if settings.ai_enabled:
        if not settings.ai_model:
            raise ValueError('AI_ENABLED=true 時需要設定 AI_MODEL')
        client = OpenAICompatibleClient(settings.ai_base_url, settings.ai_api_key, settings.ai_model)
        answerer = AiAnswerer(client, faq)

    return SupportBot(
        faq=faq,
        rules=load_rules(settings.rules_file),
        notifier=notifier,
        admin_user_ids=settings.admin_user_ids,
        roster_enabled=settings.roster_enabled,
        answerer=answerer,
        clock=clock,
    )
