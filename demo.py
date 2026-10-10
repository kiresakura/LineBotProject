"""
本機示範模式：不需要 LINE 帳號、金鑰或 PostgreSQL，在終端機模擬群組對話

用法：
    python demo.py                           # 互動模式，Ctrl-D 結束
    python demo.py examples/demo-chat.txt    # 重播對話腳本

每行格式為「名稱: 訊息」，例如「小明: /登記 光之勇者」；省略「名稱:」時沿用上一位發言者。
資料存在本機 SQLite，預設為暫存檔，結束後刪除；加上 --db 路徑可保留資料。
"""

import argparse
import os
import sys
import tempfile

import database as db
from handlers import handle_text

DEFAULT_SPEAKER = '小明'


def split_speaker(line: str, current_speaker: str):
    """拆出「名稱: 訊息」；沒有名稱時沿用目前的發言者"""
    name, separator, text = line.partition(':')
    name = name.strip()
    if separator and name and not name.startswith('/'):
        return name, text.strip()
    return current_speaker, line.strip()


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


def chat(lines, echo: bool = False):
    """逐行模擬群組發言，印出機器人的回覆"""
    speaker = DEFAULT_SPEAKER
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue

        speaker, text = split_speaker(line, speaker)
        if echo:
            print(f'{speaker}: {text}')

        reply = handle_text(f'demo-{speaker}', speaker, text)
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
    parser = argparse.ArgumentParser(description='不需要 LINE 帳號的本機示範：在終端機模擬群組對話')
    parser.add_argument('script', nargs='?', help='要重播的對話腳本；省略時進入互動模式')
    parser.add_argument('--db', help='SQLite 檔案路徑（要保留資料時使用）；省略時使用暫存檔')
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp_dir:
        # 示範一律使用本機 SQLite，不會連到正式資料庫
        db_path = args.db or os.path.join(tmp_dir, 'demo.db')
        os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
        db.init_db()

        if args.script:
            with open(args.script, encoding='utf-8') as script:
                chat(script, echo=True)
        else:
            print('輸入「名稱: 訊息」模擬群組發言，例如「小明: /登記 光之勇者」；Ctrl-D 結束')
            chat(read_terminal())
    return 0


if __name__ == '__main__':
    sys.exit(main())
