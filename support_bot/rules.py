"""
營業時間與固定回覆規則（預設 config/rules.yaml）
- business_hours：每週營業時段，結束時間早於開始時間代表營業到隔天
- closed_dates：臨時公休日
- keyword_replies：訊息含特定關鍵字時回固定內容（優先於 FAQ）
- handoff_reply / after_hours_reply：答不出來、要轉真人時的回覆（營業中／非營業時間）
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import yaml

from support_bot.faq import normalize

WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']


@dataclass(frozen=True)
class KeywordReply:
    keywords: tuple
    reply: str


@dataclass(frozen=True)
class Rules:
    timezone: ZoneInfo
    business_hours: dict  # 星期幾（0 = 週一）→ [(開始, 結束), ...]
    closed_dates: frozenset
    handoff_reply: str
    after_hours_reply: str
    keyword_replies: tuple = ()

    def _periods(self, day: date):
        if day in self.closed_dates:
            return []
        return self.business_hours.get(day.weekday(), [])

    def is_open(self, moment: datetime) -> bool:
        """moment 是否在營業時間內（以店家時區判斷）"""
        local = moment.astimezone(self.timezone)
        today, now = local.date(), local.time()

        for start, end in self._periods(today):
            if start <= now and (now < end or end <= start):
                return True
        # 前一天營業到今天凌晨的時段
        for start, end in self._periods(today - timedelta(days=1)):
            if end <= start and now < end:
                return True
        return False

    def keyword_reply(self, text: str):
        """訊息含任一關鍵字時回傳固定回覆，否則回傳 None"""
        message = normalize(text)
        for rule in self.keyword_replies:
            if any(normalize(keyword) and normalize(keyword) in message for keyword in rule.keywords):
                return rule.reply
        return None


def parse_periods(value, where: str):
    """解析「10:00-14:00, 17:00-21:00」；closed、空白或 false 代表不營業"""
    if value in (None, False, '') or str(value).strip().lower() == 'closed':
        return []

    periods = []
    for part in (value if isinstance(value, list) else str(value).split(',')):
        try:
            start, end = (datetime.strptime(piece.strip(), '%H:%M').time() for piece in str(part).split('-'))
        except ValueError:
            raise ValueError(f'{where}：「{part}」格式應為 HH:MM-HH:MM') from None
        periods.append((start, end))
    return periods


def load_rules(path) -> Rules:
    """讀取規則設定檔；格式錯誤時在啟動階段就丟出 ValueError"""
    with open(path, encoding='utf-8') as file:
        data = yaml.safe_load(file) or {}

    hours = data.get('business_hours') or {}
    unknown_days = set(hours) - set(WEEKDAYS)
    if unknown_days:
        raise ValueError(f'{path}：business_hours 只能使用 {", ".join(WEEKDAYS)}，收到 {sorted(unknown_days)}')

    for key in ('handoff_reply', 'after_hours_reply'):
        if not data.get(key):
            raise ValueError(f'{path}：缺少 {key}')

    keyword_replies = []
    for index, item in enumerate(data.get('keyword_replies') or [], start=1):
        if not isinstance(item, dict) or not item.get('keywords') or not item.get('reply'):
            raise ValueError(f'{path}：keyword_replies 第 {index} 筆需要 keywords 與 reply')
        keyword_replies.append(KeywordReply(tuple(str(k) for k in item['keywords']), str(item['reply']).strip()))

    return Rules(
        timezone=ZoneInfo(data.get('timezone', 'Asia/Taipei')),
        business_hours={
            WEEKDAYS.index(day): parse_periods(value, f'{path} business_hours.{day}')
            for day, value in hours.items()
        },
        closed_dates=frozenset(
            day if isinstance(day, date) else date.fromisoformat(str(day))
            for day in data.get('closed_dates') or []
        ),
        handoff_reply=str(data['handoff_reply']).strip(),
        after_hours_reply=str(data['after_hours_reply']).strip(),
        keyword_replies=tuple(keyword_replies),
    )

