# Implementation Plan: Bedrock RAG Query

## Overview

既存のGemini AIチャットをBedrock Knowledge Base RAGシステムに置き換える。バックエンド（FastAPI）にRAGエンドポイントとBedrockサービスを追加し、フロントエンド（Flutter）にRAGクライアントを作成してAiChatWidgetを更新する。

## Tasks

- [ ] 1. Backend configuration and schemas
  - [ ] 1.1 Update `backend/app/config.py` to add RAG environment variables
    - Add AWS_REGION, KNOWLEDGE_BASE_ID, TIMEZONE, AGENTIC_MAX_ITERATIONS, AGENTIC_FOUNDATION_MODEL_TYPE
    - Use `os.getenv()` with defaults as specified in design
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  - [ ] 1.2 Update `backend/app/schemas.py` to add RAG request/response schemas
    - Add `RAGQueryRequest` with query field validator (reject whitespace-only)
    - Add `RAGSource` model with optional title, uri, snippet
    - Add `RAGQueryResponse` with answer and sources list
    - municipality_id, district_id are optional fields for future use (no master validation)
    - _Requirements: 1.1, 1.2, 1.6_
  - [ ] 1.3 Update `backend/requirements.txt` to add boto3
    - Add `boto3>=1.38.0` (or the minimum version confirmed to contain `agentic_retrieve_stream`)
    - Verify the installed boto3 version includes `bedrock-agent-runtime` client with `agentic_retrieve_stream` method
    - _Requirements: 2.1_

- [ ] 2. Implement Bedrock service (synchronous)
  - [ ] 2.1 Create `backend/app/services/bedrock_service.py`
    - Implement `BedrockRAGService` class with DI-capable constructor (accepts optional boto3 client for testing)
    - All methods are **synchronous** (not async) since boto3 is a synchronous SDK
    - Implement `build_context_prompt()`:
      - Include current date in Japan timezone (from config.TIMEZONE)
      - Include "利用自治体は{municipality_name}です。" when municipality_name is provided
      - Include "対象地区は{district_name}です。" when district_name is provided
      - Omit municipality/district lines when values are None
      - Include anti-hallucination instruction: "取得情報にない分別方法・注意事項・収集日を推測して追加しないでください。"
      - No hardcoded values (district names, municipality names, years)
    - Implement `extract_result(stream)`:
      - Iterate stream events synchronously
      - Extract final answer from `result["generatedResponse"]["answer"]`
      - Extract sources from `result["generatedResponse"].get("citations", [])` and `result.get("results", [])`
      - Handle responseEvent for future streaming (passthrough for now)
      - Return RAGResult dataclass/namedtuple with answer and sources
    - Implement `query()` (synchronous):
      - Call `build_context_prompt()`
      - Call `client.agentic_retrieve_stream()` with AWS-official format:
        - `messages=[{"role": "user", "content": {"text": context_prompt}}]`
        - `retrievers=[{"description": "...", "configuration": {"knowledgeBase": {"knowledgeBaseId": config.KNOWLEDGE_BASE_ID}}}]`
        - `agenticRetrieveConfiguration={"foundationModelType": config.AGENTIC_FOUNDATION_MODEL_TYPE, "maxAgentIteration": config.AGENTIC_MAX_ITERATIONS}`
        - `generateResponse=True`
      - Call `extract_result()` on the response stream
      - Handle AWS credential errors (NoCredentialsError), API errors (ClientError), and empty results
    - Define custom exception class `BedrockServiceError` for service-level errors
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 4.2, 4.4, 4.5, 8.1, 8.2, 8.3, 8.5_
  - [ ]* 2.2 Write property tests for context prompt construction
    - **Property 2: Context prompt includes municipality when provided**
    - **Property 3: Context prompt excludes district when not provided**
    - **Property 4: Context prompt includes district when provided**
    - **Property 9: Context prompt includes anti-hallucination instruction**
    - **Validates: Requirements 1.4, 1.5, 3.2, 3.3, 3.4, 3.7**
  - [ ]* 2.3 Write property test for result event extraction
    - **Property 5: Result answer is extracted from generatedResponse**
    - **Property 8: Source citations extracted from result event**
    - Mock result event structure with generatedResponse.answer and citations
    - **Validates: Requirements 2.4, 8.2, 8.3**
  - [ ]* 2.4 Write property test for whitespace query validation
    - **Property 1: Whitespace-only queries are rejected**
    - **Validates: Requirements 1.2**

- [ ] 3. Implement RAG router (async with to_thread)
  - [ ] 3.1 Create `backend/app/routers/rag_router.py`
    - Implement POST `/api/rag/query` endpoint (no auth dependency)
    - Use `asyncio.to_thread()` to call `BedrockRAGService.query()` without blocking the event loop
    - Handle TimeoutError → 504 HTTPException
    - Handle BedrockServiceError → 503 HTTPException
    - Return RAGQueryResponse on success
    - _Requirements: 1.1, 1.3, 2.9, 4.1, 4.2, 4.3, 4.6, 8.4_
  - [ ] 3.2 Update `backend/app/main.py` to register rag_router
    - Import and include rag_router in app
    - _Requirements: 1.1_
  - [ ]* 3.3 Write unit tests for rag_router
    - Test successful query response structure
    - Test empty query returns 422
    - Test Bedrock error returns 503
    - Test timeout returns 504
    - Test no auth required (request without Bearer token succeeds)
    - Test asyncio.to_thread integration (mock service, verify non-blocking)
    - Mock BedrockRAGService for isolation
    - _Requirements: 1.1, 1.2, 1.3, 2.9, 4.1, 4.2, 4.3_

- [ ] 4. Checkpoint - Backend verification
  - Verify boto3 can be installed and `agentic_retrieve_stream` method exists on the client
  - Ensure all tests pass
  - Ask the user if questions arise

- [ ] 5. Implement frontend RAG client
  - [ ] 5.1 Create `frontend/lib/services/rag_service.dart`
    - Implement `RagService` class with `sendMessage(String query, {RegionSetting? region})` method
    - Use `AppConfig.apiBaseUrl` for base URL
    - Construct request body with query and optional region fields (municipality_id, municipality_name, district_id, district_name from RegionSetting)
    - Parse successful response to extract answer text
    - Return user-friendly Japanese error messages for error responses (503→接続エラー, 504→タイムアウト)
    - Handle network errors with appropriate message
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  - [ ]* 5.2 Write unit tests for RagService
    - Test correct request body with region (includes municipality_id, municipality_name, district_id, district_name)
    - Test correct request body without region (only query field)
    - Test successful response parsing (extracts answer)
    - Test error handling (503, 504, network error → Japanese messages)
    - Use MockClient from http package
    - **Property 6: Region fields included in request when region is set**
    - **Property 7: Successful response parsing extracts answer**
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 6. Update AI Chat Widget
  - [ ] 6.1 Convert `frontend/lib/widgets/ai_chat_widget.dart` to use RAG
    - Change `StatefulWidget` to `ConsumerStatefulWidget`
    - Change `State<AiChatWidget>` to `ConsumerState<AiChatWidget>`
    - Replace `GeminiService` import and instance with `RagService`
    - Read `regionSettingProvider` from `ref` to get current RegionSetting
    - Pass RegionSetting to `RagService.sendMessage()` call
    - Handle null/loading region state (send without region context)
    - Remove Gemini API key dependency
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [ ]* 6.2 Write widget test for AiChatWidget
    - Test message sending with region
    - Test message sending without region (region not configured)
    - Override regionSettingProvider and mock RagService in test ProviderScope
    - _Requirements: 7.1, 7.2, 7.3_

- [ ] 7. Final checkpoint - Full integration verification
  - Ensure all backend tests pass
  - Ensure all frontend tests pass
  - Verify no changes to unrelated features (calendar, search, GPS, etc.)
  - Ask the user if questions arise

## Notes

- Tasks marked with `*` are test tasks that should be implemented alongside their corresponding implementation task
- Each task references specific requirements for traceability
- Backend uses Python (FastAPI, pytest, hypothesis for PBT)
- Frontend uses Dart (Flutter, flutter_test)
- **boto3 is synchronous**: All `bedrock_service.py` methods are sync; `rag_router.py` uses `asyncio.to_thread()` to avoid blocking
- **Result event is authoritative**: The final `result.generatedResponse.answer` is the source of truth, not concatenated responseEvent chunks
- boto3 is mocked in all backend tests (no real AWS calls)
- Property tests run minimum 100 iterations each
- No changes to existing auth, image upload, local search, or other unrelated features
- Region IDs are passed through without validation; only names are used in context prompt
- boto3 version must be confirmed at implementation time to support `agentic_retrieve_stream`
