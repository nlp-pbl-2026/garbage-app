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

    def converse(self, **kwargs):
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
        query="飲み終わったボトルは？",
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
