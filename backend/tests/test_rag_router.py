"""RAG Router のユニットテスト

POST /api/rag/query エンドポイントのテスト。
BedrockRAGService をモックして router のみを検証する。
"""

import asyncio
import time
from unittest.mock import patch, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.bedrock_service import BedrockServiceError, RAGResult


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
class TestRagRouterSuccess:
    """正常系テスト"""

    async def test_successful_query_returns_200(self):
        """正常なクエリが200とanswer/sourcesを返す"""
        mock_result = RAGResult(
            answer="プラスチック製の植木鉢は可燃ごみです。",
            sources=[
                {
                    "title": "ゴミ品目一覧",
                    "uri": "s3://bucket/garbage_items.csv",
                    "snippet": "植木鉢は可燃ごみ",
                }
            ],
        )

        with patch("app.routers.rag_router.BedrockRAGService") as MockService:
            mock_instance = MagicMock()
            mock_instance.query.return_value = mock_result
            MockService.return_value = mock_instance

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/rag/query",
                    json={
                        "query": "プラスチック製の植木鉢は何ゴミ？",
                        "municipality_name": "松山市",
                        "district_name": "清水",
                    },
                )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "プラスチック製の植木鉢は可燃ごみです。"
        assert len(data["sources"]) == 1
        assert data["sources"][0]["title"] == "ゴミ品目一覧"
        assert data["sources"][0]["uri"] == "s3://bucket/garbage_items.csv"

    async def test_query_without_region_returns_200(self):
        """地域情報なしのクエリも正常に処理される"""
        mock_result = RAGResult(answer="一般的な回答です。", sources=[])

        with patch("app.routers.rag_router.BedrockRAGService") as MockService:
            mock_instance = MagicMock()
            mock_instance.query.return_value = mock_result
            MockService.return_value = mock_instance

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/rag/query",
                    json={"query": "テスト質問"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "一般的な回答です。"
        assert data["sources"] == []

    async def test_no_auth_required(self):
        """認証トークンなしでリクエストが成功する"""
        mock_result = RAGResult(answer="回答テスト", sources=[])

        with patch("app.routers.rag_router.BedrockRAGService") as MockService:
            mock_instance = MagicMock()
            mock_instance.query.return_value = mock_result
            MockService.return_value = mock_instance

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/rag/query",
                    json={"query": "テスト"},
                )

        assert response.status_code == 200


@pytest.mark.asyncio
class TestRagRouterValidation:
    """バリデーションテスト"""

    async def test_empty_query_returns_422(self):
        """空のクエリが422を返す"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/rag/query",
                json={"query": ""},
            )

        assert response.status_code == 422

    async def test_whitespace_only_query_returns_422(self):
        """空白のみのクエリが422を返す"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/rag/query",
                json={"query": "   \t\n  "},
            )

        assert response.status_code == 422

    async def test_missing_query_field_returns_422(self):
        """queryフィールドがないリクエストが422を返す"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/rag/query",
                json={"municipality_name": "松山市"},
            )

        assert response.status_code == 422


@pytest.mark.asyncio
class TestRagRouterErrors:
    """エラーハンドリングテスト"""

    async def test_bedrock_service_error_returns_503(self):
        """BedrockServiceError が 503 を返す"""
        with patch("app.routers.rag_router.BedrockRAGService") as MockService:
            mock_instance = MagicMock()
            mock_instance.query.side_effect = BedrockServiceError(
                "AIサービスに接続できません。しばらくしてからお試しください。"
            )
            MockService.return_value = mock_instance

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/rag/query",
                    json={"query": "テスト質問"},
                )

        assert response.status_code == 503
        data = response.json()
        assert "接続できません" in data["detail"]

    async def test_timeout_error_returns_504(self):
        """タイムアウトが 504 を返す"""
        with patch("app.routers.rag_router.BedrockRAGService") as MockService:
            mock_instance = MagicMock()
            # asyncio.wait_for のタイムアウトをシミュレート：
            # service.query が長時間ブロックする（実際は wait_for がキャンセルする）
            mock_instance.query.side_effect = TimeoutError("Timeout")
            MockService.return_value = mock_instance

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/rag/query",
                    json={"query": "テスト質問"},
                )

        assert response.status_code == 504
        data = response.json()
        assert "タイムアウト" in data["detail"]

    async def test_actual_timeout_via_wait_for(self):
        """asyncio.wait_for の実際のタイムアウトが504を返す"""
        with patch("app.routers.rag_router.BedrockRAGService") as MockService:
            mock_instance = MagicMock()

            def slow_query(**kwargs):
                time.sleep(5)  # wait_for のタイムアウトより長い
                return RAGResult(answer="遅い回答", sources=[])

            mock_instance.query.side_effect = slow_query
            MockService.return_value = mock_instance

            # タイムアウトを非常に短く設定
            with patch("app.routers.rag_router.config") as mock_config:
                mock_config.RAG_REQUEST_TIMEOUT_SECONDS = 0.1

                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/rag/query",
                        json={"query": "テスト質問"},
                    )

        assert response.status_code == 504
        data = response.json()
        assert "タイムアウト" in data["detail"]

    async def test_unexpected_error_returns_503(self):
        """予期しないエラーが 503 を返す"""
        with patch("app.routers.rag_router.BedrockRAGService") as MockService:
            mock_instance = MagicMock()
            mock_instance.query.side_effect = RuntimeError("Unexpected")
            MockService.return_value = mock_instance

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/rag/query",
                    json={"query": "テスト質問"},
                )

        assert response.status_code == 503

    async def test_kb_id_not_configured_returns_503(self):
        """KNOWLEDGE_BASE_ID 未設定時に 503 を返す"""
        with patch("app.routers.rag_router.BedrockRAGService") as MockService:
            mock_instance = MagicMock()
            mock_instance.query.side_effect = BedrockServiceError(
                "AIサービスの設定が不完全です。管理者にお問い合わせください。"
            )
            MockService.return_value = mock_instance

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/rag/query",
                    json={"query": "テスト質問"},
                )

        assert response.status_code == 503
        data = response.json()
        assert "設定が不完全" in data["detail"]
        # 内部情報が露出しない
        assert "KNOWLEDGE_BASE_ID" not in data["detail"]


@pytest.mark.asyncio
class TestRagRouterAsyncIntegration:
    """asyncio.to_thread + wait_for 統合テスト"""

    async def test_service_called_with_correct_params(self):
        """サービスが正しいパラメータで呼ばれることを確認（非ブロッキング）"""
        mock_result = RAGResult(answer="回答", sources=[])

        with patch("app.routers.rag_router.BedrockRAGService") as MockService:
            mock_instance = MagicMock()
            mock_instance.query.return_value = mock_result
            MockService.return_value = mock_instance

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/rag/query",
                    json={
                        "query": "テスト",
                        "municipality_name": "松山市",
                        "district_name": "清水",
                    },
                )

            # service.query が呼ばれたことを確認
            mock_instance.query.assert_called_once_with(
                query="テスト",
                municipality_name="松山市",
                district_name="清水",
            )

        assert response.status_code == 200


@pytest.mark.asyncio
class TestRagRouterResponseStructure:
    """レスポンス構造テスト"""

    async def test_response_has_answer_and_sources_fields(self):
        """レスポンスに answer と sources フィールドが含まれる"""
        mock_result = RAGResult(
            answer="テスト回答",
            sources=[
                {"title": "source1", "uri": "s3://uri1", "snippet": "テキスト1"},
                {"title": "source2", "uri": "s3://uri2", "snippet": None},
            ],
        )

        with patch("app.routers.rag_router.BedrockRAGService") as MockService:
            mock_instance = MagicMock()
            mock_instance.query.return_value = mock_result
            MockService.return_value = mock_instance

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/rag/query",
                    json={"query": "テスト"},
                )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert isinstance(data["sources"], list)
        assert len(data["sources"]) == 2
        assert data["sources"][0]["title"] == "source1"
        assert data["sources"][1]["snippet"] is None
