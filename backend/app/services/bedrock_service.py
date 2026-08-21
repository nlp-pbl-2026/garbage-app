"""Bedrock Knowledge Base Agentic Retrieval サービス（同期実装）

boto3は同期SDKのため、全メソッドを同期関数として実装する。
FastAPIルーターからは asyncio.to_thread() で呼び出す。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .. import config

logger = logging.getLogger(__name__)


class BedrockServiceError(Exception):
    """Bedrock サービスレベルのエラー"""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


@dataclass
class RAGResult:
    """RAGクエリの結果"""

    answer: str
    sources: list[dict] = field(default_factory=list)


class BedrockRAGService:
    """Bedrock Knowledge Base Agentic Retrieval サービス（同期実装）"""

    def __init__(self, client=None):
        """boto3クライアントをDI可能にする（テスト容易性）

        clientが未指定の場合は bedrock-agent-runtime クライアントを生成する。
        """
        if client is not None:
            self._client = client
        else:
            self._client = boto3.client(
                "bedrock-agent-runtime",
                region_name=config.AWS_REGION,
            )

    def build_context_prompt(
        self,
        query: str,
        municipality_name: str | None,
        district_name: str | None,
    ) -> str:
        """動的コンテキストプロンプトを構築する（同期）

        日付、自治体、地区はすべて実行時に動的に設定する。
        ハードコードされた地区名・年度・自治体名を含まない。
        """
        tz = timezone(timedelta(hours=9))  # Asia/Tokyo = UTC+9
        now = datetime.now(tz)
        current_date = now.strftime("%Y年%m月%d日")

        lines: list[str] = []
        lines.append(f"現在の日付は日本時間で{current_date}です。")

        if municipality_name:
            lines.append(f"利用自治体は{municipality_name}です。")

        if district_name:
            lines.append(f"対象地区は{district_name}です。")

        lines.append(
            "以下の質問について、Knowledge Baseから取得した情報に基づいて回答してください。"
        )
        lines.append(
            "取得情報にない分別方法・注意事項・収集日を推測して追加しないでください。"
        )
        lines.append("")
        lines.append("質問:")
        lines.append(query)

        return "\n".join(lines)

    def extract_result(self, stream) -> RAGResult:
        """ストリームを消費し、最終resultイベントから回答とソースを抽出する（同期）

        実AWSレスポンス構造:
          result.generatedResponse.answer → 最終回答
          result.generatedResponse.citations[].references[].resultIndex → results配列のインデックス
          result.results[] → 各検索結果（content.text, metadata._source_uri, metadata.source_title 等）

        citations の references[].resultIndex を使って result.results[index] を参照し、
        metadata からURI/タイトルを取得する。
        """
        answer = ""
        sources: list[dict] = []

        for event in stream:
            # responseEvent: 将来のストリーミング表示用（今回はresultを正とする）
            if "responseEvent" in event:
                pass

            # result: 最終結果
            if "result" in event:
                result = event["result"]
                generated_response = result.get("generatedResponse", {})
                results_list = result.get("results", [])

                # 最終回答
                answer = generated_response.get("answer", "")

                # citations → references → resultIndex で results を参照
                citations = generated_response.get("citations", [])
                seen_uris: set[str] = set()

                for citation in citations:
                    references = citation.get("references", [])
                    for ref in references:
                        result_index = ref.get("resultIndex")
                        if result_index is not None and result_index < len(
                            results_list
                        ):
                            result_entry = results_list[result_index]
                            source = self._extract_source_from_result_entry(
                                result_entry
                            )
                            if source:
                                uri = source.get("uri", "")
                                if uri and uri not in seen_uris:
                                    seen_uris.add(uri)
                                    sources.append(source)
                                elif not uri:
                                    sources.append(source)

                    # フォールバック: retrievedReferences がある場合（旧形式互換）
                    retrieved_refs = citation.get("retrievedReferences", [])
                    for ref in retrieved_refs:
                        source = self._extract_source_from_retrieved_ref(ref)
                        if source:
                            uri = source.get("uri", "")
                            if uri and uri not in seen_uris:
                                seen_uris.add(uri)
                                sources.append(source)
                            elif not uri:
                                sources.append(source)

        return RAGResult(answer=answer, sources=sources)

    def _extract_source_from_result_entry(self, result_entry: dict) -> dict | None:
        """result.results[] の1エントリからRAGSource情報を抽出する

        実AWSレスポンスの result_entry 構造:
          content.text → snippet
          metadata._source_uri → URI
          metadata.source_title → title (優先)
          metadata._document_title → title (フォールバック)
        """
        metadata = result_entry.get("metadata", {})
        content = result_entry.get("content", {})

        uri = metadata.get("_source_uri", "")
        title = metadata.get("source_title") or metadata.get("_document_title") or ""
        snippet_text = content.get("text", "")

        if not uri and not title and not snippet_text:
            return None

        source: dict = {}
        if uri:
            source["uri"] = uri
        if title:
            source["title"] = title
        elif uri:
            source["title"] = uri.rsplit("/", 1)[-1]
        if snippet_text:
            if len(snippet_text) > 200:
                snippet_text = snippet_text[:200] + "..."
            source["snippet"] = snippet_text

        return source

    def _extract_source_from_retrieved_ref(self, ref: dict) -> dict | None:
        """retrievedReferences 形式（旧形式互換）からRAGSource情報を抽出する"""
        location = ref.get("location", {})
        content = ref.get("content", {})
        metadata = ref.get("metadata", {})

        s3_location = location.get("s3Location", {})
        uri = s3_location.get("uri", "")

        title = (
            metadata.get("source_title")
            or metadata.get("_document_title")
            or metadata.get("title")
            or ""
        )
        snippet_text = content.get("text", "")

        if not uri and not title and not snippet_text:
            return None

        source: dict = {}
        if uri:
            source["uri"] = uri
        if title:
            source["title"] = title
        elif uri:
            source["title"] = uri.rsplit("/", 1)[-1]
        if snippet_text:
            if len(snippet_text) > 200:
                snippet_text = snippet_text[:200] + "..."
            source["snippet"] = snippet_text

        return source

    def query(
        self,
        query: str,
        municipality_name: str | None = None,
        district_name: str | None = None,
    ) -> RAGResult:
        """Knowledge Baseにクエリを発行し回答を返す（同期）

        1. KNOWLEDGE_BASE_ID の設定確認
        2. build_context_prompt() でコンテキスト付きプロンプトを構築
        3. agentic_retrieve_stream() を呼び出し
        4. extract_result() で最終結果を抽出
        5. RAGResult を返す
        """
        # KNOWLEDGE_BASE_ID が未設定の場合はAWSへリクエストを送らない
        if not config.KNOWLEDGE_BASE_ID:
            logger.error(
                "KNOWLEDGE_BASE_ID is not configured. "
                "Set the KNOWLEDGE_BASE_ID environment variable."
            )
            raise BedrockServiceError(
                "AIサービスの設定が不完全です。管理者にお問い合わせください。"
            )

        context_prompt = self.build_context_prompt(
            query=query,
            municipality_name=municipality_name,
            district_name=district_name,
        )

        try:
            response = self._client.agentic_retrieve_stream(
                messages=[
                    {
                        "role": "user",
                        "content": {"text": context_prompt},
                    }
                ],
                retrievers=[
                    {
                        "description": "ゴミ出し情報のKnowledge Base",
                        "configuration": {
                            "knowledgeBase": {
                                "knowledgeBaseId": config.KNOWLEDGE_BASE_ID,
                            }
                        },
                    }
                ],
                agenticRetrieveConfiguration={
                    "foundationModelType": config.AGENTIC_FOUNDATION_MODEL_TYPE,
                    "maxAgentIteration": config.AGENTIC_MAX_ITERATIONS,
                },
                generateResponse=True,
            )
        except NoCredentialsError as e:
            raise BedrockServiceError(
                "AIサービスに接続できません。しばらくしてからお試しください。",
                original_error=e,
            )
        except ClientError as e:
            raise BedrockServiceError(
                "AIサービスでエラーが発生しました。しばらくしてからお試しください。",
                original_error=e,
            )
        except Exception as e:
            raise BedrockServiceError(
                "AIサービスでエラーが発生しました。しばらくしてからお試しください。",
                original_error=e,
            )

        # ストリームからresultを抽出
        try:
            stream = response.get("stream", [])
            result = self.extract_result(stream)
        except Exception as e:
            raise BedrockServiceError(
                "応答の処理中にエラーが発生しました。",
                original_error=e,
            )

        # 回答が空の場合
        if not result.answer.strip():
            result.answer = "回答が見つかりませんでした。質問を変えてお試しください。"

        return result
