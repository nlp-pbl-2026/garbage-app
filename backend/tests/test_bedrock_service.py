"""BedrockRAGService のユニットテスト

Property tests for context prompt construction, result extraction, and query validation.
"""

import re
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from botocore.exceptions import ClientError, NoCredentialsError

from app.services.bedrock_service import (
    BedrockRAGService,
    BedrockServiceError,
    RAGResult,
)


# =============================================================================
# Property 2: Context prompt includes municipality when provided
# =============================================================================


class TestContextPromptMunicipality:
    """Property 2: municipality_name が提供された場合、コンテキストプロンプトに含まれる"""

    @pytest.fixture
    def service(self):
        return BedrockRAGService(client=MagicMock())

    @pytest.mark.parametrize(
        "municipality_name",
        [
            "松山市",
            "今治市",
            "宇和島市",
            "八幡浜市",
            "新居浜市",
            "テスト自治体",
            "A" * 50,
        ],
    )
    def test_municipality_included_in_prompt(self, service, municipality_name):
        """municipality_nameが提供された場合、プロンプトに「利用自治体は{name}です。」が含まれる"""
        prompt = service.build_context_prompt(
            query="テスト質問",
            municipality_name=municipality_name,
            district_name=None,
        )
        expected = f"利用自治体は{municipality_name}です。"
        assert expected in prompt

    def test_municipality_omitted_when_none(self, service):
        """municipality_nameがNoneの場合、プロンプトに「利用自治体は」が含まれない"""
        prompt = service.build_context_prompt(
            query="テスト質問",
            municipality_name=None,
            district_name=None,
        )
        assert "利用自治体は" not in prompt

    def test_municipality_omitted_when_empty_string(self, service):
        """municipality_nameが空文字列の場合、プロンプトに「利用自治体は」が含まれない"""
        prompt = service.build_context_prompt(
            query="テスト質問",
            municipality_name="",
            district_name=None,
        )
        assert "利用自治体は" not in prompt


# =============================================================================
# Property 3: Context prompt excludes district when not provided
# =============================================================================


class TestContextPromptDistrictExclusion:
    """Property 3: district_name が提供されない場合、コンテキストプロンプトに含まれない"""

    @pytest.fixture
    def service(self):
        return BedrockRAGService(client=MagicMock())

    def test_district_excluded_when_none(self, service):
        """district_nameがNoneの場合、プロンプトに「対象地区は」が含まれない"""
        prompt = service.build_context_prompt(
            query="テスト質問",
            municipality_name="松山市",
            district_name=None,
        )
        assert "対象地区は" not in prompt

    def test_district_excluded_when_empty_string(self, service):
        """district_nameが空文字列の場合、プロンプトに「対象地区は」が含まれない"""
        prompt = service.build_context_prompt(
            query="テスト質問",
            municipality_name="松山市",
            district_name="",
        )
        assert "対象地区は" not in prompt


# =============================================================================
# Property 4: Context prompt includes district when provided
# =============================================================================


class TestContextPromptDistrictInclusion:
    """Property 4: district_name が提供された場合、コンテキストプロンプトに含まれる"""

    @pytest.fixture
    def service(self):
        return BedrockRAGService(client=MagicMock())

    @pytest.mark.parametrize(
        "district_name",
        [
            "清水",
            "番町",
            "東雲",
            "道後",
            "桑原",
            "テスト地区",
        ],
    )
    def test_district_included_in_prompt(self, service, district_name):
        """district_nameが提供された場合、プロンプトに「対象地区は{name}です。」が含まれる"""
        prompt = service.build_context_prompt(
            query="テスト質問",
            municipality_name="松山市",
            district_name=district_name,
        )
        expected = f"対象地区は{district_name}です。"
        assert expected in prompt


# =============================================================================
# Property 9: Context prompt includes anti-hallucination instruction
# =============================================================================


class TestContextPromptAntiHallucination:
    """Property 9: コンテキストプロンプトに情報捏造防止の指示が含まれる"""

    @pytest.fixture
    def service(self):
        return BedrockRAGService(client=MagicMock())

    @pytest.mark.parametrize(
        "municipality_name,district_name",
        [
            (None, None),
            ("松山市", None),
            (None, "清水"),
            ("松山市", "清水"),
        ],
    )
    def test_anti_hallucination_instruction_always_present(
        self, service, municipality_name, district_name
    ):
        """地域パラメータに関わらず、情報捏造防止の指示が含まれる"""
        prompt = service.build_context_prompt(
            query="テスト質問",
            municipality_name=municipality_name,
            district_name=district_name,
        )
        assert (
            "取得情報にない分別方法・注意事項・収集日を推測して追加しないでください。"
            in prompt
        )


# =============================================================================
# Context prompt: date is dynamically generated in Japan timezone
# =============================================================================


class TestContextPromptDate:
    """コンテキストプロンプトに日本時間の現在日付が含まれる"""

    @pytest.fixture
    def service(self):
        return BedrockRAGService(client=MagicMock())

    def test_current_date_in_prompt(self, service):
        """プロンプトに現在の日付がYYYY年MM月DD日形式で含まれる"""
        prompt = service.build_context_prompt(
            query="テスト質問",
            municipality_name=None,
            district_name=None,
        )
        pattern = r"現在の日付は日本時間で\d{4}年\d{2}月\d{2}日です。"
        assert re.search(pattern, prompt) is not None

    def test_date_is_japan_timezone(self, service):
        """日付が日本時間（UTC+9）で生成される"""
        fixed_dt = datetime(2026, 8, 21, 10, 30, 0, tzinfo=timezone(timedelta(hours=9)))

        with patch("app.services.bedrock_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = fixed_dt
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs
            )

            prompt = service.build_context_prompt(
                query="テスト質問",
                municipality_name=None,
                district_name=None,
            )

        assert "2026年08月21日" in prompt

    def test_query_included_in_prompt(self, service):
        """ユーザーのクエリがプロンプト末尾に含まれる"""
        query_text = "プラスチック製の植木鉢はどのゴミですか？"
        prompt = service.build_context_prompt(
            query=query_text,
            municipality_name=None,
            district_name=None,
        )
        assert query_text in prompt
        assert prompt.endswith(query_text)


# =============================================================================
# Property 5: Result answer is extracted from generatedResponse
# =============================================================================


class TestExtractResultAnswer:
    """Property 5: result.generatedResponse.answer から最終回答が正しく抽出される"""

    @pytest.fixture
    def service(self):
        return BedrockRAGService(client=MagicMock())

    @pytest.mark.parametrize(
        "answer_text",
        [
            "プラスチック製の植木鉢は可燃ごみです。",
            "次回の収集日は2026年8月25日（月）です。",
            "短い回答",
            "改行を\n含む\n回答テスト",
            "A" * 500,
        ],
    )
    def test_answer_extracted_from_generated_response(self, service, answer_text):
        """result.generatedResponse.answer のテキストがそのまま返される"""
        stream = [
            {
                "result": {
                    "generatedResponse": {
                        "answer": answer_text,
                        "citations": [],
                    },
                    "results": [],
                }
            }
        ]
        result = service.extract_result(iter(stream))
        assert result.answer == answer_text

    def test_empty_answer_returns_empty_string(self, service):
        """generatedResponse.answer が空の場合は空文字列が返る"""
        stream = [
            {
                "result": {
                    "generatedResponse": {
                        "answer": "",
                        "citations": [],
                    },
                    "results": [],
                }
            }
        ]
        result = service.extract_result(iter(stream))
        assert result.answer == ""

    def test_missing_generated_response_returns_empty(self, service):
        """generatedResponse がない場合は空文字列が返る"""
        stream = [
            {
                "result": {
                    "results": [],
                }
            }
        ]
        result = service.extract_result(iter(stream))
        assert result.answer == ""

    def test_response_events_ignored_for_answer(self, service):
        """responseEvent は最終回答に使用されず、result を正とする"""
        stream = [
            {"responseEvent": {"text": "途中のテキスト1"}},
            {"responseEvent": {"text": "途中のテキスト2"}},
            {
                "result": {
                    "generatedResponse": {
                        "answer": "最終回答テキスト",
                        "citations": [],
                    },
                    "results": [],
                }
            },
        ]
        result = service.extract_result(iter(stream))
        assert result.answer == "最終回答テキスト"
        assert "途中のテキスト" not in result.answer


# =============================================================================
# Property 8: Source citations extracted from result event (actual AWS format)
# =============================================================================


class TestExtractResultSources:
    """Property 8: 実AWSレスポンス形式で citations/results からソース情報が正しく抽出される"""

    @pytest.fixture
    def service(self):
        return BedrockRAGService(client=MagicMock())

    def test_sources_extracted_via_result_index(self, service):
        """citations.references[].resultIndex を使って results[] からソースを抽出する"""
        stream = [
            {
                "result": {
                    "generatedResponse": {
                        "answer": "回答テスト",
                        "citations": [
                            {
                                "references": [
                                    {"resultIndex": 0},
                                    {"resultIndex": 1},
                                ]
                            }
                        ],
                    },
                    "results": [
                        {
                            "content": {"text": "ゴミ品目データのスニペット"},
                            "metadata": {
                                "_source_uri": "s3://bucket/garbage_items.csv",
                                "source_title": "ゴミ品目一覧",
                            },
                            "sourceRetriever": "kb1",
                        },
                        {
                            "content": {"text": "分別ルールのスニペット"},
                            "metadata": {
                                "_source_uri": "s3://bucket/rules.csv",
                                "_document_title": "分別ルール",
                            },
                            "sourceRetriever": "kb1",
                        },
                    ],
                }
            }
        ]
        result = service.extract_result(iter(stream))
        assert len(result.sources) == 2
        assert result.sources[0]["uri"] == "s3://bucket/garbage_items.csv"
        assert result.sources[0]["title"] == "ゴミ品目一覧"
        assert "ゴミ品目データ" in result.sources[0]["snippet"]
        assert result.sources[1]["uri"] == "s3://bucket/rules.csv"
        assert result.sources[1]["title"] == "分別ルール"

    def test_source_title_fallback_to_document_title(self, service):
        """source_title がない場合は _document_title を使用する"""
        stream = [
            {
                "result": {
                    "generatedResponse": {
                        "answer": "回答",
                        "citations": [{"references": [{"resultIndex": 0}]}],
                    },
                    "results": [
                        {
                            "content": {"text": "テキスト"},
                            "metadata": {
                                "_source_uri": "s3://bucket/file.csv",
                                "_document_title": "ドキュメントタイトル",
                            },
                        },
                    ],
                }
            }
        ]
        result = service.extract_result(iter(stream))
        assert result.sources[0]["title"] == "ドキュメントタイトル"

    def test_source_title_fallback_to_filename(self, service):
        """source_title も _document_title もない場合はURIからファイル名を取得"""
        stream = [
            {
                "result": {
                    "generatedResponse": {
                        "answer": "回答",
                        "citations": [{"references": [{"resultIndex": 0}]}],
                    },
                    "results": [
                        {
                            "content": {"text": "テキスト"},
                            "metadata": {
                                "_source_uri": "s3://bucket/path/to/data.csv",
                            },
                        },
                    ],
                }
            }
        ]
        result = service.extract_result(iter(stream))
        assert result.sources[0]["title"] == "data.csv"

    def test_duplicate_sources_deduplicated(self, service):
        """同じURIが複数citationから参照される場合は重複排除される"""
        stream = [
            {
                "result": {
                    "generatedResponse": {
                        "answer": "回答",
                        "citations": [
                            {"references": [{"resultIndex": 0}]},
                            {"references": [{"resultIndex": 0}]},
                        ],
                    },
                    "results": [
                        {
                            "content": {"text": "テキスト"},
                            "metadata": {
                                "_source_uri": "s3://bucket/same.csv",
                                "source_title": "同じソース",
                            },
                        },
                    ],
                }
            }
        ]
        result = service.extract_result(iter(stream))
        assert len(result.sources) == 1

    def test_snippet_truncated_to_200_chars(self, service):
        """snippet が200文字を超える場合は切り詰められる"""
        long_text = "あ" * 300
        stream = [
            {
                "result": {
                    "generatedResponse": {
                        "answer": "回答",
                        "citations": [{"references": [{"resultIndex": 0}]}],
                    },
                    "results": [
                        {
                            "content": {"text": long_text},
                            "metadata": {
                                "_source_uri": "s3://bucket/file.csv",
                            },
                        },
                    ],
                }
            }
        ]
        result = service.extract_result(iter(stream))
        assert result.sources[0]["snippet"].endswith("...")
        assert len(result.sources[0]["snippet"]) == 203  # 200 + "..."

    def test_empty_citations_returns_empty_sources(self, service):
        """citations が空の場合はsourcesも空"""
        stream = [
            {
                "result": {
                    "generatedResponse": {
                        "answer": "回答テスト",
                        "citations": [],
                    },
                    "results": [],
                }
            }
        ]
        result = service.extract_result(iter(stream))
        assert result.sources == []

    def test_retrieved_references_fallback(self, service):
        """旧形式 retrievedReferences がある場合もソースを抽出する"""
        stream = [
            {
                "result": {
                    "generatedResponse": {
                        "answer": "回答",
                        "citations": [
                            {
                                "retrievedReferences": [
                                    {
                                        "location": {
                                            "s3Location": {
                                                "uri": "s3://bucket/old_format.json"
                                            }
                                        },
                                        "content": {"text": "旧形式テキスト"},
                                        "metadata": {"source_title": "旧形式タイトル"},
                                    }
                                ]
                            }
                        ],
                    },
                    "results": [],
                }
            }
        ]
        result = service.extract_result(iter(stream))
        assert len(result.sources) == 1
        assert result.sources[0]["uri"] == "s3://bucket/old_format.json"
        assert result.sources[0]["title"] == "旧形式タイトル"

    def test_multiple_citations_multiple_results(self, service):
        """複数citationが異なるresultIndexを参照する場合"""
        stream = [
            {
                "result": {
                    "generatedResponse": {
                        "answer": "回答",
                        "citations": [
                            {"references": [{"resultIndex": 0}]},
                            {"references": [{"resultIndex": 2}]},
                        ],
                    },
                    "results": [
                        {
                            "content": {"text": "テキスト0"},
                            "metadata": {
                                "_source_uri": "s3://bucket/r0.csv",
                                "source_title": "R0",
                            },
                        },
                        {
                            "content": {"text": "テキスト1"},
                            "metadata": {
                                "_source_uri": "s3://bucket/r1.csv",
                                "source_title": "R1",
                            },
                        },
                        {
                            "content": {"text": "テキスト2"},
                            "metadata": {
                                "_source_uri": "s3://bucket/r2.csv",
                                "source_title": "R2",
                            },
                        },
                    ],
                }
            }
        ]
        result = service.extract_result(iter(stream))
        assert len(result.sources) == 2
        uris = [s["uri"] for s in result.sources]
        assert "s3://bucket/r0.csv" in uris
        assert "s3://bucket/r2.csv" in uris
        # r1 は citation から参照されないので含まれない
        assert "s3://bucket/r1.csv" not in uris


# =============================================================================
# Property 1: Whitespace-only queries are rejected (schema validation)
# =============================================================================


class TestWhitespaceQueryValidation:
    """Property 1: 空白のみのクエリはバリデーションエラーになる"""

    @pytest.mark.parametrize(
        "whitespace_query",
        [
            " ",
            "  ",
            "\t",
            "\n",
            "\r\n",
            "   \t  \n  ",
            "\t\t\t",
        ],
    )
    def test_whitespace_only_rejected(self, whitespace_query):
        """空白文字のみのクエリはバリデーションで拒否される"""
        from app.schemas import RAGQueryRequest

        with pytest.raises(Exception):
            RAGQueryRequest(query=whitespace_query)

    def test_empty_string_rejected(self):
        """空文字列のクエリはバリデーションで拒否される"""
        from app.schemas import RAGQueryRequest

        with pytest.raises(Exception):
            RAGQueryRequest(query="")

    @pytest.mark.parametrize(
        "valid_query",
        [
            "テスト",
            " テスト ",
            "a",
            "プラスチック製の植木鉢は何ゴミ？",
        ],
    )
    def test_valid_queries_accepted(self, valid_query):
        """有効なクエリはバリデーションを通過する"""
        from app.schemas import RAGQueryRequest

        req = RAGQueryRequest(query=valid_query)
        assert req.query == valid_query


# =============================================================================
# KNOWLEDGE_BASE_ID 未設定時のエラー検出
# =============================================================================


class TestKnowledgeBaseIdValidation:
    """KNOWLEDGE_BASE_IDが未設定の場合、AWSへリクエストを送らずエラーを返す"""

    def test_empty_kb_id_raises_service_error(self):
        """KNOWLEDGE_BASE_ID が空文字の場合に BedrockServiceError が発生する"""
        mock_client = MagicMock()
        service = BedrockRAGService(client=mock_client)

        with patch("app.services.bedrock_service.config") as mock_config:
            mock_config.KNOWLEDGE_BASE_ID = ""
            mock_config.AWS_REGION = "ap-northeast-1"
            mock_config.TIMEZONE = "Asia/Tokyo"
            mock_config.AGENTIC_MAX_ITERATIONS = 5
            mock_config.AGENTIC_FOUNDATION_MODEL_TYPE = "MANAGED"

            with pytest.raises(BedrockServiceError) as exc_info:
                service.query(query="テスト質問")

        assert "設定が不完全" in str(exc_info.value)
        # AWSへのリクエストが送信されないことを確認
        mock_client.agentic_retrieve_stream.assert_not_called()

    def test_none_kb_id_raises_service_error(self):
        """KNOWLEDGE_BASE_ID が None (falsy) の場合に BedrockServiceError が発生する"""
        mock_client = MagicMock()
        service = BedrockRAGService(client=mock_client)

        with patch("app.services.bedrock_service.config") as mock_config:
            mock_config.KNOWLEDGE_BASE_ID = None
            mock_config.AWS_REGION = "ap-northeast-1"
            mock_config.TIMEZONE = "Asia/Tokyo"
            mock_config.AGENTIC_MAX_ITERATIONS = 5
            mock_config.AGENTIC_FOUNDATION_MODEL_TYPE = "MANAGED"

            with pytest.raises(BedrockServiceError) as exc_info:
                service.query(query="テスト質問")

        assert "設定が不完全" in str(exc_info.value)
        mock_client.agentic_retrieve_stream.assert_not_called()

    def test_error_message_does_not_expose_internal_details(self):
        """エラーメッセージにKB IDやAWS内部情報が含まれない"""
        mock_client = MagicMock()
        service = BedrockRAGService(client=mock_client)

        with patch("app.services.bedrock_service.config") as mock_config:
            mock_config.KNOWLEDGE_BASE_ID = ""
            mock_config.AWS_REGION = "ap-northeast-1"
            mock_config.TIMEZONE = "Asia/Tokyo"
            mock_config.AGENTIC_MAX_ITERATIONS = 5
            mock_config.AGENTIC_FOUNDATION_MODEL_TYPE = "MANAGED"

            with pytest.raises(BedrockServiceError) as exc_info:
                service.query(query="テスト質問")

        error_msg = str(exc_info.value)
        assert "KNOWLEDGE_BASE_ID" not in error_msg
        assert "O5UJSVXWU4" not in error_msg
        assert "aws" not in error_msg.lower() or "ai" in error_msg.lower()


# =============================================================================
# Bedrock service query() integration tests (with mocked boto3)
# =============================================================================


class TestBedrockServiceQuery:
    """BedrockRAGService.query() の統合テスト（boto3モック使用）"""

    def _make_mock_client(self, stream_events):
        """モックboto3クライアントを作成する"""
        mock_client = MagicMock()
        mock_client.agentic_retrieve_stream.return_value = {
            "stream": iter(stream_events)
        }
        return mock_client

    def test_successful_query(self):
        """正常なクエリが回答を返す"""
        stream_events = [
            {
                "result": {
                    "generatedResponse": {
                        "answer": "プラスチック製の植木鉢は可燃ごみです。",
                        "citations": [],
                    },
                    "results": [],
                }
            }
        ]
        mock_client = self._make_mock_client(stream_events)
        service = BedrockRAGService(client=mock_client)

        with patch("app.services.bedrock_service.config") as mock_config:
            mock_config.KNOWLEDGE_BASE_ID = "O5UJSVXWU4"
            mock_config.AWS_REGION = "ap-northeast-1"
            mock_config.TIMEZONE = "Asia/Tokyo"
            mock_config.AGENTIC_MAX_ITERATIONS = 5
            mock_config.AGENTIC_FOUNDATION_MODEL_TYPE = "MANAGED"

            result = service.query(
                query="プラスチック製の植木鉢は何ゴミ？",
                municipality_name="松山市",
                district_name="清水",
            )

        assert result.answer == "プラスチック製の植木鉢は可燃ごみです。"
        assert isinstance(result, RAGResult)

    def test_successful_query_with_sources(self):
        """正常なクエリがソース付きの回答を返す（実AWSレスポンス形式）"""
        stream_events = [
            {
                "result": {
                    "generatedResponse": {
                        "answer": "プラスチック製の植木鉢は可燃ごみです。",
                        "citations": [{"references": [{"resultIndex": 0}]}],
                    },
                    "results": [
                        {
                            "content": {"text": "植木鉢（プラスチック製）→ 可燃ごみ"},
                            "metadata": {
                                "_source_uri": "s3://bucket/garbage_items.csv",
                                "source_title": "ゴミ品目一覧",
                            },
                            "sourceRetriever": "kb-retriever",
                        },
                    ],
                }
            }
        ]
        mock_client = self._make_mock_client(stream_events)
        service = BedrockRAGService(client=mock_client)

        with patch("app.services.bedrock_service.config") as mock_config:
            mock_config.KNOWLEDGE_BASE_ID = "O5UJSVXWU4"
            mock_config.AWS_REGION = "ap-northeast-1"
            mock_config.TIMEZONE = "Asia/Tokyo"
            mock_config.AGENTIC_MAX_ITERATIONS = 5
            mock_config.AGENTIC_FOUNDATION_MODEL_TYPE = "MANAGED"

            result = service.query(query="植木鉢は何ゴミ？", municipality_name="松山市")

        assert len(result.sources) == 1
        assert result.sources[0]["title"] == "ゴミ品目一覧"
        assert result.sources[0]["uri"] == "s3://bucket/garbage_items.csv"

    def test_query_calls_agentic_retrieve_stream_with_correct_params(self):
        """query() が正しいパラメータで agentic_retrieve_stream を呼び出す"""
        stream_events = [
            {
                "result": {
                    "generatedResponse": {"answer": "回答", "citations": []},
                    "results": [],
                }
            }
        ]
        mock_client = self._make_mock_client(stream_events)
        service = BedrockRAGService(client=mock_client)

        with patch("app.services.bedrock_service.config") as mock_config:
            mock_config.KNOWLEDGE_BASE_ID = "O5UJSVXWU4"
            mock_config.AWS_REGION = "ap-northeast-1"
            mock_config.TIMEZONE = "Asia/Tokyo"
            mock_config.AGENTIC_MAX_ITERATIONS = 5
            mock_config.AGENTIC_FOUNDATION_MODEL_TYPE = "MANAGED"

            service.query(
                query="テスト質問", municipality_name="松山市", district_name=None
            )

        mock_client.agentic_retrieve_stream.assert_called_once()
        call_kwargs = mock_client.agentic_retrieve_stream.call_args[1]

        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"
        assert "テスト質問" in call_kwargs["messages"][0]["content"]["text"]

        assert len(call_kwargs["retrievers"]) == 1
        kb_config = call_kwargs["retrievers"][0]["configuration"]["knowledgeBase"]
        assert kb_config["knowledgeBaseId"] == "O5UJSVXWU4"

        agentic_config = call_kwargs["agenticRetrieveConfiguration"]
        assert agentic_config["foundationModelType"] == "MANAGED"
        assert agentic_config["maxAgentIteration"] == 5

        assert call_kwargs["generateResponse"] is True

    def test_query_with_no_credentials_raises_service_error(self):
        """AWS認証エラー時に BedrockServiceError が発生する"""
        mock_client = MagicMock()
        mock_client.agentic_retrieve_stream.side_effect = NoCredentialsError()
        service = BedrockRAGService(client=mock_client)

        with patch("app.services.bedrock_service.config") as mock_config:
            mock_config.KNOWLEDGE_BASE_ID = "O5UJSVXWU4"
            mock_config.AWS_REGION = "ap-northeast-1"
            mock_config.TIMEZONE = "Asia/Tokyo"
            mock_config.AGENTIC_MAX_ITERATIONS = 5
            mock_config.AGENTIC_FOUNDATION_MODEL_TYPE = "MANAGED"

            with pytest.raises(BedrockServiceError) as exc_info:
                service.query(query="テスト質問")

        assert "接続できません" in str(exc_info.value)

    def test_query_with_client_error_raises_service_error(self):
        """Bedrock APIエラー時に BedrockServiceError が発生する"""
        mock_client = MagicMock()
        mock_client.agentic_retrieve_stream.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal Error"}},
            "AgenticRetrieveStream",
        )
        service = BedrockRAGService(client=mock_client)

        with patch("app.services.bedrock_service.config") as mock_config:
            mock_config.KNOWLEDGE_BASE_ID = "O5UJSVXWU4"
            mock_config.AWS_REGION = "ap-northeast-1"
            mock_config.TIMEZONE = "Asia/Tokyo"
            mock_config.AGENTIC_MAX_ITERATIONS = 5
            mock_config.AGENTIC_FOUNDATION_MODEL_TYPE = "MANAGED"

            with pytest.raises(BedrockServiceError) as exc_info:
                service.query(query="テスト質問")

        assert "エラーが発生しました" in str(exc_info.value)

    def test_query_with_empty_answer_returns_fallback_message(self):
        """回答が空の場合はフォールバックメッセージが返る"""
        stream_events = [
            {
                "result": {
                    "generatedResponse": {"answer": "", "citations": []},
                    "results": [],
                }
            }
        ]
        mock_client = self._make_mock_client(stream_events)
        service = BedrockRAGService(client=mock_client)

        with patch("app.services.bedrock_service.config") as mock_config:
            mock_config.KNOWLEDGE_BASE_ID = "O5UJSVXWU4"
            mock_config.AWS_REGION = "ap-northeast-1"
            mock_config.TIMEZONE = "Asia/Tokyo"
            mock_config.AGENTIC_MAX_ITERATIONS = 5
            mock_config.AGENTIC_FOUNDATION_MODEL_TYPE = "MANAGED"

            result = service.query(query="テスト質問")

        assert "回答が見つかりませんでした" in result.answer

    def test_query_with_stream_processing_error(self):
        """ストリーム処理中のエラーで BedrockServiceError が発生する"""
        mock_client = MagicMock()

        def raise_during_iteration():
            yield {"responseEvent": {"text": "部分テキスト"}}
            raise RuntimeError("Stream interrupted")

        mock_client.agentic_retrieve_stream.return_value = {
            "stream": raise_during_iteration()
        }
        service = BedrockRAGService(client=mock_client)

        with patch("app.services.bedrock_service.config") as mock_config:
            mock_config.KNOWLEDGE_BASE_ID = "O5UJSVXWU4"
            mock_config.AWS_REGION = "ap-northeast-1"
            mock_config.TIMEZONE = "Asia/Tokyo"
            mock_config.AGENTIC_MAX_ITERATIONS = 5
            mock_config.AGENTIC_FOUNDATION_MODEL_TYPE = "MANAGED"

            with pytest.raises(BedrockServiceError) as exc_info:
                service.query(query="テスト質問")

        assert "処理中にエラー" in str(exc_info.value)

    def test_query_dynamic_district_in_context(self):
        """地区が動的にコンテキストに反映される"""
        stream_events = [
            {
                "result": {
                    "generatedResponse": {"answer": "回答", "citations": []},
                    "results": [],
                }
            }
        ]
        mock_client = self._make_mock_client(stream_events)
        service = BedrockRAGService(client=mock_client)

        with patch("app.services.bedrock_service.config") as mock_config:
            mock_config.KNOWLEDGE_BASE_ID = "O5UJSVXWU4"
            mock_config.AWS_REGION = "ap-northeast-1"
            mock_config.TIMEZONE = "Asia/Tokyo"
            mock_config.AGENTIC_MAX_ITERATIONS = 5
            mock_config.AGENTIC_FOUNDATION_MODEL_TYPE = "MANAGED"

            service.query(
                query="テスト", municipality_name="松山市", district_name="番町"
            )

        call_kwargs = mock_client.agentic_retrieve_stream.call_args[1]
        prompt = call_kwargs["messages"][0]["content"]["text"]
        assert "対象地区は番町です。" in prompt
        assert "利用自治体は松山市です。" in prompt

    def test_query_without_district_omits_district_context(self):
        """地区未指定時にはコンテキストに地区情報が含まれない"""
        stream_events = [
            {
                "result": {
                    "generatedResponse": {"answer": "回答", "citations": []},
                    "results": [],
                }
            }
        ]
        mock_client = self._make_mock_client(stream_events)
        service = BedrockRAGService(client=mock_client)

        with patch("app.services.bedrock_service.config") as mock_config:
            mock_config.KNOWLEDGE_BASE_ID = "O5UJSVXWU4"
            mock_config.AWS_REGION = "ap-northeast-1"
            mock_config.TIMEZONE = "Asia/Tokyo"
            mock_config.AGENTIC_MAX_ITERATIONS = 5
            mock_config.AGENTIC_FOUNDATION_MODEL_TYPE = "MANAGED"

            service.query(query="テスト", municipality_name=None, district_name=None)

        call_kwargs = mock_client.agentic_retrieve_stream.call_args[1]
        prompt = call_kwargs["messages"][0]["content"]["text"]
        assert "対象地区は" not in prompt
        assert "利用自治体は" not in prompt

    def test_config_knowledge_base_id_used(self):
        """環境変数から取得されたKNOWLEDGE_BASE_IDが使用される"""
        stream_events = [
            {
                "result": {
                    "generatedResponse": {"answer": "回答", "citations": []},
                    "results": [],
                }
            }
        ]
        mock_client = self._make_mock_client(stream_events)
        service = BedrockRAGService(client=mock_client)

        with patch("app.services.bedrock_service.config") as mock_config:
            mock_config.KNOWLEDGE_BASE_ID = "CUSTOM_KB_ID_123"
            mock_config.AWS_REGION = "ap-northeast-1"
            mock_config.TIMEZONE = "Asia/Tokyo"
            mock_config.AGENTIC_MAX_ITERATIONS = 10
            mock_config.AGENTIC_FOUNDATION_MODEL_TYPE = "MANAGED"

            service.query(query="テスト")

        call_kwargs = mock_client.agentic_retrieve_stream.call_args[1]
        kb_id = call_kwargs["retrievers"][0]["configuration"]["knowledgeBase"][
            "knowledgeBaseId"
        ]
        assert kb_id == "CUSTOM_KB_ID_123"

        agentic_config = call_kwargs["agenticRetrieveConfiguration"]
        assert agentic_config["maxAgentIteration"] == 10
