"""質問の言い換え、RAG検索、分類、次回収集日の決定を行う。"""

import json
import logging
from dataclasses import dataclass, field
from datetime import date

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from .. import config
from .calendar_service import CalendarService, CollectionDate

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
推測で情報を追加しないでください。

利用者の質問:
{query}

補足:
{clarification_text or 'なし'}

次のJSONだけを返してください。
{{"search_query":"検索文"}}
""".strip()
        payload = self._converse_json(prompt, max_tokens=200)
        rewritten = str(payload.get("search_query", "")).strip()
        return rewritten or query.strip()

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
分類コードは 可燃, 埋立, 金・ガ, 紙類, ペット, プラ, 水銀, 粗大, 禁止 のいずれかです。
複数候補が残る、素材・大きさ・汚れ等が不足する、または根拠が弱い場合は is_resolved=false にし、
分類を確定するための質問を一つだけ clarifying_question に入れてください。
根拠にない分類や出し方を作らないでください。

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
  "clarifying_question": ""
}}
""".strip()
        payload = self._converse_json(prompt, max_tokens=600)
        category_code = str(payload.get("category_code", "")).strip()
        confidence = float(payload.get("confidence", 0.0) or 0.0)
        is_resolved = bool(payload.get("is_resolved", False))
        if category_code not in CATEGORY_NAMES:
            is_resolved = False
            category_code = ""
        if confidence < config.CLASSIFICATION_CONFIDENCE_THRESHOLD:
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
        )

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
        today_provider=None,
    ):
        self._gateway = gateway or BedrockGateway()
        self._calendar = calendar or CalendarService()
        self._today_provider = today_provider or date.today

    def query(
        self,
        *,
        query: str,
        municipality_id: str,
        district_id: str,
        clarifications: list[dict] | None = None,
    ) -> WasteGuideResult:
        if (
            municipality_id != SUPPORTED_MUNICIPALITY_ID
            or district_id != SUPPORTED_DISTRICT_ID
        ):
            raise UnsupportedRegionError("現在は松山市・清水地区のみ対応しています。")

        clarification_items = clarifications or []
        rewritten_query = self._gateway.rewrite_query(query, clarification_items)
        documents = self._gateway.retrieve(rewritten_query)
        decision = self._gateway.classify(query, clarification_items, documents)
        sources = documents[:3]

        if not decision.is_resolved:
            question = decision.clarifying_question or (
                "素材、大きさ、汚れの有無など、品物の状態をもう少し教えてください。"
            )
            return WasteGuideResult(
                status="needs_clarification",
                rewritten_query=rewritten_query,
                follow_up_question=question,
                sources=sources,
            )

        next_collection = self._calendar.next_collection(
            decision.category_code, from_date=self._today_provider()
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
