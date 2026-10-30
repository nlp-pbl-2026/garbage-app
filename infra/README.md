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

Terraformで管理するリソース（実環境への今回の反映は未実施）:

| 種別 | 用途 |
| --- | --- |
| Amazon Bedrock | Nova Liteの画像・テキスト理解と分類、Titan Text Embeddings V2による検索文のベクトル化 |
| Amazon S3 / Bedrock Knowledge Base | 比較実験用のRAGデータと検索経路 |
| AWS Lambda | FastAPIのAIあいまい検索API |
| Amazon API Gateway | Flutter向けHTTPSエンドポイント |
| Amazon DynamoDB | 検索・回答・確信度・処理時間の分析ログ |
| Amazon CloudWatch Logs | Backend実行ログ（30日保持） |

Backend API URLとAWSリソースIDはGitに固定値を記録せず、
`terraform output -raw backend_api_url`などのTerraform outputから取得してください。

## アーキテクチャ

```text
Flutter Web / mobile（選択した収集地区、テキスト・画像、追加質問）
          │ HTTPS
          ▼
API Gateway HTTP API → Lambda / FastAPI
  ├─ Nova Lite: 画像・テキストから検索文へ言い換え
  ├─ Titan Text Embeddings V2: 検索文をベクトル化
  ├─ 同梱した1,756品目のEmbedding索引: 両地域の候補を検索
  │    ├─ 松山・北条: 品目辞典の分類・注意書き
  │    └─ 中島: 公式79行を優先し、共通候補には中島の分別ルールを適用
  ├─ Nova Lite: 地域別の根拠から分類または追加質問
  ├─ 同梱した地区台帳・2026年度カレンダー: 次回収集日（可燃7時、ほか8時締切）
  └─ DynamoDB: 検索分析ログ（90日TTL）

別経路: S3 → Bedrock Managed Knowledge Base（比較実験用）
```

通常の検索では `USE_BEDROCK_KNOWLEDGE_BASE=false`、`LEXICAL_SEARCH_ENABLED=false` とし、Knowledge Base検索、表層一致検索、RRF統合は使いません。中島の共通索引は候補取得に限り、松山・北条の分類や注意書きをそのまま回答根拠にしません。根拠が不足する場合は追加質問または判定保留にします。Flutterの地区台帳・カレンダーは同じ原本から生成したアセットを使用します。

検索画像はAPIリクエストからNova Liteへ直接渡します。S3やDynamoDBには画像本体を保存せず、分析ログには画像の有無・形式・バイト数だけを記録します。既存のLambda実行ロールが持つNova Liteへの`bedrock:InvokeModel`権限を使用するため、画像検索専用のAWSリソースは追加しません。

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

以下のスクリプトを実行するとAWS環境が変更されます。更新前にデータ検証・Lambdaパッケージの内容・Terraform planを確認してください。

```bash
./scripts/aws-up.sh
./scripts/aws-down.sh
```

`scripts/aws-up.sh` は権限が揃っている場合、Lambda packageを作成し、Terraformで全AWSリソースを作成・更新して、Knowledge Baseの取り込み完了まで待ちます。
Knowledge Baseは通常検索で使いませんが、このスクリプトは比較実験用データの同期と取り込みも実行します。

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

全地区の2026年度収集カレンダー `data/regions/matsuyama/generated/calendar-2026.json` はLambdaパッケージに同梱するため、S3・Knowledge Baseには登録しません。Flutterには同じ原本から生成した `frontend/assets/data/municipality_calendar.json` を同梱します。

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

通常の意味検索は、LambdaがTitan Text Embeddings V2を直接呼び出し、同梱した`item_embeddings.npz`を両地域の候補取得に使います。中島では公式79行と地域別ルールにより判定根拠を構成します。Managed Knowledge Baseと表層一致検索は比較実験用として残しています。今回の全地区対応が既存AWS環境で動くかは、デプロイ後のAPI確認が必要です。

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

料金は変更され得るため、デプロイ前に下記の公式料金表で確認してください。通常検索ではKnowledge BaseのRetrieveを使いませんが、`aws-up.sh` は比較実験用Knowledge Baseの取り込みジョブを開始します。Knowledge Baseを残す限り保存費が発生し得ます。

- [Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/)
- [Managed Knowledge Baseの仕組み](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-build-managed.html)
- [Amazon Nova Lite model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-lite.html)
- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/)

### 短期間使わない場合

Flutterを終了し、他のAPI利用がないことを確認してください。Lambdaは常時起動ではないため停止操作は不要です。検索リクエストがなければNova Lite・Titanの呼び出しは発生しません。Knowledge Baseのindex保存費、S3保存費、DynamoDBのログ保存費は残ります。Managed Knowledge BaseにはEC2のような「停止」状態はありません。

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
