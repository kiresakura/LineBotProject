"""
本機示範模式：不需要 LINE 帳號、金鑰或資料庫伺服器，用範例設定重播一段對話並印出回覆

用法：
    python -m support_bot.demo                                # 重播 examples/demo-shop.txt（虛構咖啡店的客服對話）
    python -m support_bot.demo examples/demo-group.txt        # 重播群組名冊模組的示範
    python -m support_bot.demo --interactive                  # 自己輸入訊息，Ctrl-D 結束

腳本每行「名稱: 訊息」；省略「名稱:」時沿用上一位發言者；# 開頭為註解。
以 @ 開頭的是示範用的設定：
    @time 2026-10-13 14:00    模擬目前時間（店家時區），用來示範營業時間
    @group / @private         切換為群組聊天／一對一聊天（預設一對一）
    @admin 店長               把這位發言者加入管理員白名單
資料存在本機 SQLite 暫存檔，結束後刪除；加上 --db 路徑可保留資料。
"""

import argparse
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone

from support_bot import database as db
from support_bot.bot import build_bot
from support_bot.settings import DEFAULT_FAQ_FILE, DEFAULT_RULES_FILE, PROJECT_ROOT, Settings

DEFAULT_SCRIPT = str(PROJECT_ROOT / 'examples' / 'demo-shop.txt')
DEFAULT_SPEAKER = '客人'
WEEKDAY_NAMES = '一二三四五六日'


def split_speaker(line: str, current_speaker: str):
    """拆出「名稱: 訊息」；沒有名稱時沿用目前的發言者"""
    name, separator, text = line.partition(':')
    name = name.strip()
    if separator and name and not name.startswith('/'):
        return name, text.strip()
    return current_speaker, line.strip()


def user_id_of(name: str) -> str:
    return f'demo-{name}'


def flex_lines(component: dict) -> list:
    """把 Flex 元件轉成文字行，同一列（horizontal）的內容放在同一行"""
    kind = component.get('type')
    if kind == 'text':
        return [component['text']]
    if kind == 'button':
        return [f"[{component['action']['label']}]"]
    if kind == 'bubble':
        sections = [component[key] for key in ('header', 'body', 'footer') if key in component]
        return [line for section in sections for line in flex_lines(section)]
    if kind == 'box':
        lines = [line for child in component['contents'] for line in flex_lines(child)]
        if component.get('layout') == 'horizontal' and lines:
            return [' '.join(lines)]
        return lines
    return []


def render(message) -> str:
    """把 LINE 訊息物件轉成終端機可讀的文字"""
    data = message.to_dict()
    if data['type'] == 'flex':
        lines = flex_lines(data['contents'])
    else:
        lines = data['text'].split('\n')

    quick_reply = data.get('quickReply')
    if quick_reply:
        lines.append(' '.join(f"[{item['action']['label']}]" for item in quick_reply['items']))
    return '\n'.join(lines)


class Demo:
    def __init__(self, bot):
        self.bot = bot
        self.now = datetime.now(timezone.utc)
        bot.clock = lambda: self.now
        self.chat_type = 'user'
        self.speaker = DEFAULT_SPEAKER

    def directive(self, line: str):
        """處理 @time、@group、@private、@admin"""
        name, _, value = line[1:].partition(' ')
        value = value.strip()
        if name == 'time':
            self.now = datetime.strptime(value, '%Y-%m-%d %H:%M').replace(tzinfo=self.bot.rules.timezone)
            state = '營業中' if self.bot.rules.is_open(self.now) else '非營業時間'
            print(f'🕑 {self.now:%Y-%m-%d}（{WEEKDAY_NAMES[self.now.weekday()]}）{self.now:%H:%M}，{state}')
        elif name in ('group', 'private'):
            self.chat_type = 'group' if name == 'group' else 'user'
            print('── 群組聊天 ──' if name == 'group' else '── 一對一聊天 ──')
        elif name == 'admin':
            self.bot.admin_user_ids.add(user_id_of(value))
            print(f'⚙️  管理員白名單：{value}')
        else:
            raise ValueError(f'不認得的示範設定：{line}')
        print()

    def chat(self, lines, echo: bool = False):
        """逐行模擬發言，印出機器人的回覆"""
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('@'):
                self.directive(line)
                continue

            self.speaker, text = split_speaker(line, self.speaker)
            if echo:
                print(f'{self.speaker}: {text}')

            reply = self.bot.reply(user_id_of(self.speaker), self.speaker, text, chat_type=self.chat_type)
            if reply is not None:
                first_line, *other_lines = render(reply).split('\n')
                print(f'🤖 {first_line}')
                for other_line in other_lines:
                    print(f'   {other_line}' if other_line else '')
            print()


def read_terminal():
    """互動模式：逐行讀取鍵盤輸入，Ctrl-D 或 Ctrl-C 結束"""
    while True:
        try:
            yield input('> ')
        except (EOFError, KeyboardInterrupt):
            print()
            return


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='不需要 LINE 帳號的本機示範：用範例設定重播一段對話')
    parser.add_argument('script', nargs='?', default=DEFAULT_SCRIPT, help='要重播的對話腳本（預設：虛構咖啡店的客服對話）')
    parser.add_argument('-i', '--interactive', action='store_true', help='自己輸入訊息，不重播腳本')
    parser.add_argument('--faq', default=DEFAULT_FAQ_FILE, help='FAQ 設定檔（預設 config/faq.yaml）')
    parser.add_argument('--rules', default=DEFAULT_RULES_FILE, help='規則設定檔（預設 config/rules.yaml）')
    parser.add_argument('--db', help='SQLite 檔案路徑（要保留資料時使用）；省略時使用暫存檔')
    args = parser.parse_args(argv)

    # 轉真人通知預設寫 log；示範時把這些 log 印在畫面上
    notice = logging.StreamHandler(sys.stdout)
    notice.setFormatter(logging.Formatter('🔔 通知管理員（log）：%(message)s'))
    handoff_logger = logging.getLogger('support_bot.handoff')
    handoff_logger.addHandler(notice)

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 示範一律使用本機 SQLite，不會連到正式資料庫
            os.environ['DATABASE_URL'] = f"sqlite:///{args.db or os.path.join(tmp_dir, 'demo.db')}"
            db.init_db()
            demo = Demo(build_bot(Settings(faq_file=args.faq, rules_file=args.rules, roster_enabled=True)))

            if args.interactive:
                print('輸入「名稱: 訊息」模擬發言，例如「王小姐: 營業到幾點？」；@ 開頭的示範設定見 --help；Ctrl-D 結束')
                demo.chat(read_terminal())
            else:
                with open(args.script, encoding='utf-8') as script:
                    demo.chat(script, echo=True)
    finally:
        handoff_logger.removeHandler(notice)
    return 0


if __name__ == '__main__':
    sys.exit(main())
