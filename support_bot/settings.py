"""
執行設定：一律從環境變數讀取（金鑰不寫進程式或設定檔）
FAQ 與規則的內容放在 YAML，路徑可用 FAQ_FILE、RULES_FILE 覆寫
"""

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FAQ_FILE = str(PROJECT_ROOT / 'config' / 'faq.yaml')
DEFAULT_RULES_FILE = str(PROJECT_ROOT / 'config' / 'rules.yaml')


def parse_flag(value) -> bool:
    return (value or '').strip().lower() in ('1', 'true', 'yes', 'on')


def parse_id_list(value) -> frozenset:
    return frozenset(part.strip() for part in (value or '').split(',') if part.strip())


@dataclass(frozen=True)
class Settings:
    line_channel_secret: str = ''
    line_channel_access_token: str = ''
    faq_file: str = DEFAULT_FAQ_FILE
    rules_file: str = DEFAULT_RULES_FILE
    admin_user_ids: frozenset = frozenset()
    roster_enabled: bool = False
    handoff_notifier: str = 'log'

    @classmethod
    def from_env(cls, environ=None) -> 'Settings':
        env = os.environ if environ is None else environ
        return cls(
            line_channel_secret=env.get('LINE_CHANNEL_SECRET', ''),
            line_channel_access_token=env.get('LINE_CHANNEL_ACCESS_TOKEN', ''),
            faq_file=env.get('FAQ_FILE') or DEFAULT_FAQ_FILE,
            rules_file=env.get('RULES_FILE') or DEFAULT_RULES_FILE,
            admin_user_ids=parse_id_list(env.get('ADMIN_USER_IDS')),
            roster_enabled=parse_flag(env.get('ROSTER_ENABLED')),
            handoff_notifier=(env.get('HANDOFF_NOTIFIER') or 'log').strip().lower(),
        )
