"""FAQ 比對：關鍵字、相似詞、相似度與設定檔驗證"""

from pathlib import Path

import pytest

from support_bot.faq import FaqBook, FaqEntry, load_faq, normalize, similarity

EXAMPLE_FAQ = Path(__file__).resolve().parent.parent / 'config' / 'faq.yaml'


@pytest.fixture(scope='module')
def faq():
    return load_faq(EXAMPLE_FAQ)


def matched_id(faq, text):
    match = faq.match(text)
    return match.entry.id if match else None


def test_normalize_folds_width_case_and_punctuation():
    assert normalize('Ｗｉ－Ｆｉ　有嗎？') == 'wifi有嗎'


@pytest.mark.parametrize('text, expected', [
    ('請問營業到幾點？', 'hours'),
    ('你們地址在哪', 'location'),
    ('可以刷卡嗎', 'payment'),
    ('想外帶兩杯拿鐵', 'takeout'),
    ('有 WiFi 嗎', 'wifi'),
])
def test_keyword_match(faq, text, expected):
    match = faq.match(text)

    assert match.entry.id == expected
    assert match.method == 'keyword'


@pytest.mark.parametrize('text, expected', [
    ('可以帶毛小孩嗎', 'pets'),
    ('附近好泊車嗎', 'parking'),
    ('想預約週六下午', 'reservation'),
    ('有無線網路嗎', 'wifi'),
    ('店裡可以上網嗎', 'wifi'),
    ('可以網路預約嗎', 'reservation'),   # 「網路」不當成 Wi-Fi 的相似詞，否則會蓋過「預約」
])
def test_synonyms_map_to_keywords(faq, text, expected):
    assert matched_id(faq, text) == expected


def test_more_specific_keywords_win(faq):
    # 營業時間命中「幾點開」＋「開門」共 5 字，地址只命中「在哪」2 字
    assert matched_id(faq, '幾點開門？店在哪') == 'hours'


@pytest.mark.parametrize('text, expected', [
    ('你好', 'greeting'),
    ('您好啊！', 'greeting'),
    ('謝謝你', 'thanks'),
    ('你好，請問幾點開門', 'hours'),
    ('您好，我想取消訂單', None),        # 問候之外還有別的內容：不能只回打招呼
    ('嗨，可以包場嗎', None),
])
def test_standalone_entries_only_answer_short_messages(faq, text, expected):
    assert matched_id(faq, text) == expected


def test_similar_question_without_keywords(faq):
    match = faq.match('可以用什麼方式付費？')

    assert match.entry.id == 'payment'
    assert match.method == 'similar'
    assert match.score >= faq.min_similarity


@pytest.mark.parametrize('text', ['可以嗎', '週末可以包場辦生日派對嗎？', '我昨天掉了一把傘在店裡', '', '😀😀'])
def test_unrelated_or_vague_messages_do_not_match(faq, text):
    assert faq.match(text) is None


def test_similarity_uses_the_longer_text():
    assert similarity('可以嗎', '可以訂位嗎') == pytest.approx(3 / 5)
    assert similarity('abc', 'abc') == 1
    assert similarity('', 'abc') == 0


def test_ties_go_to_the_earlier_entry():
    faq = FaqBook([
        FaqEntry('first', '問題一', '答一', ('優惠',)),
        FaqEntry('second', '問題二', '答二', ('優惠',)),
    ])

    assert faq.match('有優惠嗎').entry.id == 'first'


def test_get_returns_entry_by_id(faq):
    assert faq.get('hours').question == '營業時間是幾點到幾點？'
    assert faq.get('missing') is None


def test_load_faq_rejects_missing_fields(tmp_path):
    path = tmp_path / 'faq.yaml'
    path.write_text('faqs:\n  - id: a\n    question: 問題\n', encoding='utf-8')

    with pytest.raises(ValueError, match='第 1 筆'):
        load_faq(path)


def test_load_faq_rejects_duplicate_ids(tmp_path):
    path = tmp_path / 'faq.yaml'
    path.write_text(
        'faqs:\n'
        '  - {id: a, question: 問題一, answer: 答一}\n'
        '  - {id: a, question: 問題二, answer: 答二}\n',
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='重複'):
        load_faq(path)
