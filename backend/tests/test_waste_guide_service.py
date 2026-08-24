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
    service = WasteGuideService(gateway=gateway)

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
    service = WasteGuideService(gateway=gateway)
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
    service = WasteGuideService(gateway=gateway)

    with pytest.raises(UnsupportedRegionError):
        service.query(
            query="ペットボトル",
            municipality_id="38201",
            district_id="38201-10",
        )

    assert gateway.rewrite_calls == []
