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


class FakeEmbeddingSearch:
    def __init__(self, matches=None):
        self.matches = matches or []
        self.queries = []

    def search(self, query, *, limit=None):
        self.queries.append(query)
        return self.matches


def test_managed_knowledge_base_uses_managed_search_configuration(monkeypatch):
    agent_runtime = FakeAgentRuntime()
    monkeypatch.setattr(
        "app.services.waste_guide_service.config.BEDROCK_KNOWLEDGE_BASE_ID",
        "FMPYJSHELD",
    )
    monkeypatch.setattr(
        "app.services.waste_guide_service.config.USE_BEDROCK_KNOWLEDGE_BASE",
        True,
    )
    gateway = BedrockGateway(
        runtime_client=object(),
        agent_runtime_client=agent_runtime,
        embedding_search=FakeEmbeddingSearch(),
    )

    assert gateway.retrieve("スプレー缶") == []
    assert agent_runtime.request["retrievalConfiguration"] == {
        "managedSearchConfiguration": {"numberOfResults": 8}
    }


def test_default_retrieve_uses_self_managed_embedding_search():
    from app.services.item_search_service import ItemMatch

    match = ItemMatch(
        item_id="item_0107",
        item="エアキャップ（ぷちぷち）",
        category="プラ",
        category_display="プラスチック製容器包装",
        note="",
        score=0.82,
    )
    embedding = FakeEmbeddingSearch([match])
    gateway = BedrockGateway(
        runtime_client=object(),
        agent_runtime_client=object(),
        embedding_search=embedding,
    )

    documents = gateway.retrieve("梱包のプチプチみたいなの")

    assert embedding.queries == ["梱包のプチプチみたいなの"]
    assert len(documents) == 1
    assert documents[0].uri == "local://items/item_0107"
    assert documents[0].text.startswith("品目: エアキャップ")
    assert documents[0].score == pytest.approx(0.82)


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


def test_classification_prompt_contains_missing_information_checklist():
    runtime = FakeRuntime(
        {
            "is_resolved": False,
            "confidence": 0,
            "clarifying_question": "素材は何ですか？",
            "evidence_indexes": [],
        }
    )
    gateway = BedrockGateway(runtime_client=runtime, agent_runtime_client=object())

    gateway.classify(
        "よく分からない容器",
        [],
        [RetrievedDocument(text="品目: 容器\n分類コード: プラ")],
    )

    prompt = runtime.request["messages"][0]["content"][0]["text"]
    for required_rule in (
        "素材・構成",
        "製品か容器包装か",
        "指定袋に入るか",
        "識別表示",
        "電池・充電池・バッテリー",
        "家庭用か事業用か",
        "分類候補を最も大きく絞れる確認を一つだけ",
        "出し方だけが変わる場合",
    ):
        assert required_rule in prompt


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


def test_rewrite_preserves_explicit_paper_and_box_features():
    gateway = BedrockGateway(
        runtime_client=FakeRuntime(
            {"search_query": "古いカメラのフィルムが入っていた容器"}
        ),
        agent_runtime_client=object(),
    )

    rewritten = gateway.rewrite_query(
        "古いカメラのフィルムが入っていた紙箱", []
    )

    assert "紙製" in rewritten
    assert "箱" in rewritten


def test_rewrite_does_not_replace_explicit_paper_with_plastic():
    gateway = BedrockGateway(
        runtime_client=FakeRuntime(
            {"search_query": "使い捨てのプラスチック製容器のふた"}
        ),
        agent_runtime_client=object(),
    )

    rewritten = gateway.rewrite_query("使い捨ての紙の容器", [])

    assert "プラスチック" not in rewritten
    assert "紙製" in rewritten
    assert "容器" in rewritten


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


def test_beverage_container_question_distinguishes_pet_and_plastic_packaging():
    gateway = FakeGateway(
        ClassificationDecision(
            is_resolved=True,
            item_name="ジュースの容器",
            category_code="プラ",
            confidence=0.98,
            evidence_indexes=(1,),
        )
    )
    service = WasteGuideService(gateway=gateway, item_search=EmptyItemSearch())

    result = service.decide(
        query="ジュースの空き容器",
        rewritten_query="ジュースの空き容器",
        documents=[RetrievedDocument(text="品目: 飲料容器\n分類コード: プラ")],
        municipality_id="38201",
        district_id="38201-08",
    )

    assert result.status == "needs_clarification"
    assert "PETマーク" in result.follow_up_question
    assert "プラマーク" in result.follow_up_question
    assert "紙パック" in result.follow_up_question


def test_explicit_paper_does_not_trigger_plastic_mark_question():
    question = WasteGuideService._conditional_evidence_question(
        query="使い捨ての紙の容器",
        clarifications=[],
        documents=[
            RetrievedDocument(
                text=(
                    "品目: 容器（プラスチック製）\n分類コード: プラ\n"
                    "出し方・注意: プラマークを確認"
                )
            )
        ],
    )

    assert question is None


def test_conditional_evidence_requires_material_before_resolving():
    gateway = FakeGateway(
        ClassificationDecision(
            is_resolved=True,
            item_name="おぼん",
            category_code="可燃",
            confidence=0.95,
            evidence_indexes=(1,),
        )
    )
    service = WasteGuideService(gateway=gateway, item_search=EmptyItemSearch())

    result = service.decide(
        query="おぼん",
        rewritten_query="おぼん",
        documents=[
            RetrievedDocument(
                text=(
                    "品目: おぼん\n分類コード: 可燃\n分類: 可燃ごみ\n"
                    "出し方・注意: 金属製のものは『金・ガ』 "
                    "袋に入らないものは『粗大』"
                )
            )
        ],
        municipality_id="38201",
        district_id="38201-08",
    )

    assert result.status == "needs_clarification"
    assert result.follow_up_question == (
        "おぼんは何製ですか？（木・プラスチック・金属など）"
    )


def test_conditional_evidence_asks_size_after_material_is_answered():
    gateway = FakeGateway(
        ClassificationDecision(
            is_resolved=True,
            item_name="おぼん",
            category_code="可燃",
            confidence=0.95,
            evidence_indexes=(1,),
        )
    )
    service = WasteGuideService(gateway=gateway, item_search=EmptyItemSearch())

    result = service.decide(
        query="おぼん",
        rewritten_query="木製のおぼん",
        documents=[
            RetrievedDocument(
                text=(
                    "品目: おぼん\n分類コード: 可燃\n分類: 可燃ごみ\n"
                    "出し方・注意: 金属製のものは『金・ガ』 "
                    "袋に入らないものは『粗大』"
                )
            )
        ],
        municipality_id="38201",
        district_id="38201-08",
        clarifications=[{"question": "何製ですか？", "answer": "木製です"}],
    )

    assert result.status == "needs_clarification"
    assert result.follow_up_question == "松山市の指定ごみ袋に入る大きさですか？"


def test_fully_answered_structured_conditions_resolve_without_third_question():
    gateway = FakeGateway(
        ClassificationDecision(
            is_resolved=False,
            confidence=0,
            clarifying_question="おぼんについてもう少し教えてください。",
        )
    )
    service = WasteGuideService(
        gateway=gateway,
        item_search=EmptyItemSearch(),
        today_provider=lambda: date(2026, 8, 24),
    )

    result = service.decide(
        query="おぼん",
        rewritten_query="木製のおぼん",
        documents=[
            RetrievedDocument(
                text=(
                    "品目: おぼん\n分類コード: 可燃\n分類: 可燃ごみ\n"
                    "出し方・注意: 金属製のものは「金・ガ」 "
                    "袋に入らないものは「粗大」"
                ),
                score=0.75,
                uri="local://items/item_0158",
            )
        ],
        municipality_id="38201",
        district_id="38201-08",
        clarifications=[
            {"question": "何製ですか？", "answer": "木製です"},
            {
                "question": "指定ごみ袋に入る大きさですか？",
                "answer": "入ります",
            },
        ],
    )

    assert result.status == "answered"
    assert result.decision.category_code == "可燃"


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
