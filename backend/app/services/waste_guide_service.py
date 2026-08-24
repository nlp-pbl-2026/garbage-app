"""質問の言い換え、RAG検索、分類、次回収集日の決定を行う。"""

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from .. import config
from .calendar_service import CalendarService, CollectionDate
from .item_search_service import ItemSearchService

logger = logging.getLogger(__name__)

SUPPORTED_MUNICIPALITY_ID = "38201"
SUPPORTED_DISTRICT_ID = "38201-08"

CATEGORY_NAMES = {
    "可燃": "可燃ごみ",
    "埋立": "埋立ごみ",
    "金・ガ": "金物・ガラス類",
    "紙類": "紙類",
    "ペット": "ペットボトル",
    "プラ": "プラスチック製容器包装",
    "水銀": "水銀ごみ",
    "粗大": "粗大ごみ",
    "禁止": "市で収集しないもの",
}


class WasteGuideError(Exception):
    """ごみ検索サービスの外部連携または応答形式エラー。"""


class UnsupportedRegionError(ValueError):
    """現在未対応の地域が指定された。"""


@dataclass(frozen=True)
class RetrievedDocument:
    text: str
    score: float | None = None
    uri: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class ClassificationDecision:
    is_resolved: bool
    item_name: str = ""
    category_code: str = ""
    disposal_instructions: str = ""
    confidence: float = 0.0
    clarifying_question: str = ""
    evidence_indexes: tuple[int, ...] = ()


@dataclass(frozen=True)
class WasteGuideResult:
    status: str
    rewritten_query: str
    answer: str | None = None
    follow_up_question: str | None = None
    decision: ClassificationDecision | None = None
    next_collection: CollectionDate | None = None
    sources: list[RetrievedDocument] = field(default_factory=list)


class BedrockGateway:
    """Bedrock RuntimeとKnowledge Base Runtimeへの薄いアダプター。"""

    def __init__(self, runtime_client=None, agent_runtime_client=None):
        self._runtime = runtime_client or boto3.client(
            "bedrock-runtime", region_name=config.AWS_REGION
        )
        self._agent_runtime = agent_runtime_client or boto3.client(
            "bedrock-agent-runtime", region_name=config.AWS_REGION
        )

    def rewrite_query(self, query: str, clarifications: list[dict]) -> str:
        clarification_text = "\n".join(
            f"追加質問: {item['question']}\n回答: {item['answer']}"
            for item in clarifications
        )
        prompt = f"""
松山市清水地区のごみ分別データを検索するため、利用者の表現を短い検索文に言い換えてください。
品目、素材、大きさ、用途、汚れの状態など、分類に必要な語を残してください。
利用者の表現から社会通念上ほぼ一意に判断できる特徴は、検索に必要な範囲で補って構いません。
例えば「お弁当の透明なフタ」は、繰り返し使う弁当箱ではなく、一般的な使い捨ての
「弁当・惣菜の透明なプラスチック製容器のふた」として検索してください。
複数の解釈が現実的に残る場合は、推測で情報を追加しないでください。
「松山市」「清水地区」「ごみ分別」のような検索対象側で既知の語は追加しないでください。

利用者の質問:
{query}

補足:
{clarification_text or 'なし'}

次のJSONだけを返してください。
{{"search_query":"検索文"}}
""".strip()
        payload = self._converse_json(prompt, max_tokens=200)
        rewritten = str(payload.get("search_query", "")).strip()
        cleaned = self._clean_rewritten_query(rewritten)
        cleaned = self._remove_unsupported_materials(
            cleaned,
            query=query,
            clarifications=clarifications,
        )
        return self._normalize_search_spelling(cleaned) or query.strip()

    @staticmethod
    def _clean_rewritten_query(value: str) -> str:
        cleaned = value
        for phrase in (
            "松山市清水地区",
            "松山市",
            "清水地区",
            "ごみ分別データ",
            "ゴミ分別データ",
            "ごみ分別",
            "ゴミ分別",
        ):
            cleaned = cleaned.replace(phrase, " ")
        return " ".join(cleaned.split())

    @staticmethod
    def _remove_unsupported_materials(
        value: str, *, query: str, clarifications: list[dict]
    ) -> str:
        """入力にない素材を言い換えが勝手に補った場合に除去する。"""

        source = unicodedata.normalize(
            "NFKC",
            " ".join(
                [query]
                + [
                    str(item.get("answer", ""))
                    for item in clarifications
                ]
            ),
        ).lower()
        allow_transparent_bento_lid = all(
            marker in source for marker in ("弁当", "透明")
        ) and any(marker in source for marker in ("ふた", "フタ", "蓋"))
        material_groups = (
            (
                ("プラスチック製の", "プラスチック製", "プラスチック", "樹脂製の", "樹脂製", "樹脂"),
                ("プラスチック", "樹脂"),
                allow_transparent_bento_lid,
            ),
            (("ガラス製の", "ガラス製", "ガラス"), ("ガラス",), False),
            (
                ("金属製の", "金属製", "金属", "アルミ製の", "アルミ製", "アルミ", "スチール製", "スチール"),
                ("金属", "アルミ", "スチール"),
                False,
            ),
            (("紙製の", "紙製"), ("紙製", "紙の"), False),
        )
        cleaned = value
        for output_terms, source_terms, context_allows in material_groups:
            if context_allows or any(term in source for term in source_terms):
                continue
            for term in output_terms:
                cleaned = cleaned.replace(term, "")
        return " ".join(cleaned.split())

    @staticmethod
    def _normalize_search_spelling(value: str) -> str:
        return value.replace("ビン", "びん").replace("瓶", "びん")

    def retrieve(self, query: str) -> list[RetrievedDocument]:
        if not config.BEDROCK_KNOWLEDGE_BASE_ID:
            raise WasteGuideError("BEDROCK_KNOWLEDGE_BASE_ID is not configured")
        try:
            response = self._agent_runtime.retrieve(
                knowledgeBaseId=config.BEDROCK_KNOWLEDGE_BASE_ID,
                retrievalQuery={"text": query},
                retrievalConfiguration={
                    "managedSearchConfiguration": {
                        "numberOfResults": config.RAG_TOP_K,
                    }
                },
            )
        except (BotoCoreError, ClientError, NoCredentialsError) as error:
            raise WasteGuideError("Knowledge Base retrieval failed") from error

        documents: list[RetrievedDocument] = []
        for result in response.get("retrievalResults", []):
            content = result.get("content", {})
            location = result.get("location", {})
            metadata = result.get("metadata", {})
            uri = location.get("s3Location", {}).get("uri") or metadata.get(
                "x-amz-bedrock-kb-source-uri"
            )
            title = metadata.get("source_title") or metadata.get("_document_title")
            documents.append(
                RetrievedDocument(
                    text=content.get("text", ""),
                    score=result.get("score"),
                    uri=uri,
                    title=title,
                )
            )
        return documents

    def classify(
        self, query: str, clarifications: list[dict], documents: list[RetrievedDocument]
    ) -> ClassificationDecision:
        evidence = "\n\n".join(
            f"根拠{i + 1}: {document.text}" for i, document in enumerate(documents)
        )
        clarification_text = "\n".join(
            f"追加質問: {item['question']}\n回答: {item['answer']}"
            for item in clarifications
        )
        prompt = f"""
あなたは松山市のごみ分別判定器です。検索根拠だけを使い、品目の分類を判定してください。
人間や人物など、ごみとして扱えない対象について分別の追加質問を生成してはいけません。
分類コードは 可燃, 埋立, 金・ガ, 紙類, ペット, プラ, 水銀, 粗大, 禁止 のいずれかです。

次の判定手順を順番に実行してください。
1. 利用者の質問と補足だけから、実物について判明している情報を整理する。
2. 検索根拠ごとに、該当する条件と分類コードを比較する。上位候補が多いだけで多数決しない。
3. 次の観点のうち、回答によって分類コードまたは市の収集可否が変わる不足情報があるか確認する。
   - 品物の特定: 一般名詞だけで、具体的な品目・用途・使用場面が複数残っていないか。
   - 素材・構成: プラスチック、紙、木、布、金属、ガラス、陶器などで分類が分かれないか。
   - 製品か容器包装か: 同じプラスチックでも、繰り返し使う製品と商品を包んだ容器包装を区別できるか。
   - 大きさ: 指定袋に入るかどうかで、通常ごみと粗大ごみに分かれないか。
   - 状態: 汚れを取り除けるか、割れているかなどで、分類や受入可否が変わらないか。
   - 中身: 液体、油、薬品、ガス、燃料などが残っているかどうかで扱いが変わらないか。
   - 識別表示: PET表示、プラマーク、材質表示などを確認しないと候補を区別できないか。
   - 電気的要素: 電池・充電池・バッテリー・電源を使うかどうかで分類が変わらないか。
   - 排出元: 家庭用か事業用かで、市の収集可否が変わらないか。
   - 部品: 本体・ふた・キャップ・取り外せる金具など、どの部分を捨てるのか不明でないか。
4. 不足情報がなく、根拠から分類を一意に決められる場合だけ is_resolved=true にする。
5. 不足情報がある場合は is_resolved=false にし、分類候補を最も大きく絞れる確認を一つだけ
   clarifying_question に入れる。質問は利用者が見て答えられる具体的な日本語にする。

条件付き根拠の扱い:
- 根拠の「金属製のものは『金・ガ』」「袋に入らないものは『粗大』」
  「プラマークがあれば『プラ』」「事業用は排出禁止」等は、注意書きではなく分類の分岐条件である。
- 分岐条件に必要な情報が質問・補足にない場合、行に記載された既定の分類コードだけを採用してはいけない。
- 例えば「おぼん」は、素材で可燃と金・ガに分かれるため、まず
  「おぼんは何製ですか？（木・プラスチック・金属など）」と質問する。
- 素材が木またはプラスチックと分かった後も、袋に入るかで可燃と粗大に分かれるなら、次に
  「松山市の指定ごみ袋に入る大きさですか？」と質問する。
- 一方、「すすいで出す」「電池は外す」「危なくないように包む」のように分類コードが変わらない記述は、
  追加質問の理由にせず disposal_instructions で案内する。

追加質問の規則:
- 一度に質問する論点は一つだけにし、可能なら根拠に存在する選択肢を短く示す。
- 素材によって分類が変わるなら素材を聞く。大きさによって変わるなら指定袋に入るかを聞く。
- 既に質問または補足で回答された情報を再質問しない。同じ意味の質問を言い換えて繰り返さない。
- 回答によって分類が変わらず、「すすぐ」「使い切る」「電池を外す」等の出し方だけが変わる場合は、
  その確認を質問せず、分類確定後の disposal_instructions で案内する。
- 検索根拠にない選択肢、条件、出し方を作らない。

検索根拠にプラスチック製の候補が多くても、利用者の質問に素材が書かれていなければ、
プラスチック製だと推測して確定してはいけません。検索候補は可能性の一覧であり、利用者の品物そのものの証明ではありません。
ただし、品目・用途・外見の組み合わせから通常の意味が十分に一意な場合は、不要な確認をしてはいけません。
「お弁当の透明なフタ」は一般的な使い捨て弁当・惣菜容器のふたを指すため、
「弁当・惣菜の容器（プラスチック製）」の根拠を使って確定し、素材を質問しないでください。
「弁当箱（プラスチック製）」は繰り返し使う製品なので、この入力の根拠として優先してはいけません。
「びん」「ビン」「瓶」は通常のガラスびんとして扱ってください。入力が「汚れたびん」の場合は、
素材を質問せず「びん」の根拠で金物・ガラス類に確定し、すすぐ等の資料上の出し方を案内してください。
例えば「汚れた容器」には「容器は、プラスチック製・ガラス製・金属製のどれですか？」と質問し、
「使い終わったボトル」には「ボトルは、ペットボトル・プラスチック製容器・ガラスびんのどれですか？」と質問してください。
「保冷剤」「ペットボトル」のように、松山市資料上で品目が一意に特定できる場合は、素材を追加で聞かずに確定して構いません。
根拠にない分類や出し方を作らないでください。
確定する場合は、使用した根拠番号を evidence_indexes に必ず1件以上入れてください。

利用者の質問:
{query}

補足:
{clarification_text or 'なし'}

検索根拠:
{evidence or '該当なし'}

次のJSONだけを返してください。
{{
  "is_resolved": true,
  "item_name": "判定対象の品目名",
  "category_code": "分類コード",
  "disposal_instructions": "根拠に基づく出し方と注意点",
  "confidence": 0.0,
  "clarifying_question": "",
  "evidence_indexes": [1]
}}
""".strip()
        payload = self._converse_json(prompt, max_tokens=600)
        category_code = str(payload.get("category_code", "")).strip()
        confidence = float(payload.get("confidence", 0.0) or 0.0)
        is_resolved = bool(payload.get("is_resolved", False))
        evidence_indexes = tuple(
            index
            for index in payload.get("evidence_indexes", [])
            if isinstance(index, int) and 1 <= index <= len(documents)
        )
        if category_code not in CATEGORY_NAMES:
            is_resolved = False
            category_code = ""
        if confidence < config.CLASSIFICATION_CONFIDENCE_THRESHOLD:
            is_resolved = False
        if is_resolved and not any(
            self._document_supports_category(documents[index - 1], category_code)
            for index in evidence_indexes
        ):
            logger.warning(
                "Rejected ungrounded classification: category=%s evidence=%s",
                category_code,
                evidence_indexes,
            )
            is_resolved = False
        return ClassificationDecision(
            is_resolved=is_resolved,
            item_name=str(payload.get("item_name", "")).strip(),
            category_code=category_code,
            disposal_instructions=str(
                payload.get("disposal_instructions", "")
            ).strip(),
            confidence=max(0.0, min(confidence, 1.0)),
            clarifying_question=str(
                payload.get("clarifying_question", "")
            ).strip(),
            evidence_indexes=evidence_indexes,
        )

    @staticmethod
    def _document_supports_category(
        document: RetrievedDocument, category_code: str
    ) -> bool:
        text = unicodedata.normalize("NFKC", document.text)
        category_name = CATEGORY_NAMES.get(category_code, "")
        return category_code in text or (category_name and category_name in text)

    def _converse_json(self, prompt: str, *, max_tokens: int) -> dict:
        try:
            response = self._runtime.converse(
                modelId=config.BEDROCK_MODEL_ID,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={
                    "maxTokens": max_tokens,
                    "temperature": 0,
                    "topP": 0.9,
                },
            )
        except (BotoCoreError, ClientError, NoCredentialsError) as error:
            raise WasteGuideError("Bedrock generation failed") from error

        content = response.get("output", {}).get("message", {}).get("content", [])
        text = "".join(part.get("text", "") for part in content).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            raise WasteGuideError("Bedrock returned invalid JSON")
        try:
            return json.loads(text[start : end + 1])
        except (json.JSONDecodeError, TypeError) as error:
            raise WasteGuideError("Bedrock returned invalid JSON") from error


class WasteGuideService:
    """利用者の質問を、回答または単一の追加質問へ変換する。"""

    def __init__(
        self,
        gateway: BedrockGateway | None = None,
        calendar: CalendarService | None = None,
        item_search: ItemSearchService | None = None,
        now_provider=None,
        today_provider=None,
    ):
        self._gateway = gateway or BedrockGateway()
        self._calendar = calendar or CalendarService()
        self._item_search = item_search or ItemSearchService()
        # today_providerは既存呼び出しとの互換用。新規コードは時刻を含むnow_providerを使う。
        self._now_provider = now_provider
        self._today_provider = today_provider

    def query(
        self,
        *,
        query: str,
        municipality_id: str,
        district_id: str,
        clarifications: list[dict] | None = None,
    ) -> WasteGuideResult:
        clarification_items = clarifications or []
        rewritten_query = self.rewrite(
            query=query,
            municipality_id=municipality_id,
            district_id=district_id,
            clarifications=clarification_items,
        )
        documents = self.retrieve(
            rewritten_query=rewritten_query,
            municipality_id=municipality_id,
            district_id=district_id,
        )
        return self.decide(
            query=query,
            rewritten_query=rewritten_query,
            documents=documents,
            municipality_id=municipality_id,
            district_id=district_id,
            clarifications=clarification_items,
        )

    def rewrite(
        self,
        *,
        query: str,
        municipality_id: str,
        district_id: str,
        clarifications: list[dict] | None = None,
    ) -> str:
        """利用者の表現を、地域資料を探すための検索文へ言い換える。"""

        self._validate_region(municipality_id, district_id)
        return self._gateway.rewrite_query(query, clarifications or [])

    def retrieve(
        self,
        *,
        rewritten_query: str,
        municipality_id: str,
        district_id: str,
    ) -> list[RetrievedDocument]:
        """言い換え済み検索文で地域別Knowledge Baseを検索する。"""

        self._validate_region(municipality_id, district_id)
        lexical_documents = [
            RetrievedDocument(
                text=match.evidence_text,
                score=match.score,
                uri=f"local://items/{match.item_id}",
                title="松山市ごみ分別辞典（品目検索）",
            )
            for match in self._item_search.search(
                rewritten_query, limit=config.LEXICAL_SEARCH_TOP_K
            )
        ]
        vector_documents = self._gateway.retrieve(rewritten_query)
        return lexical_documents + vector_documents

    def decide(
        self,
        *,
        query: str,
        rewritten_query: str,
        documents: list[RetrievedDocument],
        municipality_id: str,
        district_id: str,
        clarifications: list[dict] | None = None,
    ) -> WasteGuideResult:
        """検索根拠から分類を決め、回答または追加質問を組み立てる。"""

        self._validate_region(municipality_id, district_id)
        clarification_items = clarifications or []
        if self._is_out_of_scope(query):
            return WasteGuideResult(
                status="unable_to_determine",
                rewritten_query=rewritten_query,
                answer=(
                    "人間や人物はごみとして分類できません。"
                    "ごみとして捨てたい品物の名前や用途を入力してください。"
                ),
                decision=ClassificationDecision(is_resolved=False),
            )
        if not documents:
            if clarification_items:
                return WasteGuideResult(
                    status="unable_to_determine",
                    rewritten_query=rewritten_query,
                    answer=(
                        "いただいた情報は反映しましたが、松山市の公開資料から分類を"
                        "確認できませんでした。品目名や用途を変えて、もう一度検索してください。"
                    ),
                    decision=ClassificationDecision(is_resolved=False),
                )
            return WasteGuideResult(
                status="needs_clarification",
                rewritten_query=rewritten_query,
                follow_up_question=(
                    "地域資料で候補を見つけられませんでした。品物の用途や素材を教えてください。"
                ),
                decision=ClassificationDecision(is_resolved=False),
            )
        decision = self._gateway.classify(query, clarification_items, documents)
        ambiguity_question = self._missing_detail_question(
            query=query,
            clarifications=clarification_items,
            documents=documents,
        )
        conditional_question = self._conditional_evidence_question(
            query=query,
            clarifications=clarification_items,
            documents=documents,
        )
        required_question = conditional_question
        if required_question is None and ambiguity_question and (
            decision.is_resolved or not decision.clarifying_question
        ):
            required_question = ambiguity_question
        if required_question:
            logger.info(
                "Applying required clarification because the query lacks a detail: %s",
                query,
            )
            decision = replace(
                decision,
                is_resolved=False,
                clarifying_question=required_question,
            )
        cited_indexes = [index - 1 for index in decision.evidence_indexes]
        source_indexes = cited_indexes + [
            index for index in range(len(documents)) if index not in cited_indexes
        ]
        sources = [documents[index] for index in source_indexes[:3]]

        if not decision.is_resolved:
            question = decision.clarifying_question or (
                "素材、大きさ、汚れの有無など、品物の状態をもう少し教えてください。"
            )
            if not self._is_valid_follow_up_question(question):
                logger.warning("Rejected malformed follow-up question: %r", question)
                question = "品物の名前や用途、素材をもう少し具体的に教えてください。"
            previous_questions = [
                item.get("question", "") for item in (clarifications or [])
            ]
            is_duplicate = any(
                self._normalize_question(question)
                == self._normalize_question(previous_question)
                for previous_question in previous_questions
            )
            if is_duplicate or len(previous_questions) >= config.MAX_CLARIFICATION_TURNS:
                return WasteGuideResult(
                    status="unable_to_determine",
                    rewritten_query=rewritten_query,
                    answer=(
                        "いただいた情報は反映しましたが、松山市の公開資料から分類を"
                        "確定できませんでした。品目名や用途、汚れの状態を含めて、"
                        "別の言い方でもう一度検索してください。"
                    ),
                    decision=decision,
                    sources=sources,
                )
            return WasteGuideResult(
                status="needs_clarification",
                rewritten_query=rewritten_query,
                follow_up_question=question,
                decision=decision,
                sources=sources,
            )

        if self._now_provider is not None:
            next_collection = self._calendar.next_collection(
                decision.category_code, at=self._now_provider()
            )
        elif self._today_provider is not None:
            next_collection = self._calendar.next_collection(
                decision.category_code, from_date=self._today_provider()
            )
        else:
            next_collection = self._calendar.next_collection(
                decision.category_code,
                at=datetime.now(ZoneInfo(config.TIMEZONE)),
            )
        answer = self._build_answer(decision, next_collection)
        return WasteGuideResult(
            status="answered",
            rewritten_query=rewritten_query,
            answer=answer,
            decision=decision,
            next_collection=next_collection,
            sources=sources,
        )

    @staticmethod
    def _normalize_question(question: str) -> str:
        value = unicodedata.normalize("NFKC", question).lower()
        return re.sub(r"[\s\W_]+", "", value)

    @staticmethod
    def _is_out_of_scope(query: str) -> bool:
        normalized = unicodedata.normalize("NFKC", query)
        return any(
            phrase in normalized
            for phrase in ("人間", "人物", "人を捨て", "人の捨て方", "遺体", "死体")
        )

    @staticmethod
    def _is_valid_follow_up_question(question: str) -> bool:
        normalized = unicodedata.normalize("NFKC", question).strip()
        if not 5 <= len(normalized) <= 120:
            return False
        if any(
            unicodedata.category(character).startswith("C")
            for character in normalized
        ):
            return False
        question_marks = normalized.count("?") + normalized.count("？")
        if question_marks > 1:
            return False
        return "�" not in normalized

    @classmethod
    def _missing_detail_question(
        cls,
        *,
        query: str,
        clarifications: list[dict],
        documents: list[RetrievedDocument],
    ) -> str | None:
        """一般名詞だけの入力を、検索候補だけで確定しないための最終ガード。"""

        text = unicodedata.normalize(
            "NFKC",
            " ".join(
                [query]
                + [
                    str(item.get("answer", ""))
                    for item in clarifications
                ]
            ),
        ).lower()
        material_markers = (
            "プラスチック",
            "樹脂",
            "ガラス",
            "金属",
            "アルミ",
            "スチール",
            "紙製",
            "紙の",
            "ペットボトル",
            "pet",
        )
        if any(marker in text for marker in material_markers):
            return None

        normalized_query = cls._normalize_question(query)
        item_names = []
        for document in documents:
            first_line = document.text.splitlines()[0] if document.text else ""
            if first_line.startswith("品目:"):
                item_names.append(
                    cls._normalize_question(first_line.removeprefix("品目:"))
                )
        # Exact catalog entries (例: 保冷剤) are already sufficiently specific.
        if normalized_query and normalized_query in item_names:
            return None

        if "ボトル" in text:
            return "ボトルは、ペットボトル・プラスチック製容器・ガラスびんのどれですか？"
        if "容器" in text:
            return "容器は、プラスチック製・ガラス製・金属製のどれですか？"
        return None

    @classmethod
    def _conditional_evidence_question(
        cls,
        *,
        query: str,
        clarifications: list[dict],
        documents: list[RetrievedDocument],
    ) -> str | None:
        """地域資料の分類分岐条件が未回答なら、確定前に一つ確認する。"""

        context = unicodedata.normalize(
            "NFKC",
            " ".join(
                [query]
                + [str(item.get("answer", "")) for item in clarifications]
            ),
        ).lower()
        structured = next(
            (
                document
                for document in documents
                if document.text.startswith("品目:")
            ),
            None,
        )
        if structured is None:
            return None

        lines = structured.text.splitlines()
        item_name = lines[0].removeprefix("品目:").strip()
        display_item = re.sub(r"[（(].*$", "", item_name).strip() or "品物"
        evidence = unicodedata.normalize("NFKC", structured.text)

        material_branches = (
            "金属製のものは",
            "金属・ガラス製のものは",
            "プラスチック製のものは",
            "木・プラスチック製",
            "紙製は",
            "紙製のものは",
            "ガラス製のものは",
            "陶器製のものは",
        )
        material_answers = (
            "プラスチック",
            "樹脂",
            "金属",
            "アルミ",
            "スチール",
            "ガラス",
            "陶器",
            "セラミック",
            "紙製",
            "紙の",
            "木製",
            "木の",
            "布製",
            "革製",
            "ゴム製",
        )
        if any(branch in evidence for branch in material_branches) and not any(
            material in context for material in material_answers
        ):
            return (
                f"{display_item}は何製ですか？"
                "（木・プラスチック・金属など）"
            )

        size_branch = "袋に入らない" in evidence or "袋に入らない場合" in evidence
        size_answers = (
            "袋に入る",
            "袋に入ります",
            "袋に入らない",
            "袋に入りません",
            "指定袋",
            "粗大",
            "cm",
            "センチ",
        )
        if size_branch and not any(answer in context for answer in size_answers):
            return "松山市の指定ごみ袋に入る大きさですか？"

        if "プラマーク" in evidence and not any(
            marker in context for marker in ("プラマーク", "プラ表示", "マークあり", "マークなし")
        ):
            return "プラマークは付いていますか？"

        if "事業用" in evidence and not any(
            source in context for source in ("家庭用", "家庭で", "事業用", "仕事で", "店舗で")
        ):
            return "家庭で使用したものですか、それとも事業用ですか？"

        if "電気・電池を使用するものは" in evidence and not any(
            power in context for power in ("電動", "電池", "充電", "電気を使", "電気式", "手動")
        ):
            return "電池や電源を使うものですか？"

        return None

    @staticmethod
    def _validate_region(municipality_id: str, district_id: str) -> None:
        if (
            municipality_id != SUPPORTED_MUNICIPALITY_ID
            or district_id != SUPPORTED_DISTRICT_ID
        ):
            raise UnsupportedRegionError("現在は松山市・清水地区のみ対応しています。")

    @staticmethod
    def _build_answer(
        decision: ClassificationDecision, next_collection: CollectionDate | None
    ) -> str:
        category_name = CATEGORY_NAMES[decision.category_code]
        lines = [f"{decision.item_name}は「{category_name}」です。"]
        if decision.disposal_instructions:
            lines.append(decision.disposal_instructions)
        if next_collection:
            lines.append(
                f"清水地区の次回収集日は{next_collection.display_date}です。"
            )
        elif decision.category_code == "粗大":
            lines.append("粗大ごみは戸別収集の申し込みが必要です。")
        elif decision.category_code == "禁止":
            lines.append("松山市のごみ集積場所には出せません。")
        else:
            lines.append("公開済みカレンダーの範囲では次回収集日を確認できません。")
        return "\n".join(lines)
