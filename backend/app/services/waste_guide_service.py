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
from .calendar_service import CalendarService, CollectionDate, CollectionStatus
from .embedding_search_service import EmbeddingSearchService
from .item_search_service import ItemSearchService
from .nakajima_search_service import NakajimaSearchService
from .matsuyama_prompt_rules import classification_guidance
from .nakajima_rule_service import evidence_text as island_evidence_text, resolve_shared_item
from .region_registry_service import (
    CATEGORY_DEFINITIONS, RegionContext, RegionResolutionError, RegionalDataError, get_registry,
)

logger = logging.getLogger(__name__)

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
    category_name: str | None = None
    collection_status: CollectionStatus | None = None


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
        self._regional_embedding_searches: dict[tuple, EmbeddingSearchService] = {}

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
{region.municipality_label if region else '松山市'}{region.area_name if region else '清水'}地区のごみ分別データを検索するため、利用者の表現を短い検索文に言い換えてください。
品目、素材、大きさ、用途、汚れの状態など、分類に必要な語を残してください。
利用者の表現から社会通念上ほぼ一意に判断できる特徴は、検索に必要な範囲で補って構いません。
例えば「お弁当の透明なフタ」は、繰り返し使う弁当箱ではなく、一般的な使い捨ての
「弁当・惣菜の透明なプラスチック製容器のふた」として検索してください。
複数の解釈が現実的に残る場合は、推測で情報を追加しないでください。
「{region.municipality_label if region else '松山市'}」「{region.area_name if region else '清水'}地区」「ごみ分別」のような検索対象側で既知の語は追加しないでください。
「キャップとラベルを外したペットボトル本体」は本体を検索し、外した部品を検索対象として追加しないでください。
「ペットボトルから外したキャップ」は逆にキャップが対象です。本体と取り外した部品を区別してください。
マークの「ない」「不明」を「あり」に変換してはいけません。
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
        cleaned = self._clean_rewritten_query(rewritten, region=region)
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
    def _clean_rewritten_query(value: str, region: RegionContext | None = None) -> str:
        cleaned = value
        municipality = region.municipality_label if region else "松山市"
        area = region.area_name if region else "清水"
        for phrase in (
            f"{municipality}{area}地区",
            municipality,
            f"{area}地区",
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
        )
        additions: list[str] = []
        for markers, canonical in feature_groups:
            if any(marker in source for marker in markers) and not any(
                marker in normalized_cleaned for marker in markers
            ):
                additions.append(canonical)

        # Keep presence/absence/unknown as stated, including when the LLM
        # contradicts it. A bare mark mention is not confirmation of presence.
        mark_source = re.sub(r"\s+", "", source)
        for term, aliases in (
            ("PETマーク", r"pet(?:マーク|表示)"),
            ("プラマーク", r"プラ(?:マーク|表示)"),
        ):
            mark_context = mark_source
            for answer in reversed(clarifications):
                question = re.sub(
                    r"\s+",
                    "",
                    unicodedata.normalize("NFKC", str(answer.get("question", ""))),
                ).lower()
                reply = re.sub(
                    r"\s+", "", unicodedata.normalize("NFKC", str(answer.get("answer", "")))
                ).lower()
                if re.search(aliases, reply):
                    mark_context = reply
                    break
                if re.search(
                    aliases + r"(?:は|が)?(?:付いていますか|ついていますか|ありますか)",
                    question,
                ) and re.fullmatch(r"(?:はい|いいえ)[。!！]?", reply):
                    mark_context = term.lower() + (
                        "あり" if reply.startswith("はい") else "なし"
                    )
                    break
            if not re.search(aliases, mark_context):
                continue
            negative = r"(?:は|が|の)?(?:(?:付|つ)いてい(?:ない|ません)|ありません|無い|無し|ない|なし)"
            positive = r"(?:は|が|の)?(?:付い(?:た|ている|ています)|ついている|付き|ある|あり(?!ません)(?:ます)?)"
            unknown = (
                r"(?:は|が)?(?:不明|未確認|わからない|わかりません|分からない|分かりません)"
            )
            absent = bool(re.search(aliases + negative, mark_context))
            present = bool(re.search(aliases + positive, mark_context))
            uncertain = bool(
                re.search(
                    aliases
                    + r"(?:は|が|の)?(?:(?:付|つ)いているか(?:どうか)?(?:は)?|あるか(?:どうか)?(?:は)?)?(?:不明|未確認|わから|わかりません|分から|分かりません)",
                    mark_context,
                )
            )
            uncertain = uncertain or bool(
                re.search(aliases + positive + "か", mark_context)
            )
            state = "" if uncertain or absent == present else "なし" if absent else "あり"
            canonical = term + state
            if re.search(aliases, cleaned, re.IGNORECASE):
                cleaned = re.sub(
                    aliases + r"(?:" + negative + "|" + positive + "|" + unknown + r")?",
                    canonical,
                    cleaned,
                    flags=re.IGNORECASE,
                )
            else:
                additions.append(canonical)

        # An explicitly requested PET body must not gain bare cap/label tokens
        # merely because the user described removing those parts. This only
        # preserves retrieval intent; classification still uses regional evidence.
        pet_body = BedrockGateway._pet_body_is_target(source)

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
            "本体",
        )
        for marker in part_markers:
            if marker == "本体" and not pet_body:
                continue
            if pet_body and marker in {"キャップ", "ふた", "蓋"}:
                continue
            if marker in source and marker not in normalized_cleaned:
                additions.append(marker)
        return " ".join([cleaned, *dict.fromkeys(additions)]).strip()

    @staticmethod
    def _pet_body_is_target(value: str) -> bool:
        source = unicodedata.normalize("NFKC", value).lower()
        return "ペットボトル" in source and bool(re.search(
            r"本体(?:です|を(?:捨て|出)|だけ|のみ|[。、!！?？]|$)", source
        )) and not re.search(
            r"本体だけではなく|本体(?:と|や|から)|本体(?:は|を)?(?:捨て(?:ない|ません|ず)|残|以外)", source
        )

    def retrieve(self, query: str, *, region: RegionContext | None = None) -> list[RetrievedDocument]:
        """クエリの意味検索。既定は自前Embedding、任意でマネージドKBを併用。"""

        if not config.USE_BEDROCK_KNOWLEDGE_BASE:
            return self._retrieve_by_embedding(query, region=region)
        return self._retrieve_from_knowledge_base(query, region=region)

    def _retrieve_by_embedding(self, query: str, *, region: RegionContext | None = None) -> list[RetrievedDocument]:
        return [
            RetrievedDocument(
                text=match.evidence_text,
                score=match.score,
                uri=(f"{region.evidence_prefix}items/{match.item_id}"
                     if region and region.municipality_id != "38201" else f"local://items/{match.item_id}"),
                title=(region.rules.knowledge_title or f"{region.municipality_label}ごみ分別辞典") + "（意味検索）"
                      if region else "松山市ごみ分別辞典（意味検索）",
            )
            for match in self.search_item_candidates(query, region=region)
        ]

    def search_item_candidates(self, query: str, *, limit: int | None = None,
                               region: RegionContext | None = None):
        """Return shared item identities; callers choose regional evidence."""
        try:
            if region is None or (region.municipality_id == "38201" and self._embedding_search is not None):
                if self._embedding_search is None:
                    self._embedding_search = EmbeddingSearchService(runtime_client=self._runtime)
                search = self._embedding_search
            else:
                key = (region.municipality_id, region.rule_profile_id, region.version,
                       region.asset_path("items_path"), region.asset_path("embedding_index_path"))
                if key not in self._regional_embedding_searches:
                    self._regional_embedding_searches[key] = EmbeddingSearchService(
                        items_path=region.asset_path("items_path"),
                        embeddings_path=region.asset_path("embedding_index_path"),
                        runtime_client=self._runtime, municipality_id=region.municipality_id,
                        profile_id=region.rules.index_profile_id,
                    )
                search = self._regional_embedding_searches[key]
        except (OSError, ValueError, KeyError) as error:
            raise WasteGuideError("Verified regional item index is unavailable") from error
        if not getattr(search, "is_ready", True):
            raise WasteGuideError("Verified regional item index is unavailable")
        matches = search.search(query, limit=limit)
        if region and region.municipality_id != "38201" and any(
                (match.category and match.category not in region.category_codes) or
                any(code not in region.category_codes for code in match.category_options) for match in matches):
            raise WasteGuideError("Item data contains an unknown regional category")
        return matches

    def _retrieve_from_knowledge_base(self, query: str, *, region: RegionContext | None = None) -> list[RetrievedDocument]:
        knowledge_base_id = (region.rules.knowledge_base_id if region and region.municipality_id != "38201"
                             else config.BEDROCK_KNOWLEDGE_BASE_ID)
        if not knowledge_base_id:
            raise WasteGuideError("BEDROCK_KNOWLEDGE_BASE_ID is not configured")
        try:
            response = self._agent_runtime.retrieve(
                knowledgeBaseId=knowledge_base_id,
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
                    uri=(f"{region.evidence_prefix}kb/{len(documents)}"
                         if region and region.municipality_id != "38201" else uri),
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
        if region is None or region.municipality_id == "38201":
            profile_note, examples, size_example = classification_guidance(island)
        else:
            profile_note = "選択した自治体・分別設定の公式資料に記載された根拠だけを使ってください。"
            examples = region.rules.classification_rules
            size_example = "大きさによる分岐は該当地域の検索根拠に従ってください。"
        condition_examples = (
            "根拠の「金属製のものは『金・ガ』」「袋に入らないものは『粗大』」"
            "「プラマークがあれば『プラ』」「事業用は排出禁止」等は、注意書きではなく分類の分岐条件である。"
            if region is None or region.municipality_id == "38201" else
            "根拠にある素材・大きさ・表示・排出元による分類の変更は、注意書きではなく分岐条件である。"
        )
        dimension_based = region is not None and region.rules.size_threshold_cm is not None
        size_check = (
            f"{region.rules.size_question}。検索根拠に大きさによる分類の分岐があるか。"
            if dimension_based else "指定袋に入るかどうかで、通常ごみと粗大ごみに分かれないか。"
        )
        size_question_rule = (
            "素材によって分類が変わるなら素材を聞く。大きさによって変わるなら、地域資料にある寸法の条件を聞く。"
            if dimension_based else "素材によって分類が変わるなら素材を聞く。大きさによって変わるなら指定袋に入るかを聞く。"
        )
        prompt = f"""
あなたは{region.municipality_label if region else '松山市'}のごみ分別判定器です。検索根拠だけを使い、品目の分類を判定してください。
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
   - 大きさ: {size_check}
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
- {condition_examples}
- 分岐条件に必要な情報が質問・補足にない場合、行に記載された既定の分類コードだけを採用してはいけない。
- 素材や大きさで分類が分かれる場合だけ、利用者に確認する。{size_example}
- 一方、「すすいで出す」「電池は外す」「危なくないように包む」のように分類コードが変わらない記述は、
  追加質問の理由にせず disposal_instructions で案内する。

{examples}

追加質問の規則:
- 一度に質問する論点は一つだけにし、可能なら根拠に存在する選択肢を短く示す。
- {size_question_rule}
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
            self._document_supports_category(documents[index - 1], category_code, region=region)
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
        document: RetrievedDocument, category_code: str, *, region: RegionContext | None = None
    ) -> bool:
        names = region.category_names if region else CATEGORY_NAMES
        text = unicodedata.normalize("NFKC", document.text)
        structured = re.search(r"^分類(?:コード)?:\s*([^\n]+)", text, re.MULTILINE)
        if structured:
            label = names.get(category_code, "")
            if structured.group(1).strip() in (category_code, label, f"{label} ({category_code})"):
                return True
            # Opt-in, explicit alternatives for conditional official rows. Preserve
            # Matsuyama's established decision path and never infer codes from notes.
            if region and region.municipality_id != "38201":
                alternative = re.search(r"^条件付き分類コード:\s*(\[[^\n]*\])", text, re.MULTILINE)
                if alternative:
                    try:
                        options = json.loads(alternative.group(1))
                        return isinstance(options, list) and category_code in options and all(
                            code in region.category_codes for code in options)
                    except (ValueError, TypeError):
                        return False
            return False
        category_name = names.get(category_code, "")
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
        self._gateway = gateway
        # 言い換え処理ではカレンダーも表層検索CSVも不要。ローカルでそれらの
        # Git管理外データが未配置でも、必要な段階までは初期化しない。
        self._calendar = calendar
        self._item_search = item_search
        self._regional_item_searches: dict[tuple, ItemSearchService] = {}
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
            original_query=query,
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
        if self._gateway is None:
            self._gateway = BedrockGateway()
        if isinstance(self._gateway, BedrockGateway):
            return self._gateway.rewrite_query(query, clarifications or [], image=image, region=region)
        return self._gateway.rewrite_query(query, clarifications or [], image=image)

    def retrieve(
        self,
        *,
        rewritten_query: str,
        original_query: str | None = None,
        municipality_id: str,
        district_id: str,
    ) -> list[RetrievedDocument]:
        """言い換え済み検索文で地域別Knowledge Baseを検索する。"""

        region = self._validate_region(municipality_id, district_id)
        if self._gateway is None:
            self._gateway = BedrockGateway()
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
                candidates = (search_candidates(rewritten_query, limit=24, region=region)
                              if isinstance(self._gateway, BedrockGateway) else
                              search_candidates(rewritten_query, limit=24))
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
        # 意味検索は表現の揺れに強い一方、LLMの言い換えが公式品目名を
        # 落とすことがある。元入力に公式品目名が明記されている場合だけは、
        # 設定にかかわらず同じ自治体のCSVから完全一致候補を補う。
        lexical_documents: list[RetrievedDocument] = []
        exact_documents: list[RetrievedDocument] = []
        if municipality_id != "38201":
            try:
                search = self._regional_item_search(region)
            except (OSError, ValueError, KeyError) as error:
                raise WasteGuideError("Verified regional item index is unavailable") from error
            exact_documents = self._exact_item_documents(
                search=search,
                query=original_query or rewritten_query,
                region=region,
            )
        if config.LEXICAL_SEARCH_ENABLED:
            try:
                if municipality_id == "38201" and self._item_search is not None:
                    search = self._item_search
                elif municipality_id == "38201":
                    search = ItemSearchService()
                else:
                    search = self._regional_item_search(region)
            except (OSError, ValueError, KeyError) as error:
                raise WasteGuideError("Regional item data is unavailable") from error
            lexical_documents = [
                RetrievedDocument(
                    text=match.evidence_text,
                    score=match.score,
                    uri=(f"local://items/{match.item_id}" if municipality_id == "38201"
                         else f"{region.evidence_prefix}items/{match.item_id}"),
                    title=(region.rules.knowledge_title or f"{region.municipality_label}ごみ分別辞典") + "（品目検索）",
                )
                for match in search.search(
                    rewritten_query, limit=config.LEXICAL_SEARCH_TOP_K
                )
            ]
        lexical_documents = self._deduplicate_documents(
            [*exact_documents, *lexical_documents]
        )
        vector_documents = (self._gateway.retrieve(rewritten_query, region=region)
                            if isinstance(self._gateway, BedrockGateway) else self._gateway.retrieve(rewritten_query))
        return self._fuse_documents(lexical_documents, vector_documents)

    def _regional_item_search(self, region: RegionContext) -> ItemSearchService:
        key = (
            region.municipality_id,
            region.rule_profile_id,
            region.version,
            region.asset_path("items_path"),
        )
        if key not in self._regional_item_searches:
            self._regional_item_searches[key] = ItemSearchService(
                items_path=region.asset_path("items_path"),
                municipality_id=region.municipality_id,
            )
        return self._regional_item_searches[key]

    @classmethod
    def _exact_item_documents(
        cls,
        *,
        search: ItemSearchService,
        query: str,
        region: RegionContext,
    ) -> list[RetrievedDocument]:
        normalized_query = cls._normalize_item_key(query)
        documents: list[RetrievedDocument] = []
        for match in search.search(query, limit=24):
            base_name = re.sub(r"[（(].*$", "", match.item).strip()
            if not cls._item_name_matches_query(base_name, query):
                continue
            documents.append(
                RetrievedDocument(
                    text=match.evidence_text,
                    score=match.score,
                    uri=f"{region.evidence_prefix}items/{match.item_id}",
                    title=(
                        region.rules.knowledge_title
                        or f"{region.municipality_label}ごみ分別辞典"
                    )
                    + "（品目名一致）",
                )
            )
        return documents

    @staticmethod
    def _deduplicate_documents(
        documents: list[RetrievedDocument],
    ) -> list[RetrievedDocument]:
        unique: dict[str, RetrievedDocument] = {}
        for document in documents:
            key = document.uri or document.text
            unique.setdefault(key, document)
        return list(unique.values())

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
        if municipality_id != "38201" and any(
                not (doc.uri or "").startswith(region.evidence_prefix) for doc in documents):
            raise UnsupportedRegionError("指定された自治体・分別設定・データ版以外の検索根拠は使用できません。")
        if municipality_id == "38201" and any((doc.uri or "").startswith("regional://") for doc in documents):
            raise UnsupportedRegionError("他の自治体の検索根拠は使用できません。")
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
                        f"いただいた情報は反映しましたが、{region.municipality_label}の公開資料から分類を"
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
        if self._gateway is None:
            self._gateway = BedrockGateway()
        if isinstance(self._gateway, BedrockGateway):
            decision = self._gateway.classify(query, clarification_items, documents,
                                              image=image, region=region)
        else:
            decision = self._gateway.classify(query, clarification_items, documents, image=image)
        if decision.category_code and decision.category_code not in region.category_codes:
            decision = replace(decision, is_resolved=False, category_code="")
        if municipality_id != "38201":
            explicit_detail = bool(clarification_items) or any(
                marker in unicodedata.normalize("NFKC", query).lower()
                for marker in (
                    "袋に入",
                    "袋に収ま",
                    "cm",
                    "センチ",
                    "木製",
                    "紙製",
                    "プラスチック",
                    "金属",
                    "ガラス",
                    "陶器",
                    "汚れ",
                    "洗った",
                    "すすいだ",
                    "マーク",
                )
            )
            exact_decision = (
                self._resolve_exact_structured_decision(
                    query=query,
                    clarifications=clarification_items,
                    documents=documents,
                    region=region,
                )
                if decision.is_resolved or explicit_detail
                else None
            )
            if exact_decision is not None:
                logger.info(
                    "Resolved classification from exact regional evidence: %s",
                    query,
                )
                decision = exact_decision
        detail_query = " ".join(
            part for part in (query, rewritten_query) if part.strip()
        )
        ambiguity_question = self._missing_detail_question(
            query=query,
            clarifications=clarification_items,
            documents=documents,
            region=region,
        )
        conditional_question = self._carry_condition_question(
            query=query,
            clarifications=clarification_items,
            documents=documents,
        ) or self._conditional_evidence_question(
            # A rewritten search term is not confirmation of the user's size
            # or material. Preserve the legacy Matsuyama path; regional data
            # must use the original input and answers for condition checks.
            query=detail_query if municipality_id == "38201" else query,
            clarifications=clarification_items,
            documents=documents,
            region=region,
            selected_evidence_indexes=decision.evidence_indexes,
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
            and municipality_id == "38201"
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
                        f"いただいた情報は反映しましたが、{region.municipality_label}の公開資料から分類を"
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

        if self._calendar is None or self._calendar.region != region:
            try:
                self._calendar = CalendarService(region=region)
            except (OSError, ValueError, KeyError) as error:
                raise WasteGuideError("Regional calendar data is invalid") from error
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
        collection_status = self._calendar.collection_status(decision.category_code, next_collection)
        answer = self._build_answer(decision, next_collection, region=region, collection_status=collection_status)
        return WasteGuideResult(
            status="answered",
            rewritten_query=rewritten_query,
            answer=answer,
            decision=decision,
            next_collection=next_collection,
            sources=sources,
            category_name=region.category_names[decision.category_code],
            collection_status=collection_status,
        )

    @staticmethod
    def _normalize_question(question: str) -> str:
        value = unicodedata.normalize("NFKC", question).lower()
        return re.sub(r"[\s\W_]+", "", value)

    @classmethod
    def _normalize_item_key(cls, value: str) -> str:
        return cls._normalize_question(value).replace("衣裳", "衣装")

    @classmethod
    def _item_name_matches_query(cls, item_name: str, query: str) -> bool:
        normalized_item = cls._normalize_item_key(item_name)
        normalized_query = cls._normalize_item_key(query)
        # Exact CSV supplements must preserve the requested part as well as the
        # item name. A cap mentioned while describing its removal is not the
        # disposal target of an explicitly requested PET body, and vice versa.
        context = unicodedata.normalize("NFKC", query).lower()
        if "ペットボトル" in context:
            body_target = BedrockGateway._pet_body_is_target(context)
            part_target = not body_target and re.search(
                r"(?:キャップ|ラベル|ふた|蓋)(?:だけ|のみ|です|を(?:捨て|出)|[。、!！?？]|$)", context
            )
            if body_target and any(part in item_name for part in ("キャップ", "ラベル", "ふた", "蓋")):
                return False
            if part_target and "本体" in item_name:
                return False
        if len(normalized_item) >= 2 and normalized_item in normalized_query:
            return True
        # 「油容器（プラ製）」に対する「油のプラスチック容器」のように、
        # 素材語が品目名の途中へ入る自然な表現を同じ容器として扱う。
        if normalized_item.endswith("容器"):
            prefix = normalized_item.removesuffix("容器")
            return len(prefix) >= 1 and prefix in normalized_query and "容器" in normalized_query
        return False

    @classmethod
    def _matching_structured_documents(
        cls,
        *,
        query: str,
        documents: list[RetrievedDocument],
    ) -> list[tuple[int, RetrievedDocument, str]]:
        """Return official rows whose base item name occurs in the user input."""

        normalized_query = cls._normalize_item_key(query)
        matches: list[tuple[int, RetrievedDocument, str]] = []
        for index, document in enumerate(documents, start=1):
            first_line = document.text.splitlines()[0] if document.text else ""
            if not first_line.startswith("品目:"):
                continue
            item_name = first_line.removeprefix("品目:").strip()
            base_name = re.sub(r"[（(].*$", "", item_name).strip()
            if cls._item_name_matches_query(base_name, query):
                matches.append((index, document, item_name))
        return matches

    @staticmethod
    def _structured_values(document: RetrievedDocument) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in document.text.splitlines()[1:]:
            key, separator, value = line.partition(":")
            if separator:
                values[key.strip()] = value.strip()
        return values

    @staticmethod
    def _material_in_context(context: str) -> bool:
        return any(
            marker in context
            for marker in (
                "プラスチック",
                "プラ製",
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
        )

    @classmethod
    def _exact_material_question(
        cls,
        *,
        query: str,
        clarifications: list[dict],
        documents: list[RetrievedDocument],
    ) -> str | None:
        matches = cls._matching_structured_documents(query=query, documents=documents)
        if len(matches) < 2:
            return None
        context = unicodedata.normalize(
            "NFKC",
            " ".join([query] + [str(item.get("answer", "")) for item in clarifications]),
        ).lower()
        if cls._material_in_context(context):
            return None
        bases: dict[str, list[str]] = {}
        for _, _, item_name in matches:
            base_name = re.sub(r"[（(].*$", "", item_name).strip()
            qualifier_match = re.search(r"[（(]([^）)]+)[）)]", item_name)
            qualifier = qualifier_match.group(1) if qualifier_match else ""
            if qualifier and any(
                marker in qualifier
                for marker in ("紙", "プラ", "樹脂", "金属", "木", "ガラス", "陶器")
            ):
                bases.setdefault(base_name, []).append(qualifier)
        ambiguous = next(
            ((base, qualifiers) for base, qualifiers in bases.items() if len(set(qualifiers)) >= 2),
            None,
        )
        if ambiguous is None:
            return None
        base_name, qualifiers = ambiguous
        examples = "・".join(dict.fromkeys(qualifiers))
        return f"{base_name}は何製ですか？（{examples}）"

    @classmethod
    def _resolve_exact_structured_decision(
        cls,
        *,
        query: str,
        clarifications: list[dict],
        documents: list[RetrievedDocument],
        region: RegionContext,
    ) -> ClassificationDecision | None:
        """Apply an explicit user condition to an exact official catalog row.

        This never invents a rule: the primary category and every branch are read
        from the selected municipality's structured evidence.
        """

        matches = cls._matching_structured_documents(query=query, documents=documents)
        if not matches:
            return None
        context = unicodedata.normalize(
            "NFKC",
            " ".join([query] + [str(item.get("answer", "")) for item in clarifications]),
        ).lower()

        material_markers = {
            "紙": ("紙製", "紙の"),
            "プラ": ("プラスチック", "プラ製", "樹脂"),
            "金属": ("金属", "アルミ", "スチール"),
            "木": ("木製", "木の"),
            "ガラス": ("ガラス",),
            "陶器": ("陶器", "セラミック"),
        }
        selected = matches[0]
        selected_by_explicit_material = False
        if len(matches) > 1:
            selected_by_material = []
            for candidate in matches:
                item_name = candidate[2]
                qualifier_match = re.search(r"[（(]([^）)]+)[）)]", item_name)
                qualifier = qualifier_match.group(1) if qualifier_match else ""
                if any(
                    label in qualifier and any(marker in context for marker in markers)
                    for label, markers in material_markers.items()
                ):
                    selected_by_material.append(candidate)
            if len(selected_by_material) == 1:
                selected = selected_by_material[0]
                selected_by_explicit_material = True
            elif cls._exact_material_question(
                query=query,
                clarifications=clarifications,
                documents=documents,
            ):
                return None

        evidence_index, document, _ = selected
        values = cls._structured_values(document)
        primary = values.get("分類コード", "")
        if primary not in region.category_codes:
            return None
        item_evidence = unicodedata.normalize("NFKC", document.text).split(
            "区分共通の出し方", 1
        )[0]
        try:
            options = json.loads(values.get("条件付き分類コード", "[]"))
        except (TypeError, ValueError):
            options = []
        if not isinstance(options, list):
            options = []

        def category_in(text: str, allowed: list[str] | None = None) -> str | None:
            allowed_codes = set(allowed or region.category_codes)
            for code, label in sorted(
                region.category_names.items(), key=lambda item: len(item[1]), reverse=True
            ):
                if code in allowed_codes and (label in text or code in text):
                    return code
            return None

        def after_first(markers: tuple[str, ...]) -> str:
            positions = [item_evidence.find(marker) for marker in markers]
            positions = [position for position in positions if position >= 0]
            return item_evidence[min(positions) : min(positions) + 120] if positions else ""

        question_answers = [
            (
                unicodedata.normalize("NFKC", str(item.get("question", ""))),
                unicodedata.normalize("NFKC", str(item.get("answer", ""))).strip(),
            )
            for item in clarifications
        ]
        negative_size = any(
            marker in context
            for marker in ("袋に入らない", "袋に入りません", "袋に収まらない", "袋に収まりません")
        ) or any(
            re.search(r"袋.*(?:入|収ま)", question)
            and (
                re.match(r"いいえ(?:[、。！!]|$)", answer)
                or any(marker in answer for marker in ("入りません", "収まりません", "入らない", "収まらない"))
            )
            for question, answer in question_answers
        )
        positive_size = any(
            marker in context
            for marker in ("袋に入る", "袋に入ります", "袋に収まる", "袋に収まります")
        ) or any(
            re.search(r"袋.*(?:入|収ま)", question)
            and (
                re.match(r"はい(?:[、。！!]|$)", answer)
                or any(marker in answer for marker in ("入ります", "収まります", "入る", "収まる"))
            )
            for question, answer in question_answers
        )
        size_condition = bool(
            re.search(r"袋.{0,8}(?:入ら|入れ|収まら|収まれ|収まな)", item_evidence)
        )
        material_condition = bool(
            re.search(r"(?:木|紙|プラ|樹脂|金属|ガラス|陶器)製.{0,8}(?:なら|は)", item_evidence)
        )
        dirty_condition = "汚れが落ちない" in item_evidence
        mark_condition = "プラマーク" in item_evidence
        # Do not override Nova with the primary row when this deterministic
        # supplement cannot evaluate its official branch (e.g. Toon carryability
        # or paper-pack lining). Existing conditional guards still ask as needed.
        if options and not (size_condition or material_condition or dirty_condition or mark_condition):
            return None
        if options and re.search(r"大人[12]人", item_evidence):
            return None

        category = primary
        if negative_size and size_condition:
            tail = after_first(("袋に入ら", "袋に収まら", "袋に入れ"))
            category = category_in(tail, options) or (
                "facility_dropoff"
                if "facility_dropoff" in region.category_codes
                and any(marker in tail for marker in ("美化センター", "持込", "許可業者"))
                else "bulky" if "bulky" in options else primary
            )
        elif positive_size and size_condition:
            category = primary
        elif size_condition:
            return None

        material_branches = (
            (("木製", "木の"), ("木製なら", "木製は")),
            (("プラスチック", "プラ製", "樹脂"), ("プラスチック製", "プラ製", "樹脂製")),
            (("金属", "アルミ", "スチール"), ("金属製",)),
            (("紙製", "紙の"), ("紙製",)),
            (("ガラス",), ("ガラス製",)),
            (("陶器", "セラミック"), ("陶器製",)),
        )
        if material_condition and not selected_by_explicit_material:
            resolved_material = False
            for answers, evidence_markers in material_branches:
                if not any(answer in context for answer in answers):
                    continue
                tail = after_first(evidence_markers)
                material_category = category_in(tail, options or None)
                if material_category:
                    category = material_category
                    resolved_material = True
                    break
            if not resolved_material:
                return None

        if dirty_condition:
            if any(marker in context for marker in ("汚れが落ちない", "汚れを落とせない", "汚れが取れない")):
                category = category_in(after_first(("汚れが落ちない",))) or category
            elif not any(marker in context for marker in ("洗った", "すすいだ", "水洗いした", "水洗いしました", "水洗い済み", "汚れを取り除", "きれい")):
                return None

        if mark_condition and not any(
            marker in context for marker in ("プラマーク", "プラ表示", "マークあり", "マークなし")
        ):
            return None
        if category not in region.category_codes:
            return None
        instructions = values.get("出し方・注意", "")
        if category == primary:
            # Keep the official preparation/deadline guidance on an exact match.
            # Do not attach the primary stream's guidance to an alternate branch.
            shared = document.text.partition("区分共通の出し方")[2].partition(":")[2].strip()
            instructions = "\n".join(dict.fromkeys(part for part in (instructions, shared) if part))
        return ClassificationDecision(
            is_resolved=True,
            item_name=re.sub(r"を?(?:捨て|処分).*$", "", query).strip() or query.strip(),
            category_code=category,
            disposal_instructions=instructions,
            confidence=max(0.9, document.score or 0.0),
            evidence_indexes=(evidence_index,),
        )

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
        region: RegionContext | None = None,
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
        # A positively identified packaging mark already supplies the material.
        # Keep the established Matsuyama guard unchanged. Uncertain/negative
        # statements still require the normal evidence/model checks.
        if region and region.municipality_id != "38201" and re.search(
            r"(?:プラ|紙)マーク(?:付き(?!では|じゃ|でない|か|とは)|が付いて(?:います|いる)|あり(?!ません))",
            text,
        ):
            return None
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
    def _carry_condition_question(
        cls,
        *,
        query: str,
        clarifications: list[dict],
        documents: list[RetrievedDocument],
    ) -> str | None:
        """Keep an explicit carryability branch unresolved until the user answers.

        The highest structured candidate must have an explicit item-specific
        carryability branch. One-adult evidence requires no fixed classification;
        two-adult evidence requires bulky plus a not-collected alternative.
        Fixed entries without alternatives and Matsuyama evidence are unchanged.
        Rewritten text/image inference is not user confirmation.
        """
        structured = next((d for d in documents if d.text.startswith("品目:")), None)
        if structured is None:
            return None
        lines = structured.text.splitlines()
        primary = next((line.removeprefix("分類コード:").strip() for line in lines
                        if line.startswith("分類コード:")), None)
        encoded = next((line.removeprefix("条件付き分類コード:").strip() for line in lines
                        if line.startswith("条件付き分類コード:")), "[]")
        try:
            options = json.loads(encoded)
        except (ValueError, TypeError):
            return None
        evidence = unicodedata.normalize("NFKC", structured.text)
        # Opt-in for an explicit two-adult carryability branch. The conditional
        # metadata and item-specific note (not shared instructions) must both
        # authorize it; existing one-adult evidence keeps the original path.
        specific = evidence.split("区分共通の出し方", 1)[0]
        if (primary == "bulky" and isinstance(options, list)
                and "not_collected" in options and "大人2人" in specific
                and re.search(r"運べる|持ち運べる", specific)):
            def normalized(value):
                return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value)))
            confirmed = re.compile(r"(?:標準的な)?(?:大人)?[2二]人で(?:は|も)?(?:持ち運べ|運べ)(?:ます|ません|る|ない)")
            uncertain = re.compile(r"分か[らり]|わか[らり]|不明|かもしれ|と思う")
            texts = [query] + [item.get("answer", "") for item in clarifications]
            if any(confirmed.search(normalized(t)) and not uncertain.search(normalized(t)) for t in texts):
                return None
            for item in clarifications:
                q, a = normalized(item.get("question", "")), normalized(item.get("answer", ""))
                if (re.search(r"[2二]人", q) and re.search(r"運べ|持ち運", q)
                        and not uncertain.search(a)
                        and (re.match(r"^(?:はい|いいえ)(?:[、。!！]|$)", a)
                             or a.rstrip("。!") in {"運べます", "運べません", "持ち運べます", "持ち運べません"})):
                    return None
            return "1m程度で、標準的な大人2人で持ち運べる大きさ・重さですか？"
        if (primary != "" or not isinstance(options, list)
                or not all(isinstance(option, str) for option in options)
                or not {"bulky", "not_collected"}.issubset(options)
                or "大人1人" not in evidence
                or not re.search(r"持ち運べる|運べる|運搬できる", evidence)
                or not re.search(r"持ち運びできない|持ち運べない|運べない|運搬できない", evidence)):
            return None

        def normalize(value):
            return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value)))

        explicit = re.compile(r"(?:大人)?[1一]人(?:で(?:は|も)?|だけで)"
                              r"(?:持ち運(?:べ|びでき)|運(?:べ|搬でき)|持て)(?:ます|ません|る|ない)")
        uncertain = re.compile(r"か(?:どうか)?(?:は)?(?:分か[らり]|わか[らり]|不明)|かもしれ|と思う")
        texts = [query] + [item.get("answer", "") for item in clarifications]
        if any(explicit.search(normalize(text)) and not uncertain.search(normalize(text)) for text in texts):
            return None
        for item in clarifications:
            question, answer = normalize(item.get("question", "")), normalize(item.get("answer", ""))
            if re.search(r"分か[らり]|わか[らり]|不明|かもしれ|と思う", answer):
                continue
            if (re.search(r"[1一]人", question) and re.search(r"運べ|運搬|持ち運|持て", question)
                    and (re.match(r"^(?:はい|いいえ)(?:[、。!！]|$)", answer)
                         or answer.rstrip("。!") in {"運べます", "運べません", "持ち運べます", "持ち運べません"})):
                return None
        return "大人1人で持ち運べる重さ・大きさですか？"

    @classmethod
    def _conditional_evidence_question(
        cls,
        *,
        query: str,
        clarifications: list[dict],
        documents: list[RetrievedDocument],
        region: RegionContext | None = None,
        selected_evidence_indexes: tuple[int, ...] = (),
    ) -> str | None:
        """地域資料の分類分岐条件が未回答なら、確定前に一つ確認する。"""

        context = unicodedata.normalize(
            "NFKC",
            " ".join(
                [query]
                + [str(item.get("answer", "")) for item in clarifications]
            ),
        ).lower()
        structured = next((doc for doc in documents if doc.text.startswith("品目:")), None)
        if structured is None:
            return None
        selected = next((documents[index - 1] for index in selected_evidence_indexes
                         if 1 <= index <= len(documents)
                         and documents[index - 1].text.startswith("品目:")), structured)
        regional = region is not None and region.municipality_id != "38201"
        if regional:
            material_question = cls._exact_material_question(
                query=query, clarifications=clarifications, documents=documents,
            )
            if material_question:
                return material_question
            exact_matches = cls._matching_structured_documents(query=query, documents=documents)
            # Use an exact requested item when present; otherwise use the cited
            # item, never an unrelated leading cap candidate. Matsuyama retains
            # its existing first-candidate guard.
            structured = exact_matches[0][1] if exact_matches else selected
        lines = structured.text.splitlines()
        item_name = lines[0].removeprefix("品目:").strip()
        display_item = re.sub(r"[（(].*$", "", item_name).strip() or "品物"
        evidence = unicodedata.normalize("NFKC", structured.text)
        if regional:
            evidence = evidence.split("区分共通の出し方", 1)[0]

        # Explicit opt-in for municipalities with a dimensional boundary.
        # Search rewrites and image estimates never count as a measured size.
        threshold = getattr(region.rules, "size_threshold_cm", None) if region else None
        item_evidence = unicodedata.normalize("NFKC", selected.text).split(
            "区分共通の出し方", 1
        )[0]
        if (threshold and "条件付き分類コード:" in item_evidence
                and re.search(rf"{threshold}cm(?:以下|超)", item_evidence)):
            uncertain = re.compile(r"(?:cm|センチ).{0,12}(?:わから|分から|不明|かもしれ)")
            measured = bool(re.search(r"\d+(?:\.\d+)?\s*(?:cm|センチ)", context)) and not uncertain.search(context)
            measured = measured or any(
                re.search(rf"{threshold}\s*cm.*(?:以下|超)", unicodedata.normalize("NFKC", str(item.get("question", ""))).lower())
                and re.fullmatch(r"\s*(?:はい|いいえ)[。！!]?\s*", str(item.get("answer", "")))
                for item in clarifications
            )
            measured = measured or any(
                "cm" in unicodedata.normalize("NFKC", str(item.get("question", ""))).lower()
                and re.fullmatch(r"\s*\d+(?:\.\d+)?\s*", str(item.get("answer", "")))
                for item in clarifications
            )
            if not measured:
                return region.rules.size_question

        material_branches = (
            "金属製のものは",
            "金属・ガラス製のものは",
            "プラスチック製のものは",
            "木・プラスチック製",
            "紙製は",
            "紙製のものは",
            "木製なら",
            "木製は",
            "プラ製は",
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

        size_branch = any(
            marker in evidence
            for marker in (
                "袋に入らない",
                "袋に入らなければ",
                "袋に収まらない",
                "袋に収まらなければ",
                "袋に入れば",
            )
        )
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
        size_answered = any(answer in context for answer in size_answers)
        if region and region.municipality_id != "38201":
            size_answered = size_answered or any(
                re.search(r"袋.*入[るり]", str(item.get("question", "")))
                and re.fullmatch(r"\s*(?:はい|いいえ)[。！!]?\s*", str(item.get("answer", "")))
                for item in clarifications
            )
        if size_branch and not size_answered:
            return region.rules.size_question if region else "松山市の指定ごみ袋に入る大きさですか？"

        if "汚れが落ちない" in evidence and not any(
            marker in context
            for marker in (
                "汚れが落ちない",
                "汚れを落とせない",
                "汚れが取れない",
                "洗った",
                "すすいだ",
                "水洗いした",
                "水洗いしました",
                "水洗い済み",
                "汚れを取り除",
                "きれい",
            )
        ):
            return f"{display_item}の汚れは水ですすいで落とせますか？"

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

        # Some official tables split the same named item by quantity rather
        # than material or dimensions. The primary code in a conditional row
        # is not a default when the user did not state that quantity.
        encoded_options = next(
            (
                line.removeprefix("条件付き分類コード:").strip()
                for line in lines
                if line.startswith("条件付き分類コード:")
            ),
            "[]",
        )
        try:
            quantity_options = json.loads(encoded_options)
        except (ValueError, TypeError):
            quantity_options = []
        quantity_branch = (
            isinstance(quantity_options, list)
            and bool(quantity_options)
            and "少量" in evidence
            and any(marker in evidence for marker in ("多量", "量が多い", "大量"))
        )
        quantity_answered = any(
            marker in context
            for marker in ("少量", "少し", "わずか", "多量", "大量", "たくさん")
        )
        if quantity_branch and not quantity_answered:
            return f"{display_item}は少量ですか、それとも多量ですか？"

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
        except RegionalDataError as error:
            raise WasteGuideError(str(error)) from error

    @staticmethod
    def _build_answer(
        decision: ClassificationDecision, next_collection: CollectionDate | None,
        *, region: RegionContext | None = None, collection_status: CollectionStatus | None = None,
    ) -> str:
        names = region.category_names if region else CATEGORY_NAMES
        category_name = names[decision.category_code]
        lines = [f"{decision.item_name}は「{category_name}」です。"]
        if decision.disposal_instructions:
            lines.append(decision.disposal_instructions)
        if collection_status and collection_status.status == "unverified":
            lines.append(collection_status.message or "この区分の収集日は未確認です。")
        elif next_collection:
            lines.append(
                f"{region.area_name if region else '清水'}地区の次回収集日は{next_collection.display_date}です。"
            )
        elif region and region.rules.categories[decision.category_code].answer_note:
            lines.append(region.rules.categories[decision.category_code].answer_note)
        elif region is None and decision.category_code == "粗大":
            lines.append("粗大ごみは戸別収集の申し込みが必要です。")
        elif region is None and decision.category_code == "禁止":
            lines.append("松山市のごみ集積場所には出せません。")
        else:
            lines.append("公開済みカレンダーの範囲では次回収集日を確認できません。")
        if region and region.rules.categories[decision.category_code].time_note:
            lines.append(region.rules.categories[decision.category_code].time_note)
        return "\n".join(lines)
