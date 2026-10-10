"""
FAQ 自動回覆：問答放在 YAML（預設 config/faq.yaml），店家不用改程式就能新增或修改
比對順序：關鍵字（先把相似詞換成同一個詞）→ 與問題原文的相似度（容忍錯字與不同說法）
"""

import difflib
import re
import unicodedata
from dataclasses import dataclass

import yaml

DEFAULT_MIN_SIMILARITY = 0.7
# standalone 問答（問候、道謝）允許關鍵字以外再多幾個字，例如「謝謝你」「您好啊」
STANDALONE_EXTRA_CHARS = 2


def normalize(text: str) -> str:
    """全形轉半形、英文轉小寫，並去掉空白、標點與表情符號"""
    text = unicodedata.normalize('NFKC', text).lower()
    return ''.join(char for char in text if char.isalnum())


@dataclass(frozen=True)
class FaqEntry:
    id: str
    question: str
    answer: str
    keywords: tuple = ()
    standalone: bool = False  # True：訊息幾乎只有關鍵字時才回覆，避免「您好，我想取消訂單」被當成打招呼


@dataclass(frozen=True)
class FaqMatch:
    entry: FaqEntry
    method: str  # 'keyword'：關鍵字命中；'similar'：與問題原文相似
    score: float


class FaqBook:
    def __init__(self, entries, synonyms=None, min_similarity=DEFAULT_MIN_SIMILARITY):
        self.entries = list(entries)
        self.min_similarity = min_similarity

        # 相似詞 → 標準詞；一次替換、長的優先，避免短詞先把長詞拆開
        self._synonyms = {
            normalize(variant): normalize(word)
            for word, variants in (synonyms or {}).items()
            for variant in variants
            if normalize(variant)
        }
        variants = sorted(self._synonyms, key=len, reverse=True)
        self._synonym_pattern = re.compile('|'.join(map(re.escape, variants))) if variants else None

        self._keywords = {entry.id: [self.canonical(k) for k in entry.keywords] for entry in self.entries}
        self._questions = {entry.id: self.canonical(entry.question) for entry in self.entries}

    def canonical(self, text: str) -> str:
        """正規化並把相似詞換成標準詞"""
        text = normalize(text)
        if self._synonym_pattern:
            text = self._synonym_pattern.sub(lambda found: self._synonyms[found.group()], text)
        return text

    def get(self, entry_id: str):
        return next((entry for entry in self.entries if entry.id == entry_id), None)

    def match(self, text: str):
        """
        找出最符合的問答
        回傳: FaqMatch；比對不到時回傳 None
        """
        message = self.canonical(text)
        if not message:
            return None

        # 1. 關鍵字：命中的關鍵字越長、越多，分數越高；同分時取檔案中較前面的問答
        best = None
        for entry in self.entries:
            matched = [keyword for keyword in self._keywords[entry.id] if keyword and keyword in message]
            if entry.standalone:
                rest = message
                for keyword in matched:
                    rest = rest.replace(keyword, '')
                if len(rest) > STANDALONE_EXTRA_CHARS:
                    continue
            score = sum(len(keyword) for keyword in matched)
            if score and (best is None or score > best.score):
                best = FaqMatch(entry, 'keyword', score)
        if best:
            return best

        # 2. 沒有關鍵字命中時，比較訊息與問題原文的相似度
        for entry in self.entries:
            score = similarity(message, self._questions[entry.id])
            if score >= self.min_similarity and (best is None or score > best.score):
                best = FaqMatch(entry, 'similar', score)
        return best


def similarity(a: str, b: str) -> float:
    """相同的字數 ÷ 較長一方的字數；以較長的一方為分母，避免「可以嗎」這類短句誤配到「可以訂位嗎」"""
    if not a or not b:
        return 0.0
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    same = sum(block.size for block in matcher.get_matching_blocks())
    return same / max(len(a), len(b))


def load_faq(path) -> FaqBook:
    """讀取 FAQ 設定檔；格式錯誤時在啟動階段就丟出 ValueError"""
    with open(path, encoding='utf-8') as file:
        data = yaml.safe_load(file) or {}

    entries = []
    for index, item in enumerate(data.get('faqs') or [], start=1):
        if not isinstance(item, dict) or not all(item.get(key) for key in ('id', 'question', 'answer')):
            raise ValueError(f'{path}：第 {index} 筆 FAQ 需要 id、question 與 answer')
        entry_id = str(item['id'])
        if any(entry.id == entry_id for entry in entries):
            raise ValueError(f'{path}：FAQ id「{entry_id}」重複')
        entries.append(FaqEntry(
            id=entry_id,
            question=str(item['question']).strip(),
            answer=str(item['answer']).strip(),
            keywords=tuple(str(keyword) for keyword in item.get('keywords') or ()),
            standalone=bool(item.get('standalone', False)),
        ))

    return FaqBook(
        entries,
        synonyms=data.get('synonyms') or {},
        min_similarity=float(data.get('min_similarity', DEFAULT_MIN_SIMILARITY)),
    )
