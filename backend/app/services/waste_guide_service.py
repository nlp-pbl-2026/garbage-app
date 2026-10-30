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
from .embedding_search_service import EmbeddingSearchService
from .item_search_service import ItemSearchService
from .nakajima_search_service import NakajimaSearchService
from .nakajima_rule_service import evidence_text as island_evidence_text, resolve_shared_item
from .region_registry_service import CATEGORY_DEFINITIONS, RegionContext, RegionResolutionError, get_registry

logger = logging.getLogger(__name__)

SUPPORTED_MUNICIPALITY_ID = "38201"
CATEGORY_NAMES = {code: label for code, (_, label) in CATEGORY_DEFINITIONS.items()}


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
class ImageInput:
    """Bedrock Converse APIへ渡す検証済み画像。"""

    format: str
    data: bytes


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

    def __init__(
        self,
        runtime_client=None,
        agent_runtime_client=None,
        embedding_search: EmbeddingSearchService | None = None,
    ):
        self._runtime = runtime_client or boto3.client(
            "bedrock-runtime", region_name=config.AWS_REGION
        )
        self._agent_runtime = agent_runtime_client or boto3.client(
            "bedrock-agent-runtime", region_name=config.AWS_REGION
        )
        # 自前Embedding検索はクエリのEmbeddingに同じRuntimeを使い回す。
        self._embedding_search = embedding_search

    def rewrite_query(
        self,
        query: str,
        clarifications: list[dict],
        image: ImageInput | None = None,
        region: RegionContext | None = None,
    ) -> str:
        clarification_text = "\n".join(
            f"追加質問: {item['question']}\n回答: {item['answer']}"
            for item in clarifications
        )
        prompt = f"""
松山市{region.area_name if region else '清水'}地区のごみ分別データを検索するため、利用者の表現を短い検索文に言い換えてください。
品目、素材、大きさ、用途、汚れの状態など、分類に必要な語を残してください。
利用者の表現から社会通念上ほぼ一意に判断できる特徴は、検索に必要な範囲で補って構いません。
例えば「お弁当の透明なフタ」は、繰り返し使う弁当箱ではなく、一般的な使い捨ての
「弁当・惣菜の透明なプラスチック製容器のふた」として検索してください。
複数の解釈が現実的に残る場合は、推測で情報を追加しないでください。
「松山市」「清水地区」「ごみ分別」のような検索対象側で既知の語は追加しないでください。
画像が添付されている場合は、写っている品物、用途、形状、表示、見た目から確認できる素材だけを
検索文へ含めてください。画像で確認できない素材や大きさを推測してはいけません。
利用者の文章は画像より優先し、文章に明記された品物・部位・素材・状態を落とさないでください。
画像が不鮮明な場合は特定の商品名を推測せず、見える形状や用途を一般的な語で表してください。
検索文は「一般的な品目名、品目辞典に載りそうな同義語、画像で確認できる特徴」の順にしてください。
たとえば、透明でねじ式キャップの飲料ボトルだと明確に確認できる場合は、単なる
「プラスチックボトル」ではなく「ペットボトル 飲料用透明ボトル」としてください。
飲料用か確認できない洗剤・化粧品などのボトルを、ペットボトルと推測してはいけません。

利用者の質問:
{query or '（画像のみ）'}

補足:
{clarification_text or 'なし'}

次のJSONだけを返してください。
{{"search_query":"検索文"}}
""".strip()
        payload = self._converse_json(prompt, max_tokens=200, image=image)
        rewritten = str(payload.get("search_query", "")).strip()
        cleaned = self._clean_rewritten_query(rewritten)
        if image is None:
            cleaned = self._remove_unsupported_materials(
                cleaned,
                query=query,
                clarifications=clarifications,
            )
        # 利用者が文章で明示した特徴は、画像の有無にかかわらず優先する。
        cleaned = self._preserve_explicit_features(
            cleaned,
            query=query,
            clarifications=clarifications,
        )
        result = self._normalize_search_spelling(cleaned) or query.strip()
        if not result:
            raise WasteGuideError("Bedrock could not identify the image")
        return result

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

    @staticmethod
    def _preserve_explicit_features(
        value: str, *, query: str, clarifications: list[dict]
    ) -> str:
        """利用者が明示した分類特徴を、LLMの言い換えで欠落させない。"""

        source = unicodedata.normalize(
            "NFKC",
            " ".join(
                [query]
                + [str(item.get("answer", "")) for item in clarifications]
            ),
        ).lower()
        source = BedrockGateway._normalize_search_spelling(source)
        cleaned = BedrockGateway._normalize_search_spelling(
            unicodedata.normalize("NFKC", value)
        )
        normalized_cleaned = cleaned.lower()
        feature_groups = (
            (("紙製", "紙の", "紙箱", "紙パック"), "紙製"),
            (("プラスチック", "樹脂"), "プラスチック製"),
            (("ガラス",), "ガラス製"),
            (("金属", "アルミ", "スチール"), "金属製"),
            (("陶器", "陶磁器", "セラミック"), "陶磁器製"),
            (("petマーク", "pet表示"), "PETマークあり"),
            (("プラマーク", "プラ表示"), "プラマークあり"),
        )
        additions: list[str] = []
        for markers, canonical in feature_groups:
            if any(marker in source for marker in markers) and not any(
                marker in normalized_cleaned for marker in markers
            ):
                additions.append(canonical)

        # 「Xが入っていた箱」のような入力では、X本体ではなく包装・部品が対象。
        # 対象部位を落とすと別品目へ寄るため、明示語を必ず検索文へ残す。
        part_markers = (
            "箱",
            "ふた",
            "蓋",
            "キャップ",
            "容器",
            "ボトル",
            "びん",
            "瓶",
            "缶",
            "袋",
            "芯",
            "電球",
            "ランプ",
            "電池",
            "バッテリー",
        )
        for marker in part_markers:
            if marker in source and marker not in normalized_cleaned:
                additions.append(marker)
        return " ".join([cleaned, *dict.fromkeys(additions)]).strip()

    def retrieve(self, query: str) -> list[RetrievedDocument]:
        """クエリの意味検索。既定は自前Embedding、任意でマネージドKBを併用。"""

        if not config.USE_BEDROCK_KNOWLEDGE_BASE:
            return self._retrieve_by_embedding(query)
        return self._retrieve_from_knowledge_base(query)

    def _retrieve_by_embedding(self, query: str) -> list[RetrievedDocument]:
        return [
            RetrievedDocument(
                text=match.evidence_text,
                score=match.score,
                uri=f"local://items/{match.item_id}",
                title="松山市ごみ分別辞典（意味検索）",
            )
            for match in self.search_item_candidates(query)
        ]

    def search_item_candidates(self, query: str, *, limit: int | None = None):
        """Return shared item identities; callers choose regional evidence."""
        try:
            if self._embedding_search is None:
                self._embedding_search = EmbeddingSearchService(runtime_client=self._runtime)
        except (OSError, ValueError, KeyError) as error:
            raise WasteGuideError("Verified Matsuyama item index is unavailable") from error
        if not getattr(self._embedding_search, "is_ready", True):
            raise WasteGuideError("Verified Matsuyama item index is unavailable")
        return self._embedding_search.search(query, limit=limit)

    def _retrieve_from_knowledge_base(self, query: str) -> list[RetrievedDocument]:
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
        self,
        query: str,
        clarifications: list[dict],
        documents: list[RetrievedDocument],
        image: ImageInput | None = None,
        region: RegionContext | None = None,
    ) -> ClassificationDecision:
        evidence = "\n\n".join(
            f"根拠{i + 1}: {document.text}" for i, document in enumerate(documents)
        )
        clarification_text = "\n".join(
            f"追加質問: {item['question']}\n回答: {item['answer']}"
            for item in clarifications
        )
        island = region is not None and region.is_nakajima
        category_list = ", ".join(region.category_codes if region else CATEGORY_NAMES)
        profile_note = ("中島地域の公式資料に基づく共通区分・例外ルールだけで判定してください。"
                        "共通索引の品目名は検索候補であり、松山・北条地域の分類や注意書きは適用しないでください。"
                        "中島では缶類とびん類を別に扱い、粗大ごみは地区別カレンダーの収集日に出します。"
                        if island else "松山・北条地域の公式資料に記載された根拠だけを使ってください。")
        mainland_examples = """品目種別ごとの分類原則:
- 木材と木製家具は別品目として扱い、家具の分類を木材の行から決めない。
- プラスチック製容器包装は商品を包んでいた容器・包装に限る。プラスチック製品は根拠を確認する。
- 乾電池・アルカリ電池は「埋立」、ボタン型電池は「水銀」、充電式・リチウムイオンは「禁止」。
- 土・砂・粘土・石・陶器などは「埋立」。公式資料の対象条件を必ず確認する。
- 市が収集しない品目は大型でも「粗大」にしない。"""
        island_examples = """中島地域の分類原則:
- 飲料缶・缶詰は「缶」、飲料・食料品用のびんは「びん」。用途が不明な容器は確認する。
- スプレー缶、一斗缶、金属製のびんのキャップなどは「金・ガ」。
- 粗大ごみは地区別カレンダーに収集日がある。松山・北条地域の戸別申込制を当てはめない。
- 共通索引の候補には、中島の公式計画で共通と確認できた区分だけを適用する。用途・材質・大きさ等の条件が足りない場合は確定しない。
- 中島の資料に区分や条件の根拠がない場合は分類を確定しない。"""
        size_example = ("中島地域では透明袋45L以下か、粗大ごみとして出す大きさかを公式根拠で確認する。"
                        if island else "袋に入らないものは該当根拠に従って粗大ごみとして扱う。")
        prompt = f"""
あなたは松山市のごみ分別判定器です。検索根拠だけを使い、品目の分類を判定してください。
人間や人物など、ごみとして扱えない対象について分別の追加質問を生成してはいけません。
分類コードは {category_list} のいずれかです。{profile_note}
添付画像がある場合、画像は利用者が捨てたい対象です。画像から直接確認できる品物、形状、表示、
汚れなどは判定に使えますが、画像で見えない素材、大きさ、中身を推測してはいけません。
分類コードと出し方は必ず検索根拠で裏付けてください。

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
- 素材や大きさで分類が分かれる場合だけ、利用者に確認する。{size_example}
- 一方、「すすいで出す」「電池は外す」「危なくないように包む」のように分類コードが変わらない記述は、
  追加質問の理由にせず disposal_instructions で案内する。

{island_examples if island else mainland_examples}

追加質問の規則:
- 一度に質問する論点は一つだけにし、可能なら根拠に存在する選択肢を短く示す。
- 素材によって分類が変わるなら素材を聞く。大きさによって変わるなら指定袋に入るかを聞く。
- 既に質問または補足で回答された情報を再質問しない。同じ意味の質問を言い換えて繰り返さない。
- 回答によって分類が変わらず、「すすぐ」「使い切る」「電池を外す」等の出し方だけが変わる場合は、
  その確認を質問せず、分類確定後の disposal_instructions で案内する。
- 検索根拠にない選択肢、条件、出し方を作らない。
- 「Xが入っていた箱」「Xの容器」「Xのふた」のような表現では、捨てる対象はX本体ではなく、
  明示された箱・容器・ふたである。本体の根拠を上位という理由だけで採用しない。
- 飲料の空き容器は、プラスチック製という回答だけではペットボトルとプラ容器を区別できない。
  PETマーク、プラマーク、紙パック、ガラスびん、金属缶のどれかを確認する。

検索根拠にプラスチック製の候補が多くても、利用者の質問に素材が書かれていなければ、
プラスチック製だと推測して確定してはいけません。検索候補は可能性の一覧であり、利用者の品物そのものの証明ではありません。
ただし、品目・用途・外見の組み合わせから通常の意味が十分に一意な場合は、不要な確認をしてはいけません。
「お弁当の透明なフタ」は一般的な使い捨て弁当・惣菜容器のふたを指しますが、
該当地域の根拠がない場合は確定しないでください。
「弁当箱（プラスチック製）」は繰り返し使う製品なので、この入力の根拠として優先してはいけません。
「びん」「ビン」「瓶」は通常のガラスびんとして扱ってください。分類は地域の根拠に従ってください。
例えば「汚れた容器」には「容器は、プラスチック製・ガラス製・金属製のどれですか？」と質問し、
「使い終わったボトル」には「ボトルは、ペットボトル・プラスチック製容器・ガラスびんのどれですか？」と質問してください。
「保冷剤」「ペットボトル」のように、該当地域の資料で品目が一意に特定できる場合だけ、素材を追加で聞かずに確定して構いません。
根拠にない分類や出し方を作らないでください。
確定する場合は、使用した根拠番号を evidence_indexes に必ず1件以上入れてください。

利用者の質問:
{query or '（画像のみ）'}

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
        payload = self._converse_json(prompt, max_tokens=600, image=image)
        category_code = str(payload.get("category_code", "")).strip()
        confidence = float(payload.get("confidence", 0.0) or 0.0)
        is_resolved = bool(payload.get("is_resolved", False))
        evidence_indexes = tuple(
            index
            for index in payload.get("evidence_indexes", [])
            if isinstance(index, int) and 1 <= index <= len(documents)
        )
        if category_code not in (region.category_codes if region else CATEGORY_NAMES):
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
        structured = re.search(r"^分類(?:コード)?:\s*([^\n]+)", text, re.MULTILINE)
        if structured:
            label = CATEGORY_NAMES.get(category_code, "")
            return structured.group(1).strip() in (category_code, label, f"{label} ({category_code})")
        category_name = CATEGORY_NAMES.get(category_code, "")
        return category_code in text or (category_name and category_name in text)

    def _converse_json(
        self,
        prompt: str,
        *,
        max_tokens: int,
        image: ImageInput | None = None,
    ) -> dict:
        content: list[dict] = []
        if image is not None:
            content.append(
                {
                    "image": {
                        "format": image.format,
                        "source": {"bytes": image.data},
                    }
                }
            )
        content.append({"text": prompt})
        try:
            response = self._runtime.converse(
                modelId=config.BEDROCK_MODEL_ID,
                messages=[{"role": "user", "content": content}],
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
        # 言い換え処理ではカレンダーも表層検索CSVも不要。ローカルでそれらの
        # Git管理外データが未配置でも、必要な段階までは初期化しない。
        self._calendar = calendar
        self._item_search = item_search
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
        image: ImageInput | None = None,
    ) -> WasteGuideResult:
        clarification_items = clarifications or []
        rewritten_query = self.rewrite(
            query=query,
            municipality_id=municipality_id,
            district_id=district_id,
            clarifications=clarification_items,
            image=image,
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
            image=image,
        )

    def rewrite(
        self,
        *,
        query: str,
        municipality_id: str,
        district_id: str,
        clarifications: list[dict] | None = None,
        image: ImageInput | None = None,
    ) -> str:
        """利用者の表現を、地域資料を探すための検索文へ言い換える。"""

        region = self._validate_region(municipality_id, district_id)
        if isinstance(self._gateway, BedrockGateway):
            return self._gateway.rewrite_query(query, clarifications or [], image=image, region=region)
        return self._gateway.rewrite_query(query, clarifications or [], image=image)

    def retrieve(
        self,
        *,
        rewritten_query: str,
        municipality_id: str,
        district_id: str,
    ) -> list[RetrievedDocument]:
        """言い換え済み検索文で地域別Knowledge Baseを検索する。"""

        region = self._validate_region(municipality_id, district_id)
        if region.is_nakajima:
            try:
                matches = NakajimaSearchService().search(rewritten_query)
            except FileNotFoundError as error:
                raise WasteGuideError("Nakajima source data is unavailable") from error
            documents = [RetrievedDocument(
                text=f"品目: {row['item']}\n分類: {row['category_display']} ({row['category']})\n出し方・条件: {row['note']}",
                score=row['score'], uri=f"nakajima://items/{row['item_id']}",
                title="中島地域 2026年度ごみカレンダー（公式）",
            ) for row in matches]
            normalized_query = unicodedata.normalize("NFKC", rewritten_query).lower()
            documented_example = any(
                row["item_id"].startswith("nk-item-") and row["score"] >= .9
                for row in matches
            )
            food_bottle_rule = (
                any(row["item_id"].startswith("nk-rule-") and row["category"] == "びん"
                    for row in matches)
                and any(word in normalized_query for word in (
                    "ジャム", "食品", "食料", "飲料", "調味料", "しょうゆ", "醤油",
                    "みりん", "料理酒", "ビール", "ワイン", "ラムネ", "牛乳",
                ))
            )
            if documented_example or food_bottle_rule:
                return documents
            # Search the existing 1,756 vectors once, then replace the mainland
            # category/note with an independently sourced Nakajima rule.  The
            # broader candidate pool compensates for unresolved conditional rows.
            search_candidates = getattr(self._gateway, "search_item_candidates", None)
            if search_candidates is None:
                return documents  # Test gateways without a vector adapter.
            try:
                candidates = search_candidates(rewritten_query, limit=24)
            except WasteGuideError:
                # The previously supported 79 official rows remain available
                # when a local installation has no shared vector bundle.
                logger.warning("Shared item index unavailable for Nakajima; using official examples only")
                return documents
            explicit_names = {
                self._normalize_question(row["item"])
                for row in matches
                if not row["item_id"].startswith("nk-rule-")
            }
            for match in candidates:
                if len(documents) >= config.RAG_TOP_K:
                    break
                if match.score < 0.4 or self._normalize_question(match.item) in explicit_names:
                    continue
                rule = resolve_shared_item(match)
                if rule.category is None:
                    continue
                documents.append(RetrievedDocument(
                    text=island_evidence_text(match, rule),
                    score=match.score,
                    uri=f"nakajima://shared/{match.item_id}",
                    title="中島地域 2026年度共通分別ルール",
                ))
            return documents
        # 既定は意味検索(Embedding)単体。表層一致は設定で併用可能。
        lexical_documents: list[RetrievedDocument] = []
        if config.LEXICAL_SEARCH_ENABLED:
            if self._item_search is None:
                self._item_search = ItemSearchService()
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
        return self._fuse_documents(lexical_documents, vector_documents)

    @staticmethod
    def _fuse_documents(
        lexical: list[RetrievedDocument],
        vector: list[RetrievedDocument],
        *,
        rrf_k: int = 60,
    ) -> list[RetrievedDocument]:
        """表層一致とEmbeddingの結果をRRFで統合し、重複品目をまとめる。

        両方の検索で上位に来た品目を押し上げ、同一品目（同一uri）の重複を
        除く。スコアは両検索の最大値を残し、既存の確信度ガードと整合させる。
        """

        fused: dict[str, dict] = {}
        for documents in (lexical, vector):
            for rank, document in enumerate(documents):
                key = document.uri or document.text
                entry = fused.get(key)
                contribution = 1.0 / (rrf_k + rank)
                if entry is None:
                    fused[key] = {
                        "document": document,
                        "rrf": contribution,
                        "best_score": document.score or 0.0,
                    }
                else:
                    entry["rrf"] += contribution
                    if (document.score or 0.0) > entry["best_score"]:
                        entry["best_score"] = document.score or 0.0
                        entry["document"] = document
        ordered = sorted(fused.values(), key=lambda entry: -entry["rrf"])
        results: list[RetrievedDocument] = []
        for entry in ordered[: config.RAG_TOP_K]:
            document = entry["document"]
            results.append(
                RetrievedDocument(
                    text=document.text,
                    score=entry["best_score"],
                    uri=document.uri,
                    title=document.title,
                )
            )
        return results

    def decide(
        self,
        *,
        query: str,
        rewritten_query: str,
        documents: list[RetrievedDocument],
        municipality_id: str,
        district_id: str,
        clarifications: list[dict] | None = None,
        image: ImageInput | None = None,
    ) -> WasteGuideResult:
        """検索根拠から分類を決め、回答または追加質問を組み立てる。"""

        region = self._validate_region(municipality_id, district_id)
        if region.is_nakajima and any(not (doc.uri or "").startswith("nakajima://") for doc in documents):
            raise UnsupportedRegionError("中島地域以外の検索根拠を使用できません。")
        if not region.is_nakajima and any((doc.uri or "").startswith("nakajima://") for doc in documents):
            raise UnsupportedRegionError("中島地域の検索根拠を使用できません。")
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
        if region.is_nakajima:
            container_question = self._nakajima_container_question(query, clarification_items)
            if container_question:
                previous_questions = [item.get("question", "") for item in clarification_items]
                if (len(previous_questions) >= config.MAX_CLARIFICATION_TURNS
                        or any(self._normalize_question(container_question)
                               == self._normalize_question(previous)
                               for previous in previous_questions)):
                    return WasteGuideResult(
                        status="unable_to_determine",
                        rewritten_query=rewritten_query,
                        answer="中島地域の公式資料から、この容器の分別を確定できませんでした。用途や材質を確認してください。",
                        decision=ClassificationDecision(is_resolved=False),
                        sources=documents[:3],
                    )
                return WasteGuideResult(
                    status="needs_clarification",
                    rewritten_query=rewritten_query,
                    follow_up_question=container_question,
                    decision=ClassificationDecision(is_resolved=False),
                    sources=documents[:3],
                )
        if isinstance(self._gateway, BedrockGateway):
            decision = self._gateway.classify(query, clarification_items, documents,
                                              image=image, region=region)
        else:
            decision = self._gateway.classify(query, clarification_items, documents, image=image)
        if decision.category_code and decision.category_code not in region.category_codes:
            decision = replace(decision, is_resolved=False, category_code="")
        detail_query = " ".join(
            part for part in (query, rewritten_query) if part.strip()
        )
        ambiguity_question = self._missing_detail_question(
            query=query,
            clarifications=clarification_items,
            documents=documents,
        )
        conditional_question = self._conditional_evidence_question(
            query=detail_query,
            clarifications=clarification_items,
            documents=documents,
            region=region,
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
        elif (
            not decision.is_resolved
            and len(clarification_items) >= config.MAX_CLARIFICATION_TURNS
        ):
            structured_decision = self._resolve_answered_structured_conditions(
                query=query,
                clarifications=clarification_items,
                documents=documents,
            )
            if structured_decision is not None:
                logger.info(
                    "Resolved classification from fully answered structured evidence: %s",
                    query,
                )
                decision = structured_decision
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

        if self._calendar is None or self._calendar.region.area_id != region.area_id:
            self._calendar = CalendarService(region=region)
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
        answer = self._build_answer(decision, next_collection, region=region)
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
    def _nakajima_container_question(query: str, clarifications: list[dict]) -> str | None:
        """Do not let query rewriting turn an unspecified container into a type."""

        context = unicodedata.normalize(
            "NFKC", " ".join([query] + [str(item.get("answer", "")) for item in clarifications])
        ).lower()
        food_use_answer = next((
            unicodedata.normalize("NFKC", str(item.get("answer", ""))).strip().lower()
            for item in reversed(clarifications)
            if "飲料" in unicodedata.normalize("NFKC", str(item.get("question", "")))
            and any(word in unicodedata.normalize("NFKC", str(item.get("question", "")))
                    for word in ("食料品", "食料用品", "食品"))
        ), "")
        confirmed_food_bottle = food_use_answer in (
            "はい", "ええ", "そうです", "そのとおりです", "yes",
        )
        bottle = any(word in context for word in ("びん", "ビン", "瓶"))
        can = "缶" in context
        if can and bottle:
            selected = next((
                unicodedata.normalize("NFKC", str(item.get("answer", ""))).strip().lower()
                for item in reversed(clarifications)
                if unicodedata.normalize("NFKC", str(item.get("answer", ""))).strip().lower()
                in ("缶", "空き缶", "缶だけ", "びん", "ビン", "瓶", "びんだけ", "瓶だけ")
            ), "")
            if selected in ("缶", "空き缶", "缶だけ"):
                bottle = False
            elif selected in ("びん", "ビン", "瓶", "びんだけ", "瓶だけ"):
                can = False
            else:
                return "捨てるのは缶とびんのどちらですか？"
        if bottle and not any(word in context for word in ("ふた", "フタ", "キャップ")):
            if not confirmed_food_bottle and not any(word in context for word in (
                "飲料", "食料", "食品", "調味料", "ジャム", "しょうゆ", "醤油", "みりん",
                "料理酒", "ビール", "ワイン", "ラムネ", "牛乳", "ドレッシング",
            )):
                return "そのびんは飲料・食料品用ですか？"
        if can and not any(word in context for word in (
            "缶詰", "アルミ缶", "スチール缶", "飲料", "ジュース", "お茶",
            "ビール", "コーヒー", "スプレー缶", "一斗缶", "缶切り",
            "缶バッジ", "カセットボンベ",
        )):
            return "その缶は飲料・缶詰用ですか、それとも別の用途ですか？"
        return None

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

        beverage_markers = ("ジュース", "飲料", "お茶", "水", "酒", "しょうゆ")
        if "容器" in text and any(marker in text for marker in beverage_markers):
            return (
                "飲料などの容器は、PETマークのあるペットボトル・"
                "プラマークのある容器・紙パック・ガラスびん・金属缶のどれですか？"
            )
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
        region: RegionContext | None = None,
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
            "入ります",
            "入りません",
            "指定袋",
            "粗大",
            "cm",
            "センチ",
        )
        if size_branch and not any(answer in context for answer in size_answers):
            return ("中島地域の45L以下の透明袋に入る大きさですか？"
                    if region and region.is_nakajima else "松山市の指定ごみ袋に入る大きさですか？")

        explicitly_non_plastic = any(
            marker in context
            for marker in ("紙製", "紙の", "紙箱", "ガラス", "金属", "陶器", "陶磁器")
        )
        if "プラマーク" in evidence and not explicitly_non_plastic and not any(
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

    @classmethod
    def _resolve_answered_structured_conditions(
        cls,
        *,
        query: str,
        clarifications: list[dict],
        documents: list[RetrievedDocument],
    ) -> ClassificationDecision | None:
        """回答済みの分岐条件を、完全一致した地域資料へ適用する。"""

        if not documents:
            return None
        document = documents[0]
        if not document.uri or not document.uri.startswith("local://items/"):
            return None
        if document.score is None or document.score < 0.5:
            return None

        lines = document.text.splitlines()
        if not lines or not lines[0].startswith("品目:"):
            return None
        item_name = lines[0].removeprefix("品目:").strip()
        normalized_item = cls._normalize_question(
            re.sub(r"[（(].*$", "", item_name)
        )
        normalized_query = cls._normalize_question(query)
        if not normalized_item or normalized_item not in normalized_query:
            return None

        values = {}
        for line in lines[1:]:
            key, separator, value = line.partition(":")
            if separator:
                values[key.strip()] = value.strip()
        category_code = values.get("分類コード", "")
        if category_code not in CATEGORY_NAMES:
            return None

        context = unicodedata.normalize(
            "NFKC",
            " ".join(
                [query]
                + [str(item.get("answer", "")) for item in clarifications]
            ),
        ).lower()
        evidence = unicodedata.normalize("NFKC", document.text)
        conditional_categories = (
            (("袋に入らない", "袋に入りません"), "袋に入らない"),
            (("金属", "アルミ", "スチール"), "金属製"),
            (("プラスチック", "樹脂"), "プラスチック製"),
            (("ガラス",), "ガラス製"),
            (("陶器", "セラミック"), "陶器製"),
            (("紙製", "紙の"), "紙製"),
            (("事業用", "仕事で", "店舗で"), "事業用"),
            (("プラマーク", "プラ表示", "マークあり"), "プラマーク"),
            (("電動", "電池", "充電", "電気式"), "電気・電池を使用するもの"),
        )
        for answers, condition in conditional_categories:
            if not any(answer in context for answer in answers):
                continue
            condition_position = evidence.find(condition)
            if condition_position < 0:
                continue
            condition_text = evidence[condition_position : condition_position + 80]
            for candidate_code in CATEGORY_NAMES:
                if f"「{candidate_code}」" in condition_text:
                    category_code = candidate_code
                    break

        return ClassificationDecision(
            is_resolved=True,
            item_name=query.strip(),
            category_code=category_code,
            disposal_instructions=values.get("出し方・注意", ""),
            confidence=max(0.9, document.score),
            evidence_indexes=(1,),
        )

    @staticmethod
    def _validate_region(municipality_id: str, district_id: str) -> RegionContext:
        try:
            return get_registry().resolve(municipality_id, district_id)
        except RegionResolutionError as error:
            raise UnsupportedRegionError(str(error)) from error

    @staticmethod
    def _build_answer(
        decision: ClassificationDecision, next_collection: CollectionDate | None,
        *, region: RegionContext | None = None,
    ) -> str:
        category_name = CATEGORY_NAMES[decision.category_code]
        lines = [f"{decision.item_name}は「{category_name}」です。"]
        if decision.disposal_instructions:
            lines.append(decision.disposal_instructions)
        if next_collection:
            lines.append(
                f"{region.area_name if region else '清水'}地区の次回収集日は{next_collection.display_date}です。"
            )
        elif decision.category_code == "粗大" and not (region and region.is_nakajima):
            lines.append("粗大ごみは戸別収集の申し込みが必要です。")
        elif decision.category_code == "禁止":
            lines.append("松山市のごみ集積場所には出せません。")
        else:
            lines.append("公開済みカレンダーの範囲では次回収集日を確認できません。")
        return "\n".join(lines)
