"""Synthetic carryability evidence; no official data, network or model calls."""
import pytest
from app.services.waste_guide_service import RetrievedDocument, WasteGuideService


EVIDENCE = ('品目: 大きな家具\n分類コード: \n分類: 運搬条件で判断\n'
            '条件付き分類コード: ["bulky", "not_collected"]\n'
            '出し方・注意: 大人1人で持ち運べる家具は「粗大」。'
            '大人1人で持ち運びできない家具は「禁止」。')


def question(query, clarifications=(), evidence=EVIDENCE):
    return WasteGuideService._carry_condition_question(query=query,
        clarifications=list(clarifications),documents=[RetrievedDocument(evidence)])


def test_material_answer_does_not_confirm_carryability():
    assert question('大きな壊れた家具', [{'question':'素材は何ですか？','answer':'木材'}])
    assert question('大きな家具', [{'question':'木製ですか？','answer':'はい'}])


@pytest.mark.parametrize('query', ['大人1人で運べます','大人1人では運べません',
    '45リットルの袋に入らない木製家具。大人1人で運べます。','大人一人で持ち運べない家具'])
def test_explicit_positive_or_negative_carry_answer_is_used(query):
    assert question(query) is None


@pytest.mark.parametrize('answer', ['はい','いいえ','はい、運べます。','運べません'])
def test_short_answer_binds_to_the_carry_question(answer):
    assert question('大きな家具', [{'question':'大人1人で持ち運べますか？','answer':answer}]) is None


@pytest.mark.parametrize('query', ['1人で運べるか分かりません','大人1人で運べるか不明です',
    '1人で持ち運べると思う','2人なら運べます'])
def test_unknown_or_other_condition_is_not_confirmation(query):
    assert question(query)


@pytest.mark.parametrize('evidence', [
    EVIDENCE.replace('分類コード: \n', '分類コード: bulky\n'),
    EVIDENCE.replace('["bulky", "not_collected"]', '["粗大", "禁止"]'),
    EVIDENCE.replace('大人1人', '収集業者'),
    EVIDENCE.replace('["bulky", "not_collected"]', '["bulky"]'),
    EVIDENCE.replace('["bulky", "not_collected"]', 'invalid'),
    EVIDENCE.replace('["bulky", "not_collected"]', '[[]]'),
])
def test_unrelated_fixed_or_legacy_evidence_does_not_opt_in(evidence):
    assert question('大きな家具',evidence=evidence) is None
