"""營業時間判斷、固定關鍵字回覆與設定檔驗證"""

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from support_bot.rules import load_rules, parse_periods

EXAMPLE_RULES = Path(__file__).resolve().parent.parent / 'config' / 'rules.yaml'
TAIPEI = ZoneInfo('Asia/Taipei')


@pytest.fixture(scope='module')
def rules():
    return load_rules(EXAMPLE_RULES)


def taipei(text):
    return datetime.strptime(text, '%Y-%m-%d %H:%M').replace(tzinfo=TAIPEI)


@pytest.mark.parametrize('moment, expected', [
    ('2026-10-13 10:00', True),    # 週二開門
    ('2026-10-13 19:59', True),
    ('2026-10-13 20:00', False),   # 打烊時間不算營業
    ('2026-10-13 09:59', False),
    ('2026-10-12 14:00', False),   # 週一公休
    ('2026-12-31 14:00', False),   # 臨時公休日（週四）
])
def test_is_open_follows_weekly_hours_and_closed_dates(rules, moment, expected):
    assert rules.is_open(taipei(moment)) is expected


def test_is_open_converts_to_shop_timezone(rules):
    # UTC 02:00 = 台北 10:00（週二）
    assert rules.is_open(datetime(2026, 10, 13, 2, 0, tzinfo=timezone.utc))
    assert not rules.is_open(datetime(2026, 10, 13, 1, 59, tzinfo=timezone.utc))


def test_overnight_period_continues_after_midnight(tmp_path):
    path = tmp_path / 'rules.yaml'
    path.write_text(
        'business_hours:\n'
        '  fri: "18:00-02:00"\n'
        'handoff_reply: 轉真人\n'
        'after_hours_reply: 非營業時間\n',
        encoding='utf-8',
    )
    bar = load_rules(path)

    assert bar.is_open(taipei('2026-10-16 23:30'))       # 週五晚上
    assert bar.is_open(taipei('2026-10-17 01:59'))       # 週六凌晨，仍屬週五的時段
    assert not bar.is_open(taipei('2026-10-17 02:00'))
    assert not bar.is_open(taipei('2026-10-17 23:30'))   # 週六沒有營業


@pytest.mark.parametrize('value, expected', [
    ('closed', []),
    (False, []),              # YAML 的 off／no 會被讀成 false
    (None, []),
    ('10:00-14:00, 17:00-21:00', [('10:00', '14:00'), ('17:00', '21:00')]),
    (['09:30-12:00'], [('09:30', '12:00')]),
])
def test_parse_periods(value, expected):
    periods = [(start.strftime('%H:%M'), end.strftime('%H:%M')) for start, end in parse_periods(value, 'test')]

    assert periods == expected


@pytest.mark.parametrize('value', ['10-20', '10:00', '25:00-26:00'])
def test_parse_periods_rejects_bad_format(value):
    with pytest.raises(ValueError, match='HH:MM-HH:MM'):
        parse_periods(value, 'test')


def test_keyword_reply(rules):
    assert rules.keyword_reply('請給我 MENU').startswith('📋 菜單')
    assert rules.keyword_reply('最近有什麼優惠？').startswith('🎉')
    assert rules.keyword_reply('營業到幾點') is None


def test_load_rules_requires_handoff_replies(tmp_path):
    path = tmp_path / 'rules.yaml'
    path.write_text('handoff_reply: 轉真人\n', encoding='utf-8')

    with pytest.raises(ValueError, match='after_hours_reply'):
        load_rules(path)


def test_load_rules_rejects_unknown_weekday(tmp_path):
    path = tmp_path / 'rules.yaml'
    path.write_text(
        'business_hours:\n  monday: "10:00-20:00"\nhandoff_reply: a\nafter_hours_reply: b\n',
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='monday'):
        load_rules(path)
