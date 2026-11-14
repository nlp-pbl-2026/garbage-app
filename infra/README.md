# AWS RAG・Backendインフラストラクチャ

Flutter Webは独立した`infra/frontend/`で管理し、S3＋CloudFrontの構築・初回公開は完了しています。[通常の手動更新・初回構築・復旧手順](../docs/aws-frontend-hosting.md)を参照してください。通常更新は`scripts/frontend.py`とローカルAWS CLI認証で行い、Terraform applyやbootstrapは不要です。GitHub用IAM/OIDCは将来の明示的な有効化時だけ扱います。既存バックエンドのTerraformやstateは使いません。S3 backendの例はTerraform 1.17.2に対応する`allowed_account_ids`で認証先を制限し、既存stateの保存先を維持しています。

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
| Amazon DynamoDB | 品質改善用の検索文・言い換え・追加質問と回答・AIの回答、検索状態・区分・確信度・処理時間等。閲覧は分析キーで保護 |
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
| `../scripts/deploy_lambda_s3.py` | 既存S3経由のLambdaコード更新・バックアップ・復旧（Terraformなし） |
| `../scripts/flutter_with_data.py` | UIデータをAPI取得・検証し、隔離コピーでFlutterを起動・ビルド |
| `../scripts/aws-up.sh` | package、Terraform apply、RAG取り込みをまとめて実行 |
| `../scripts/aws-down.sh` | 全リソースを確認付きでdestroy |
| `operator-policy.example.json` | Terraform操作者に必要な最小権限例 |

Terraform stateはGit管理しません。複数人で運用する場合は、別途ブートストラップしたS3 backendなどへstateを移行してください。

Flutter用の新APIと住所表の同梱変更は[専用手順書](../docs/frontend-data-setup.md)を参照してください。新APIはAWS未反映ですが、ZIP内の`frontend_export_policy.json`で全20市町のUI用データを公開配信する設定です。資料の利用条件の確認状態は未確認のまま別管理し、管理者の公開判断とは区別します。既存の安全なS3コード更新で反映でき、現行の`$default`プロキシ構成では追加のIAM権限・環境変数・API Gateway変更は不要です。

## IAM制約のある環境

組織のガードレールでIAMロールの命名、タグ、ポリシー作成が制限されている場合は、
Terraform変数とリソース名をその環境に合わせてください。通常の`terraform plan/apply/destroy`には、
対象リソースの操作権限に加えて`iam:GetPolicyVersion`と`iam:ListPolicyVersions`が必要です。
必要権限の例は[`operator-policy.example.json`](operator-policy.example.json)を参照してください。

## ルートから構築・削除

**既存環境のコードだけを更新する場合は、[S3経由のLambda更新手順](../docs/lambda-s3-deploy.md)を使用してください。** 全20市町のZIPは約88.5 MiBで直接アップロード制限を超えます。`deploy_lambda_s3.py`は既存バケットと関数を確認し、`--execute`と対象確認文字列がある場合だけS3アップロード・コード更新を行います。以下の`aws-up.sh`はTerraformやKnowledge Baseも操作するため、コードだけの更新には使いません。

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

### 全自治体のローカル準備

標準カタログは20自治体を参照します。Lambda用データのステージングは、各自治体のCSV・索引・マニフェスト・カレンダーの整合性を検査し、不足時に停止します。各データガイドに従ってGit管理外の原本・CSV・索引を配置してください。[全20市町の統合検証](../docs/municipality-data-integration.md)と[S3経由のコード更新](../docs/lambda-s3-deploy.md)を参照してください。公開APIへの反映は別途必要です。

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

公開APIはAWS認証不要です。API Gatewayの既定ルートは5 req/s、burst 10に制限し、分析APIだけは別途管理キーで保護しています。公開URLを秘密として扱っても濫用対策にはなりません。個別の利用制限・費用監視・緊急停止とWAF導入時の制約は[セキュリティ対応と残作業](../docs/public-repository-security.md)を参照してください。今回のコード修正はAWSに未反映で、設定・stateは変更していません。
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

### 伊方町追加時のローカル準備

標準カタログへ伊方町（38442）を追加しています。[伊方町データガイド](../docs/ikata-data.md)に従って、CSV・専用NPZ・manifest・2026年度カレンダーを配置・生成してから `scripts/package_backend_data.py` で検証してください。既存3市の必要ファイルも引き続き必要です。伊方・瀬戸・三崎は同じ伊方町索引を利用し、地区別カレンダーだけを切り替えます。この実装でAWS設定・リソースは変更しておらず、公開APIへの反映、実機テスト、データの公開条件の確認は別途必要です。

### 新居浜市追加時のローカル準備

[新居浜市データガイド](../docs/niihama-data.md)に従って専用CSV・NPZ・manifest・カレンダーを配置し、共通生成処理でFlutterと同じ原本を利用してください。`scripts/package_backend_data.py` は標準カタログに登録された全自治体の実行時ファイルを検証して配置します。原本PDFや評価ログ、住所候補表はLambdaの分類・収集日APIには不要です。新居浜市の住所表はFlutterアセットへ別途生成されます。公開APIへの反映、実機検証、資料の利用・公開条件確認は別途必要です。

### 東温市追加時のローカル準備

[東温市データガイド](../docs/toon-data.md)に従いCSV・専用NPZ・manifest・32地区分のカレンダーを配置してください。重信・川内は同じ東温市索引を共有し、体温計の収集区分を切り替えます。搬出期限不明の区分で当日の期限内とは回答せず、日付未確認の計測器に定期予定を付けません。LambdaへOCR・PDF・生成スクリプトを含める必要はありません。`scripts/package_backend_data.py` のローカル検証で登録19自治体の実行時ファイルを配置できます。公開APIへの反映、実機検証、利用条件の確認は別途必要です。AWSやTerraformの設定・リソースは今回変更していません。

### 久万高原町データの同梱

久万高原町（`38386`）も既存の自治体カタログから読み込みます。追加リソースや専用APIは不要です。`data/regions/kumakogen/registry.json`、`knowledge/items.csv`、`knowledge/item_embeddings.npz`、`knowledge/index_manifest.json`、`generated/calendar-2026.json`を既存のデータステージング処理で同梱します。PDF・OCR・APIの生ログは同梱しません。共通原本から生成したFlutterのカタログ・台帳・カレンダーも対応版が必要です。

[取得・検証・索引共有手順](../docs/kumakogen-data.md)に従ってGit管理外データを配置してください。標準カタログ全体のパッケージングには他自治体の全データも必要です。一部自治体だけを一時カタログで検証した結果を、全自治体のLambda ZIPの完成として扱いません。今回AWSへのデプロイやTerraform操作は行っていません。

### 西条市データの同梱

[西条市データガイド](../docs/saijo-data.md)に従って、`saijo/registry.json`、`knowledge/items.csv`、`knowledge/item_embeddings.npz`、`knowledge/index_manifest.json`、`generated/calendar-2026.json`を配置します。追加AWSリソース・専用APIは不要です。随時収集の未確認区分は予定を作らず、他の確認済み区分は利用できます。ローカルの西条市単体ステージングと移設後のhealth・品目一覧・索引読込みを検証し、全カタログのステージングは他担当自治体の不足データにより停止することを確認しています。実AWSへのデプロイ・Linux/ARMでの実行・スマートフォンへの配布は行っていません。Flutterも同じ原本から対応版のデータを生成してください。

### 今治市データの同梱

[今治市データガイド](../docs/imabari-data.md)に従い、`imabari/registry.json`、`generated/calendar-2026.json`、`knowledge/mainland/`と`knowledge/sekizen/`それぞれの`items.csv`・`item_embeddings.npz`・`index_manifest.json`を配置します。`package_backend_data.py` は入れ子の2索引も同梱し、通常地域と関前のハッシュ・モデル・地区対応を検証します。PDF・OCR・API生ログは含めません。追加AWSリソース・API変更は不要です。

`backend/.venv/bin/python scripts/verify_imabari_package.py` は今治市単体の9実行時ファイルを一時フォルダへステージし、移設後のLambdaエントリーポイントのhealth・4プロフィールの品目一覧・2索引の読込みを無料で確認します。全自治体を含むパッケージは他メンバー担当の不足ファイルを配置してから検証してください。Linux/ARM・実AWSの動作や、スマートフォン配布は別確認です。Flutterも同じ版の台帳・カテゴリ・カレンダーが必要で、今回AWSへの変更は行っていません。
