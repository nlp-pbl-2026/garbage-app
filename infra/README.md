# AWS RAG・Backendインフラストラクチャ

このディレクトリは、ごみ分別ガイド専用のAWSリソースをTerraformで管理します。過去に作成されたKnowledge Base、S3バケット、IAMロールはimportも参照もしていません。

## 現在の構成

基本設定:

| 項目 | 値 |
| --- | --- |
| リージョン | `ap-northeast-1`（東京） |
| Terraform | 1.10以上 |
| AWS Provider | `~> 6.60` |
| 管理タグ | Terraform変数で指定 |

作成済みリソース:

| 種別 | 用途 |
| --- | --- |
| Amazon Bedrock | Nova LiteとTitan Text Embeddings V2による言い換え・意味検索・分類 |
| Amazon S3 / Bedrock Knowledge Base | 比較実験用のRAGデータと検索経路 |
| AWS Lambda | FastAPIのAIあいまい検索API |
| Amazon API Gateway | Flutter向けHTTPSエンドポイント |
| Amazon DynamoDB | 検索・回答・確信度・処理時間の分析ログ |
| Amazon CloudWatch Logs | Backend実行ログ（30日保持） |

Backend API URLとAWSリソースIDはGitに固定値を記録せず、
`terraform output -raw backend_api_url`などのTerraform outputから取得してください。

## アーキテクチャ

```text
data/regions/matsuyama/common/knowledge
  ├─ items.csv
  ├─ category_rules.csv
  └─ general_rules.csv
          │ terraform apply
          ▼
Private S3 bucket
          │ managed S3 connector / ingestion job
          ▼
Bedrock Managed Knowledge Base
          │ Retrieve API
          ▼
FastAPI
  ├─ Nova Lite: 言い換え
  ├─ ローカル品目CSV: 表層一致検索
  ├─ Managed KB: 意味検索
  ├─ RRF: 2つの検索結果を統合
  ├─ Nova Lite: 分類または追加質問
  ├─ ローカルCSV: 清水地区の次回収集日（可燃7時、ほか8時締切）
  └─ DynamoDB: 検索分析ログ（90日TTL）
          │ HTTP
          ▼
API Gateway HTTP API
          │ HTTPS
          ▼
Flutter Web / mobile（あいまい検索・管理キー付き分析画面）
```

S3は公開アクセスをすべて遮断し、バージョニングとSSE-S3（AES-256）を有効にしています。IAMロールは対象バケットの `knowledge/matsuyama/common/` だけを読み取れます。

## Terraformファイル

| ファイル | 内容 |
| --- | --- |
| `terraform/main.tf` | S3、IAM、Knowledge Base、data source |
| `terraform/backend.tf` | Lambda、API Gateway、DynamoDB、CloudWatch Logs |
| `terraform/providers.tf` | AWS provider、共通タグ、IAMポリシー用のタグなしprovider |
| `terraform/variables.tf` | リージョン、環境、組織タグ、破棄設定 |
| `terraform/outputs.tf` | バックエンドに必要なID |
| `scripts/sync_knowledge_base.sh` | 取り込み開始と完了待機 |
| `../scripts/package_backend.sh` | Lambda向けLinux/ARM64 zipの生成 |
| `../scripts/aws-up.sh` | package、Terraform apply、RAG取り込みをまとめて実行 |
| `../scripts/aws-down.sh` | 全リソースを確認付きでdestroy |
| `operator-policy.example.json` | Terraform操作者に必要な最小権限例 |

Terraform stateはGit管理しません。複数人で運用する場合は、別途ブートストラップしたS3 backendなどへstateを移行してください。

## IAM制約のある環境

組織のガードレールでIAMロールの命名、タグ、ポリシー作成が制限されている場合は、
Terraform変数とリソース名をその環境に合わせてください。通常の`terraform plan/apply/destroy`には、
対象リソースの操作権限に加えて`iam:GetPolicyVersion`と`iam:ListPolicyVersions`が必要です。
必要権限の例は[`operator-policy.example.json`](operator-policy.example.json)を参照してください。

## ルートから構築・削除

通常はプロジェクトルートで次だけを実行します。

```bash
./scripts/aws-up.sh
./scripts/aws-down.sh
```

`scripts/aws-up.sh` は権限が揃っている場合、Lambda packageを作成し、Terraformで全AWSリソースを作成・更新して、Knowledge Baseの取り込み完了まで待ちます。

`iam:GetPolicyVersion`または`iam:ListPolicyVersions`が不足していても、環境変数で指定した既存Lambdaを確認できる場合は、
制限モードでそのコードだけを`UpdateFunctionCode`で更新します。Terraform、Knowledge Base、S3は変更しません。
新規構築、構成変更、RAGデータ更新には完全な権限が必要です。

制限モードでは、コード更新前に既存Lambdaの`USE_BEDROCK_KNOWLEDGE_BASE=false`と`LEXICAL_SEARCH_ENABLED=false`を確認します。公開環境はTitan Embedding単体に固定しているため、設定が異なる場合は意図しない検索方式へ切り替えず、安全のため更新を停止します。

`scripts/aws-down.sh` は削除planを表示した後、Knowledge Base、API、ログテーブル、S3を含む全リソースを削除します。必要なIAM読取権限がなければ部分削除せず停止します。

## Terraformを個別に実行する場合

前提:

- `aws sts get-caller-identity` が対象アカウントを返す
- Terraform 1.10以上をインストール済み
- 前述のIAM規則を満たす権限がある

```bash
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform validate
./scripts/package_backend.sh
terraform -chdir=infra/terraform plan
terraform -chdir=infra/terraform apply
./infra/scripts/sync_knowledge_base.sh
```

`sync_knowledge_base.sh` は `terraform` をPATHから探します。別のバイナリを使う場合は指定できます。

```bash
TERRAFORM_BIN=/path/to/terraform ./infra/scripts/sync_knowledge_base.sh
```

## データ更新

RAG原本は次の場所だけを編集します。

```text
data/regions/matsuyama/common/knowledge/
```

反映手順:

```bash
terraform -chdir=infra/terraform plan
terraform -chdir=infra/terraform apply
./infra/scripts/sync_knowledge_base.sh
```

TerraformがS3オブジェクトのETag差分を検出してアップロードし、スクリプトが新しい取り込みジョブの完了まで待機します。

清水地区の収集カレンダー `data/regions/matsuyama/shimizu/calendar/2026.csv` はバックエンドが直接読むため、S3・Knowledge Baseには登録しません。

## バックエンド設定

```bash
export AWS_REGION="$(terraform -chdir=infra/terraform output -raw aws_region)"
export BEDROCK_KNOWLEDGE_BASE_ID="$(terraform -chdir=infra/terraform output -raw knowledge_base_id)"
export BEDROCK_MODEL_ID="amazon.nova-lite-v1:0"
export BEDROCK_EMBEDDING_MODEL_ID="amazon.titan-embed-text-v2:0"
export USE_BEDROCK_KNOWLEDGE_BASE="false"
export LEXICAL_SEARCH_ENABLED="false"
```

このアカウントではAPACクロスリージョン推論プロファイル `apac.amazon.nova-lite-v1:0` がシドニーなどへルーティングされる可能性があり、identity policyで拒否されます。東京リージョン内の直接モデルIDを使用してください。

AWS上ではこれらの値をTerraformがLambda環境変数へ設定し、Bedrock・DynamoDBへの認証はLambda実行ロールが担当します。アクセスキーの `.env` 保存は不要です。FlutterはAWS認証情報を持たず、次のAPI URLだけを受け取ります。

本番の意味検索は、LambdaがTitan Text Embeddings V2を直接呼び出し、同梱した`item_embeddings.npz`を検索します。Managed Knowledge Baseと表層一致検索は比較実験用として残しています。

```bash
API_BASE_URL="$(terraform -chdir=infra/terraform output -raw backend_api_url)"
cd frontend
flutter run -d chrome --dart-define=API_BASE_URL="${API_BASE_URL}"
```

ハッカソン審査では、リポジトリルートの次のコマンドで公開APIの確認から起動まで行えます。

```bash
./scripts/run-demo.sh
```

公開APIはAWS認証不要です。API Gatewayの既定ルートは5 req/s、burst 10に制限し、分析APIだけは別途管理キーで保護しています。公開URLは審査関係者に限定して共有してください。
APIの疎通だけを確認する場合は`./scripts/run-demo.sh --check`を実行します。

検索分析画面へ入力する管理キーは次で表示します。この値はGitや公開Flutter buildへ含めないでください。

```bash
terraform -chdir=infra/terraform output -raw analytics_api_key
```

## 状態確認

```bash
terraform -chdir=infra/terraform output
terraform -chdir=infra/terraform state list

aws bedrock-agent get-knowledge-base \
  --knowledge-base-id "$(terraform -chdir=infra/terraform output -raw knowledge_base_id)" \
  --region ap-northeast-1
```

直近の取り込みはBedrockコンソール、または `list-ingestion-jobs` で確認できます。

```bash
aws bedrock-agent list-ingestion-jobs \
  --knowledge-base-id "$(terraform -chdir=infra/terraform output -raw knowledge_base_id)" \
  --data-source-id "$(terraform -chdir=infra/terraform output -raw data_source_id)" \
  --region ap-northeast-1
```

## 費用と未使用時の扱い

結論として、アプリを起動していなくても完全な無料にはなりません。

| リソース | 未使用時 | 使用時 |
| --- | --- | --- |
| Bedrock Managed Knowledge Base | indexを保持している限りraw data容量課金が続く | 標準Retrieve APIの呼び出し回数でも課金 |
| Amazon Nova Lite | オンデマンド利用では呼び出さなければトークン課金なし | 入力・出力トークン量で課金 |
| S3 | オブジェクトと過去versionを保持する限り容量課金が続く | PUT、GET、LISTなどのrequest課金 |
| IAM | IAMロール・ポリシー自体の追加料金なし | 追加料金なし |
| CloudWatch | 保存するログ・カスタムメトリクス等があれば課金対象になり得る | 量に応じて課金 |
| Lambda / API Gateway | リクエストがなければ実行・APIリクエスト課金は原則発生しない | 呼び出し回数と実行時間に応じて課金 |
| DynamoDB | PAY_PER_REQUESTのため予約容量課金なし。ログ保存量の課金は残る | 読み書きと保存量に応じて課金 |

2026-08-24時点のManaged Knowledge Base公式単価は、index storageがraw data 1 GBあたり月額USD 5、標準Retrieveが1,000 API callsあたりUSD 1です。managed parser、managed embedding、managed rerankerは追加料金なしです。現在のRAG原本は約320 KBなので保存費は小さいものの、Knowledge Baseを残す限りゼロとは限りません。

- [Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/)
- [Managed Knowledge Baseの仕組み](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-build-managed.html)
- [Amazon Nova Lite model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-lite.html)
- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/)

### 短期間使わない場合

Flutterを終了してください。Lambdaは常時起動ではないため停止操作は不要で、Nova Liteの推論とRetrieve呼び出しも止まります。Knowledge Baseのindex保存費、S3保存費、DynamoDBのログ保存費は残ります。Managed Knowledge BaseにはEC2のような「停止」状態はありません。

### 長期間使わない場合

費用を止めるにはAWSリソースを削除します。再開時はTerraform applyと取り込みをやり直せます。

Terraform実行者に前述の`iam:GetPolicyVersion`と`iam:ListPolicyVersions`がない場合、管理ポリシーをrefreshできず、
通常のdestroyを安全に完遂できません。実行前に管理者へ権限付与を依頼してください。

削除前に必ずplanを確認してください。次の変数は、バージョニング済みS3内の全object versionも削除対象にします。

```bash
./scripts/aws-down.sh
```

これはKnowledge Base、index、data source、Backend API、検索ログ、IAMロール・ポリシー、S3内の原本と全versionを削除する復旧不能な操作です。リポジトリ内のコードとCSVは残るため、再構築は可能です。

削除確認:

```bash
terraform -chdir=infra/terraform state list
```

何も表示されなければstate上の削除は完了です。実際のAWS側もBedrockコンソールとS3コンソールで確認してください。
