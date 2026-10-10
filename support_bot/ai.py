"""
選配的 AI 回答（預設關閉，AI_ENABLED=true 才啟用）
- 呼叫任何 OpenAI 相容的 Chat Completions API（AI_BASE_URL、AI_API_KEY、AI_MODEL）
- 只把 FAQ 內容交給模型當作資料，並要求標註出處 [source:FAQ id]
- 模型回 NO_ANSWER、沒有標註出處、標註了不存在的出處或呼叫失敗時，一律改轉真人
"""

import json
import logging
import re
import urllib.request

logger = logging.getLogger(__name__)

NO_ANSWER = 'NO_ANSWER'
SOURCE_PATTERN = re.compile(r'\[source:\s*([^\]\s]+)\s*\]')

SYSTEM_PROMPT = (
    '你是店家 LINE 官方帳號的客服助理。只能根據使用者提供的「資料」回答，不可以使用資料以外的知識或自行推測。\n'
    '用繁體中文簡短回答，並在最後標註用到的資料編號，格式為 [source:編號]，例如 [source:hours]。\n'
    f'資料裡沒有答案時，只回覆 {NO_ANSWER}，不要加任何其他文字。'
)


class OpenAICompatibleClient:
    """最小的 Chat Completions 用戶端，只用標準函式庫"""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 15):
        self.url = base_url.rstrip('/') + '/chat/completions'
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete(self, messages: list) -> str:
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        payload = json.dumps({'model': self.model, 'messages': messages, 'temperature': 0}).encode('utf-8')
        request = urllib.request.Request(self.url, data=payload, headers=headers, method='POST')
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.load(response)
        return data['choices'][0]['message']['content']


class AiAnswerer:
    def __init__(self, client, faq):
        self.client = client  # 需要有 complete(messages) -> str；測試時換成假模型
        self.faq = faq

    def build_messages(self, question: str) -> list:
        sources = '\n\n'.join(
            f'[{entry.id}]\n問：{entry.question}\n答：{entry.answer}' for entry in self.faq.entries
        )
        return [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': f'資料：\n{sources}\n\n顧客的問題：{question}'},
        ]

    def answer(self, question: str):
        """回傳附出處的回答；無法根據 FAQ 回答時回傳 None（交給轉真人）"""
        try:
            content = self.client.complete(self.build_messages(question))
        except Exception:
            logger.exception('AI 回答失敗，改轉真人')
            return None

        cited_ids = list(dict.fromkeys(SOURCE_PATTERN.findall(content)))
        sources = [self.faq.get(entry_id) for entry_id in cited_ids]
        text = SOURCE_PATTERN.sub('', content).strip()
        if NO_ANSWER in content or not text or not sources or None in sources:
            return None

        titles = '、'.join(f'「{entry.question}」' for entry in sources)
        return f'{text}\n\n📖 出處：常見問題{titles}（AI 依常見問題整理）'
