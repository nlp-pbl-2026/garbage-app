# ごみ分別ガイド

松山市・清水地区を対象に、利用者が入力した品目をRAGで検索し、ごみ分類と次回収集日、または分類に必要な追加質問を返すアプリケーションです。

会話型チャットではなく、1件の質問に対して次のどちらかを返します。

- 分類を確定できる場合: 分類、出し方、清水地区の次回収集日
- 分類を確定できない場合: 判定に必要な追加質問を1件

現在対応している地域は松山市（自治体ID `38201`）の清水地区（地区ID `38201-08`）だけです。

## 処理フロー

1. Amazon Nova Liteで利用者の入力を検索向けに言い換える
2. Amazon Bedrock Managed Knowledge Baseから関連文書をtop-k検索する
3. 検索結果だけを根拠にごみ分類を生成する
4. 分類と確信度を評価する
5. 確定できる場合は地域別カレンダーから次回収集日を返す
6. 確定できない場合は追加質問を1件返す

## ディレクトリ

| パス | 内容 |
| --- | --- |
| `backend/` | FastAPI API、Bedrock連携、分類ロジック、カレンダー検索 |
| `frontend/` | Flutterクライアント。検索、回答、追加質問を単一画面で表示 |
| `data/regions/matsuyama/common/knowledge/` | RAGへ取り込む松山市の品目・分類ルール |
| `data/regions/matsuyama/shimizu/calendar/` | 清水地区の収集カレンダー |
| `infra/terraform/` | AWSリソースを管理するTerraform |
| `infra/scripts/` | Knowledge Baseの取り込みスクリプト |

AWSの実リソース、費用、構築・更新・削除手順は [`infra/README.md`](infra/README.md) を参照してください。

## 必要なもの

- Python 3.10以上
- [uv](https://docs.astral.sh/uv/)
- Flutter SDKとChrome
- Terraform 1.10以上
- AWS CLIで対象アカウントへ認証済みであること
- `ap-northeast-1` のAmazon Bedrockで `amazon.nova-lite-v1:0` を利用できること

## 起動

### 1. バックエンド設定

AWS構築済み環境の値をTerraform outputから読み込みます。

```bash
export AWS_REGION="$(terraform -chdir=infra/terraform output -raw aws_region)"
export BEDROCK_KNOWLEDGE_BASE_ID="$(terraform -chdir=infra/terraform output -raw knowledge_base_id)"
export BEDROCK_MODEL_ID="amazon.nova-lite-v1:0"
```

依存関係を同期し、APIを起動します。

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

確認先:

- ヘルスチェック: `http://127.0.0.1:8000/api/health`
- OpenAPI UI: `http://127.0.0.1:8000/docs`

### 2. Flutter Web

別ターミナルで起動します。

```bash
cd frontend
flutter pub get
flutter run -d chrome \
  --dart-define=API_BASE_URL=http://localhost:8000
```

## APIの使用例

```bash
curl -sS http://127.0.0.1:8000/api/search/classify \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "ペットボトルは何ごみ？",
    "municipality_id": "38201",
    "district_id": "38201-08",
    "clarifications": []
  }'
```

追加質問へ回答するときは、元の質問と質問・回答の組を送ります。

```json
{
  "query": "この容器は何ごみ？",
  "municipality_id": "38201",
  "district_id": "38201-08",
  "clarifications": [
    {
      "question": "容器は紙製ですか、プラスチック製ですか？",
      "answer": "プラスチック製です"
    }
  ]
}
```

## プロンプト・モデル・検索設定

| 設定 | 場所 | 内容 |
| --- | --- | --- |
| 言い換えプロンプト | `backend/app/services/waste_guide_service.py` の `rewrite_query()` | 入力と追加回答をRAG検索文へ変換 |
| 分類・追加質問プロンプト | 同ファイルの `classify()` | RAG根拠から分類JSONまたは追加質問を生成 |
| モデルID | `backend/app/config.py` の `BEDROCK_MODEL_ID` | 既定値 `amazon.nova-lite-v1:0`。環境変数で上書き可能 |
| Knowledge Base ID | 同ファイルの `BEDROCK_KNOWLEDGE_BASE_ID` | Terraform outputから設定 |
| RAG取得件数 | 同ファイルの `RAG_TOP_K` | 既定値 `8` |
| 分類確信度 | 同ファイルの `CLASSIFICATION_CONFIDENCE_THRESHOLD` | 既定値 `0.75` |
| APIタイムアウト | 同ファイルの `RAG_REQUEST_TIMEOUT_SECONDS` | 既定値 `60` 秒 |
| AWS認証 | AWS SDKの標準credential chain | 必要なら `AWS_PROFILE` を設定 |
| DB | `backend/app/config.py` の `DATABASE_URL` | 既定値はローカルSQLite |
| JWT署名鍵 | 同ファイルの `SECRET_KEY` | 本番では必ず安全な値を環境変数で設定 |
| タイムゾーン | 同ファイルの `TIMEZONE` | 既定値 `Asia/Tokyo` |
| フロントAPI URL | `frontend/lib/constants/app_config.dart` | `--dart-define=API_BASE_URL=...` で設定 |

このアカウントではAPACクロスリージョン推論プロファイルが明示的に拒否されるため、`apac.amazon.nova-lite-v1:0` ではなく東京リージョン内の `amazon.nova-lite-v1:0` を使います。

## データ更新

RAGデータを編集した後はTerraformでS3へ反映し、取り込みを再実行します。

```bash
terraform -chdir=infra/terraform plan
terraform -chdir=infra/terraform apply
./infra/scripts/sync_knowledge_base.sh
```

収集カレンダーはバックエンドがリポジトリ内のCSVを直接参照するため、Knowledge Baseへの取り込み対象ではありません。

## テスト

```bash
cd backend
uv run pytest -q

cd ../frontend
flutter test test/unit
flutter analyze --no-fatal-warnings --no-fatal-infos
flutter build web --dart-define=API_BASE_URL=http://localhost:8000
```
