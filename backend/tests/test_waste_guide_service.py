import json
from datetime import date

import pytest

from app.services.waste_guide_service import (
    BedrockGateway,
    ClassificationDecision,
    RetrievedDocument,
    UnsupportedRegionError,
    WasteGuideService,
)


class FakeAgentRuntime:
    def __init__(self):
        self.request = None

    def retrieve(self, **kwargs):
        self.request = kwargs
        return {"retrievalResults": []}


class FakeRuntime:
    def __init__(self, payload):
        self.payload = payload
        self.request = None

    def converse(self, **kwargs):
        self.request = kwargs
        return {
            "output": {
                "message": {"content": [{"text": json.dumps(self.payload)}]}
            }
        }


class FakeGateway:
    def __init__(self, decision: ClassificationDecision):
        self.decision = decision
        self.rewrite_calls = []
        self.classify_calls = []

    def rewrite_query(self, query, clarifications):
        self.rewrite_calls.append((query, clarifications))
        return "ペットボトル 飲料容器"

    def retrieve(self, query):
        return [
            RetrievedDocument(
                text="ペットボトルはペットボトルの日に出す",
                score=0.95,
                uri="s3://new-bucket/items.csv",
            )
        ]

    def classify(self, query, clarifications, documents):
        self.classify_calls.append((query, clarifications, documents))
        return self.decision


class EmptyItemSearch:
    def search(self, query, *, limit):
        return []


def test_managed_knowledge_base_uses_managed_search_configuration(monkeypatch):
    agent_runtime = FakeAgentRuntime()
    monkeypatch.setattr(
        "app.services.waste_guide_service.config.BEDROCK_KNOWLEDGE_BASE_ID",
        "FMPYJSHELD",
    )
    gateway = BedrockGateway(runtime_client=object(), agent_runtime_client=agent_runtime)

    assert gateway.retrieve("スプレー缶") == []
    assert agent_runtime.request["retrievalConfiguration"] == {
        "managedSearchConfiguration": {"numberOfResults": 8}
    }


def test_classification_requires_cited_evidence_supporting_category():
    payload = {
        "is_resolved": True,
        "item_name": "容器",
        "category_code": "プラ",
        "confidence": 0.95,
        "evidence_indexes": [1],
    }
    gateway = BedrockGateway(
        runtime_client=FakeRuntime(payload), agent_runtime_client=object()
    )

    unsupported = gateway.classify(
        "容器", [], [RetrievedDocument(text="品目: 金属製容器\n分類コード: 金・ガ")]
    )
    supported = gateway.classify(
        "容器", [], [RetrievedDocument(text="品目: 食品容器\n分類コード: プラ")]
    )

    assert unsupported.is_resolved is False
    assert supported.is_resolved is True
    assert supported.evidence_indexes == (1,)


def test_rewrite_removes_known_region_and_generic_search_terms():
    gateway = BedrockGateway(
        runtime_client=FakeRuntime(
            {"search_query": "松山市清水地区 汚れたびん ごみ分別"}
        ),
        agent_runtime_client=object(),
    )

    assert gateway.rewrite_query("汚れたびん", []) == "汚れたびん"


def test_rewrite_prompt_treats_transparent_bento_lid_as_disposable_container():
    runtime = FakeRuntime(
        {"search_query": "弁当・惣菜の透明なプラスチック製容器のふた"}
    )
    gateway = BedrockGateway(runtime_client=runtime, agent_runtime_client=object())

    rewritten = gateway.rewrite_query("お弁当の透明なフタ", [])

    prompt = runtime.request["messages"][0]["content"][0]["text"]
    assert rewritten == "弁当・惣菜の透明なプラスチック製容器のふた"
    assert "一般的な使い捨て" in prompt


def test_rewrite_removes_material_not_supported_by_user_input():
    gateway = BedrockGateway(
        runtime_client=FakeRuntime({"search_query": "汚れたプラスチック製のビン"}),
        agent_runtime_client=object(),
    )

    assert gateway.rewrite_query("汚れたビン", []) == "汚れたびん"


def test_rewrite_keeps_material_from_clarification():
    gateway = BedrockGateway(
        runtime_client=FakeRuntime({"search_query": "汚れたガラス製ビン"}),
        agent_runtime_client=object(),
    )

    rewritten = gateway.rewrite_query(
        "汚れたビン",
        [{"question": "何製ですか？", "answer": "ガラス"}],
    )

    assert rewritten == "汚れたガラス製びん"


def test_answered_result_includes_next_collection():
    gateway = FakeGateway(
        ClassificationDecision(
            is_resolved=True,
            item_name="ペットボトル",
            category_code="ペット",
            disposal_instructions="キャップとラベルを外して出してください。",
            confidence=0.96,
        )
    )
    service = WasteGuideService(
        gateway=gateway,
        item_search=EmptyItemSearch(),
        today_provider=lambda: date(2026, 8, 24),
    )

    result = service.query(
        query="飲み終わったペットボトルは？",
        municipality_id="38201",
        district_id="38201-08",
    )

    assert result.status == "answered"
    assert result.next_collection is not None
    assert result.next_collection.date == date(2026, 9, 2)
    assert "ペットボトル" in result.answer
    assert "2026年9月2日（水）" in result.answer
    assert result.sources[0].score == 0.95


def test_unresolved_result_returns_one_follow_up_question():
    gateway = FakeGateway(
        ClassificationDecision(
            is_resolved=False,
            confidence=0.4,
            clarifying_question="容器は紙製ですか、プラスチック製ですか？",
        )
    )
    service = WasteGuideService(gateway=gateway, item_search=EmptyItemSearch())

    result = service.query(
        query="アイスの容器",
        municipality_id="38201",
        district_id="38201-08",
    )

    assert result.status == "needs_clarification"
    assert result.answer is None
    assert result.follow_up_question == "容器は紙製ですか、プラスチック製ですか？"
    assert result.decision is not None
    assert result.decision.confidence == 0.4


def test_generic_container_is_asked_for_material_even_when_model_resolves():
    gateway = FakeGateway(
        ClassificationDecision(
            is_resolved=True,
            item_name="容器",
            category_code="プラ",
            confidence=0.98,
            evidence_indexes=(1,),
        )
    )
    service = WasteGuideService(gateway=gateway, item_search=EmptyItemSearch())

    result = service.query(
        query="汚れた容器",
        municipality_id="38201",
        district_id="38201-08",
    )

    assert result.status == "needs_clarification"
    assert result.follow_up_question == (
        "容器は、プラスチック製・ガラス製・金属製のどれですか？"
    )


def test_bottle_can_be_resolved_after_material_clarification():
    gateway = FakeGateway(
        ClassificationDecision(
            is_resolved=True,
            item_name="ボトル",
            category_code="プラ",
            disposal_instructions="汚れを取り除いて出してください。",
            confidence=0.98,
            evidence_indexes=(1,),
        )
    )
    service = WasteGuideService(
        gateway=gateway,
        item_search=EmptyItemSearch(),
        today_provider=lambda: date(2026, 8, 24),
    )

    result = service.query(
        query="使い終わったボトル",
        municipality_id="38201",
        district_id="38201-08",
        clarifications=[
            {
                "question": "ボトルは、ペットボトル・プラスチック製容器・ガラスびんのどれですか？",
                "answer": "プラスチック製容器です",
            }
        ],
    )

    assert result.status == "answered"


def test_clarification_is_passed_to_both_generation_steps():
    gateway = FakeGateway(
        ClassificationDecision(
            is_resolved=False,
            clarifying_question="汚れは落とせますか？",
        )
    )
    service = WasteGuideService(gateway=gateway, item_search=EmptyItemSearch())
    clarifications = [{"question": "素材は？", "answer": "プラスチック"}]

    service.query(
        query="この容器",
        municipality_id="38201",
        district_id="38201-08",
        clarifications=clarifications,
    )

    assert gateway.rewrite_calls[0][1] == clarifications
    assert gateway.classify_calls[0][1] == clarifications


def test_rejects_unsupported_region_before_calling_bedrock():
    gateway = FakeGateway(ClassificationDecision(is_resolved=False))
    service = WasteGuideService(gateway=gateway, item_search=EmptyItemSearch())

    with pytest.raises(UnsupportedRegionError):
        service.query(
            query="ペットボトル",
            municipality_id="38201",
            district_id="38201-10",
        )

    assert gateway.rewrite_calls == []


def test_duplicate_follow_up_is_stopped_after_user_answer():
    repeated_question = "容器はプラスチック製ですか？"
    gateway = FakeGateway(
        ClassificationDecision(
            is_resolved=False,
            confidence=0,
            clarifying_question=repeated_question,
        )
    )
    service = WasteGuideService(gateway=gateway, item_search=EmptyItemSearch())

    result = service.query(
        query="お弁当の透明なふた",
        municipality_id="38201",
        district_id="38201-08",
        clarifications=[
            {"question": repeated_question, "answer": "はい、プラスチック製です"}
        ],
    )

    assert result.status == "unable_to_determine"
    assert result.follow_up_question is None
    assert "いただいた情報は反映しました" in result.answer


def test_no_documents_never_calls_generation_or_claims_a_category():
    gateway = FakeGateway(
        ClassificationDecision(
            is_resolved=True,
            category_code="プラ",
            confidence=0.99,
        )
    )
    service = WasteGuideService(gateway=gateway, item_search=EmptyItemSearch())

    result = service.decide(
        query="未知の品物",
        rewritten_query="未知の品物",
        documents=[],
        municipality_id="38201",
        district_id="38201-08",
        clarifications=[{"question": "素材は？", "answer": "プラスチック"}],
    )

    assert result.status == "unable_to_determine"
    assert result.decision.is_resolved is False
    assert gateway.classify_calls == []


def test_person_query_is_rejected_without_asking_follow_up_questions():
    gateway = FakeGateway(ClassificationDecision(is_resolved=False))
    service = WasteGuideService(gateway=gateway, item_search=EmptyItemSearch())

    result = service.decide(
        query="汚れた人間",
        rewritten_query="汚れた人間",
        documents=[RetrievedDocument(text="無関係な検索結果")],
        municipality_id="38201",
        district_id="38201-08",
    )

    assert result.status == "unable_to_determine"
    assert result.follow_up_question is None
    assert result.answer == (
        "人間や人物はごみとして分類できません。"
        "ごみとして捨てたい品物の名前や用途を入力してください。"
    )
    assert gateway.classify_calls == []


def test_malformed_follow_up_question_is_replaced_with_readable_fallback():
    gateway = FakeGateway(
        ClassificationDecision(
            is_resolved=False,
            clarifying_question=(
                "浩れた人除は常できないのですか？"
                "何の話がしたいのですか？どういうものですか？"
            ),
        )
    )
    service = WasteGuideService(gateway=gateway, item_search=EmptyItemSearch())

    result = service.decide(
        query="よく分からないもの",
        rewritten_query="よく分からないもの",
        documents=[RetrievedDocument(text="候補")],
        municipality_id="38201",
        district_id="38201-08",
    )

    assert result.status == "needs_clarification"
    assert result.follow_up_question == (
        "品物の名前や用途、素材をもう少し具体的に教えてください。"
    )


def test_cited_evidence_is_shown_before_other_candidates():
    gateway = FakeGateway(
        ClassificationDecision(
            is_resolved=True,
            item_name="食品容器",
            category_code="プラ",
            confidence=0.95,
            evidence_indexes=(2,),
        )
    )
    service = WasteGuideService(
        gateway=gateway,
        item_search=EmptyItemSearch(),
        today_provider=lambda: date(2026, 8, 24),
    )
    documents = [
        RetrievedDocument(text="別候補", uri="local://items/other"),
        RetrievedDocument(text="採用根拠", uri="local://items/cited"),
    ]

    result = service.decide(
        query="食品容器",
        rewritten_query="食品容器",
        documents=documents,
        municipality_id="38201",
        district_id="38201-08",
    )

    assert result.sources[0].uri == "local://items/cited"
