# Requirements Document

## Introduction

既存のGemini APIベースのAIチャット機能を、Amazon Bedrock Knowledge Base（Agentic Retrieval + Answer Generation）を使ったRAGシステムに置き換える。FlutterフロントエンドからFastAPIバックエンドを経由してBedrock Managed Knowledge Baseへクエリを発行し、ゴミ出し情報に特化した回答を返す。

## Glossary

- **RAG_Service**: FastAPIバックエンドでBedrock Knowledge Baseとの通信を担当する同期サービスコンポーネント
- **RAG_Router**: FastAPIバックエンドでRAGクエリのHTTPエンドポイントを提供するルーターコンポーネント
- **RAG_Client**: FlutterフロントエンドでバックエンドのRAG APIを呼び出すサービスクラス
- **AI_Chat_Widget**: FlutterフロントエンドでRAGチャットUIを表示するウィジェット
- **Knowledge_Base**: Amazon Bedrock Managed Knowledge Base（ID: O5UJSVXWU4）
- **Agentic_Retrieval**: Bedrock Agent RuntimeのストリーミングAPI（agentic_retrieve_stream）による反復検索・回答生成
- **Region_Setting**: ユーザーが選択した地域情報（都道府県、市区町村、地区）
- **Context_Prompt**: Knowledge Baseへのクエリに付与する動的コンテキスト情報（日付、地域名）
- **Result_Event**: AgenticRetrieveStreamの最終結果イベント。generatedResponse.answer、citations、resultsを含む

## Requirements

### Requirement 1: RAG Query Endpoint

**User Story:** As a frontend developer, I want a backend API endpoint that accepts garbage-related queries with region context, so that the AI chat can retrieve relevant answers from the Knowledge Base.

#### Acceptance Criteria

1. WHEN a POST request is sent to `/api/rag/query` with a valid query and region information, THE RAG_Router SHALL accept the request and return a JSON response containing an answer and sources
2. WHEN a POST request is sent with an empty or whitespace-only query field, THE RAG_Router SHALL return a 422 validation error with a descriptive message
3. THE RAG_Router SHALL accept requests without authentication (no JWT token required)
4. WHEN district_id and district_name are not provided in the request, THE RAG_Router SHALL process the query without district context
5. WHEN municipality_id and municipality_name are provided in the request, THE RAG_Router SHALL include municipality context in the Knowledge Base query
6. THE RAG_Router SHALL NOT validate the existence of municipality_id or district_id against a master data source

### Requirement 2: Bedrock Knowledge Base Integration

**User Story:** As a backend developer, I want a service that communicates with Amazon Bedrock Knowledge Base using Agentic Retrieval, so that user queries are answered with accurate garbage disposal information.

#### Acceptance Criteria

1. WHEN the RAG_Service receives a query, THE RAG_Service SHALL call the Bedrock `agentic_retrieve_stream` API using the messages/retrievers/agenticRetrieveConfiguration request format
2. THE RAG_Service SHALL pass messages as a list containing a single user message with the context prompt as text content
3. THE RAG_Service SHALL pass retrievers as a list containing a Knowledge Base retriever with the Knowledge Base ID from configuration
4. THE RAG_Service SHALL set agenticRetrieveConfiguration with `foundationModelType = "MANAGED"` and `maxAgentIteration` from configuration (default 5)
5. THE RAG_Service SHALL set `generateResponse = True` to enable answer generation
6. THE RAG_Service SHALL read Knowledge Base ID, AWS region, max iterations, and foundation model type from environment variables via config module
7. THE RAG_Service SHALL NOT hardcode AWS credentials, Knowledge Base IDs, AWS regions, district names, municipality names, or year values
8. THE RAG_Service SHALL be implemented as synchronous functions (not async def) since boto3 is a synchronous SDK
9. THE RAG_Router SHALL call the RAG_Service via `asyncio.to_thread()` or equivalent to avoid blocking the FastAPI event loop

### Requirement 3: Dynamic Context Construction

**User Story:** As a system designer, I want the backend to construct a dynamic context prompt based on the current date and user's region, so that Knowledge Base queries return location-specific and temporally-relevant answers.

#### Acceptance Criteria

1. WHEN constructing a query for the Knowledge Base, THE RAG_Service SHALL include the current date in Japan timezone (from TIMEZONE configuration)
2. WHEN municipality_name is provided in the request, THE RAG_Service SHALL include "利用自治体は{municipality_name}です。" in the context prompt
3. WHEN district_name is provided in the request, THE RAG_Service SHALL include "対象地区は{district_name}です。" in the context prompt
4. WHEN district_name is not provided, THE RAG_Service SHALL omit district information from the context prompt
5. WHEN municipality_name is not provided, THE RAG_Service SHALL omit municipality information from the context prompt
6. THE RAG_Service SHALL derive the current date dynamically from the system clock in the configured timezone
7. THE context prompt SHALL include an instruction to answer based on retrieved information and not fabricate disposal methods, precautions, or collection dates not in the retrieved data

### Requirement 4: Error Handling

**User Story:** As a user, I want clear error messages when the AI chat encounters problems, so that I understand what went wrong and can retry appropriately.

#### Acceptance Criteria

1. IF an AWS authentication or credentials error occurs, THEN THE RAG_Service SHALL raise an error that results in a 503 HTTP response with a descriptive message
2. IF the Bedrock API returns an error, THEN THE RAG_Service SHALL raise an error that results in a 503 HTTP response with a descriptive message
3. IF the Bedrock API call times out, THEN THE RAG_Router SHALL return a 504 HTTP response with a timeout message
4. IF the Knowledge Base returns no answer content (result.generatedResponse.answer is empty or absent), THEN THE RAG_Service SHALL return a message indicating no answer was found
5. IF a stream processing error occurs during result event handling, THEN THE RAG_Service SHALL raise an error that results in an appropriate HTTP error response
6. THE RAG_Router SHALL NOT fallback to Gemini API or local search when an error occurs

### Requirement 5: Configuration Management

**User Story:** As a DevOps engineer, I want all RAG-related settings managed through environment variables, so that the application can be configured without code changes across environments.

#### Acceptance Criteria

1. THE config module SHALL expose AWS_REGION with a default value of `ap-northeast-1`
2. THE config module SHALL expose KNOWLEDGE_BASE_ID read from the `KNOWLEDGE_BASE_ID` environment variable
3. THE config module SHALL expose TIMEZONE with a default value of `Asia/Tokyo`
4. THE config module SHALL expose AGENTIC_MAX_ITERATIONS with a default value of `5`
5. THE config module SHALL expose AGENTIC_FOUNDATION_MODEL_TYPE with a default value of `MANAGED`

### Requirement 6: Frontend RAG Client

**User Story:** As a frontend developer, I want a Dart service that communicates with the backend RAG endpoint, so that the AI chat widget can send queries and receive answers.

#### Acceptance Criteria

1. WHEN a query is sent via the RAG_Client, THE RAG_Client SHALL send a POST request to `{AppConfig.apiBaseUrl}/api/rag/query` with the query and region information
2. WHEN the Region_Setting is available, THE RAG_Client SHALL include municipality_id, municipality_name, district_id, and district_name in the request body
3. WHEN no Region_Setting is available, THE RAG_Client SHALL send only the query without region fields
4. WHEN the backend returns a successful response, THE RAG_Client SHALL parse and return the answer text
5. IF the backend returns an error response, THEN THE RAG_Client SHALL return a user-friendly Japanese error message

### Requirement 7: AI Chat Widget Integration

**User Story:** As a user, I want the AI chat to use the RAG system with my region settings, so that I get garbage disposal answers specific to my neighborhood.

#### Acceptance Criteria

1. WHEN the AI_Chat_Widget is initialized, THE AI_Chat_Widget SHALL access the regionSettingProvider to obtain current region information
2. WHEN a user sends a message, THE AI_Chat_Widget SHALL pass the message and current region setting to the RAG_Client
3. WHEN a user sends a message while region is not configured, THE AI_Chat_Widget SHALL send the query without region context
4. THE AI_Chat_Widget SHALL be implemented as a ConsumerStatefulWidget to access Riverpod providers

### Requirement 8: Result Event Processing

**User Story:** As a backend developer, I want the final result event from AgenticRetrieveStream processed to extract the generated answer and citations, so that users receive complete and sourced responses.

#### Acceptance Criteria

1. THE RAG_Service SHALL separate result event processing logic from HTTP router logic
2. WHEN the stream completes, THE RAG_Service SHALL extract the final answer from `result.generatedResponse.answer`
3. THE RAG_Service SHALL extract source citation information from `result.generatedResponse.citations` and `result.results` when available
4. WHEN the result is processed, THE RAG_Router SHALL return it as a standard HTTP JSON response to the frontend
5. THE RAG_Service SHALL handle responseEvent text chunks for future streaming support but SHALL use result.generatedResponse.answer as the authoritative answer for the current HTTP response
