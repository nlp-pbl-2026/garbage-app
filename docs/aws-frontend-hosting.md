# Flutter WebをS3＋CloudFrontで手動公開する

実装・ローカル検証までの変更です。AWS構築、Terraform apply、GitHub設定、本番アップロード・公開はまだ行っていません。以下の変更コマンドは内容確認後に操作者が実行します。

## 管理範囲

| パス | 用途 |
| --- | --- |
| `infra/frontend/bootstrap/` | Web専用のstateバケットを一度だけ新設 |
| `infra/frontend/` | Web専用S3、CloudFront、OAC、キャッシュ／ヘッダーポリシー、OIDCロール |
| `.github/workflows/deploy-frontend.yml` | mainからの`workflow_dispatch`だけで公開・復旧 |
| `scripts/build_frontend_release.py` | APIデータ検証、隔離コピーでのビルド、成果物ハッシュ作成 |
| `scripts/deploy_frontend.py` | 対象確認、世代配置、条件付き入口切替、公開検証・復旧 |

初期値はアカウント`088066169748`、東京リージョン、`Environment=dev`、`Project=U-22`。既存のLambda・API Gateway・S3・CloudFront、バックエンドTerraform・stateは変更しません。新しいstateとWebバケットを使い、通常のWeb公開ではTerraformを実行しません。

## 世代と公開の仕組み

1. バックエンド更新・確認後、操作者がmanifestの`dataset_version`を記録する。
2. `flutter_with_data.py`の既存処理で全20市町を取得し、ハッシュ・参照・有効期間・公開状態・指定版を検証する。
3. Flutter **3.47.1**、framework revision **6655482ec06e547f90abf8ae7590466f4415978d**に固定し、`--base-href=/releases/<世代ID>/ --no-web-resources-cdn`でビルドする。
4. `releases/<世代ID>/`へ条件付き新規作成し、全オブジェクトのSHA-256・サイズ・Content-Type・Cache-Controlを確認する。異なる内容で既存世代を上書きしない。
5. バックエンド版、CloudFront ETag、入口のETag／VersionIdを再確認する。
6. ルート`index.html`だけを`If-Match`（初回は`If-None-Match: *`）で切り替える。HTMLのbase hrefにより、起動JS・エンジン・カレンダー等は同じ世代から読み込まれる。
7. `/`と`/index.html`をinvalidateして完了待ちし、公開HTML・UIアセット・起動JSのハッシュとバックエンド版を検証する。

ルートHTMLは`no-cache,max-age=0,must-revalidate`、世代別ファイルは`public,max-age=31536000,immutable`。CloudFrontのminimum/default TTLは0。旧世代を保持し、公開済みタブの追加アセット取得に備えます。Flutter画面・API・ハッシュURL方式は維持し、404を一律HTMLへ変換しません。SDK内部の`.last_build_id`だけを成果物コピーから除外します。

インストール用Web manifestの`id`・`start_url`・`scope`は、成果物コピー内で`/`に固定します。インストール済みアプリも最新のルート入口を開き、古い世代URLへ起動先が固定されないための設定です。元の`frontend/web/manifest.json`は変更しません。

S3は全公開ブロック、ACL無効化、SSE-S3、versioningを有効にし、OAC署名付きのCloudFront読み取りだけをbucket policyで許可します。標準CloudFrontドメインを使い、独自ドメイン・ACM・S3 website endpointは不要です。

品目CSV・Embedding索引・原資料・環境変数・state・バックアップは公開しません。従来pubspecに含まれる`assets/choumei.csv`等のGit管理済みUIアセットは同梱します。資料の利用条件確認記録は未確認のまま別管理し、この処理で承認済みへ変更しません。

## 1. 初回AWS構築（AWSへの変更を伴う）

Terraform 1.10以上（検証版1.17.2）、AWS CLI v2、認証済み構築用アカウントを用意します。AWS providerは既存と同じ6.60系で、各rootのlockfileを追跡します。

構築には新規S3の作成・読み取り・タグ・公開ブロック・versioning・暗号化・ownership・bucket policy、CloudFront Distribution/OAC/cache policy/response headers policyの作成・読み取り・更新・タグ、専用IAMロールとinline policyの権限が必要です。OIDC新設時はその作成・タグ権限も必要。命名・Projectタグ・SCP等で拒否されたら理由を確認し、既存バックエンドのロールを書き換えて回避しないでください。

まずOIDCの既存登録を読み取りで確認します。

```bash
aws iam get-open-id-connect-provider \
  --open-id-connect-provider-arn arn:aws:iam::088066169748:oidc-provider/token.actions.githubusercontent.com
```

既存なら`create_github_oidc_provider=false`（data sourceで読むだけ）。明確にNoSuchEntityなら`true`にします。AccessDeniedを不存在と判断しません。subject例は2026年7月以降のimmutable owner/repository ID形式です。実際のsubjectと対象Environmentに一致させ、JWT全体をログへ出さないでください。

bootstrapは初期担当者1人だけが実行します。既存stateを流用しません。

```bash
terraform -chdir=infra/frontend/bootstrap init
terraform -chdir=infra/frontend/bootstrap plan \
  -var='aws_account_id=088066169748' -out=bootstrap.tfplan
# 新規Web stateバケット関連だけであることを確認してから実行
terraform -chdir=infra/frontend/bootstrap apply bootstrap.tfplan
```

bootstrapのローカルstateはGitに追加せず、初期担当者が暗号化した共有保管先等へバックアップします。他メンバーはbootstrapを繰り返さず、以後は共有stateでWebインフラを管理します。

```bash
cp infra/frontend/terraform.tfvars.example infra/frontend/terraform.tfvars
cp infra/frontend/backend.hcl.example infra/frontend/backend.hcl
# アカウント、リージョン、OIDC subjectと登録有無を編集・確認
terraform -chdir=infra/frontend init -backend-config=backend.hcl
terraform -chdir=infra/frontend plan -out=web.tfplan
# 新規Webリソースだけで、既存リソースの更新・削除がないことを確認
terraform -chdir=infra/frontend apply web.tfplan
mkdir -p .frontend-releases
terraform -chdir=infra/frontend output -json web_target > .frontend-releases/target.json
terraform -chdir=infra/frontend output -raw deploy_role_arn
terraform -chdir=infra/frontend output -raw web_url
```

Web・stateバケットは`force_destroy=false`かつ`prevent_destroy=true`。デプロイ用IAMロールはWebの指定オブジェクトのGet/Put、構成確認のGet、対象CloudFrontのinvalidationに限定します。DeleteObject・UpdateDistribution・stateアクセス・Lambda更新は許可しません。

## 2. stateの共同管理

`backend.hcl.example`の専用S3・`frontend/dev/terraform.tfstate`を共用し、SSE-S3・versioning・全公開ブロック・HTTPS限定とします。`use_lockfile=true`でS3ロックを使い、DynamoDBを追加しません。

インフラ運用者には`state-access-policy.example.json`相当の権限を別途付与します。stateはGet/Put、`.tflock`だけGet/Put/Delete。state本体のDeleteは不要です。ロック競合時は他メンバーの処理を確認し、無効化・force-unlock・S3でのロック削除を日常運用にしません。環境追加は別keyとリソース名で行い、Terraform workspaceとは混ぜません。

通常のGitHubデプロイ用ロールにはstate権限を与えません。

## 3. GitHub初期設定（今回未実施）

ワークフローをレビューしてmainへマージした後、以下を設定します。マージ自体では実行されません。

1. Actionsを利用可能にし、固定コミットの公式Actionsを許可する。
2. Environment **frontend-production**を作成し、デプロイbranchをmainだけに制限、required reviewerを指定する。OIDCがこのEnvironmentを信頼するため、この保護設定を先に行う。
3. Repository Variablesに`FRONTEND_API_BASE_URL`（既存のHTTPS API URL）を登録する。
4. Environment Variablesに`FRONTEND_TARGET_JSON`（`terraform output -json web_target`のJSON）と`FRONTEND_DEPLOY_ROLE_ARN`を登録する。

長期アクセスキーはSecretsへ登録しません。build jobはAWS認証なしでAPI取得し、Environment承認後のdeploy/rollback jobだけ`id-token: write`を持ちます。ワークフローはmainに限定し、公開直前にmainのSHAがビルド時から変わっていないことも確認します。

## 4. 通常の手動公開

1. 従来の安全な手順でバックエンドを更新・確認する。Web workflowはバックエンドを更新しない。
2. healthとmanifestを確認し、検証した`dataset_version`を記録する。実Bedrock評価は別途費用承認を得る。
3. Actions → **Deploy Flutter Web (manual)** → Run workflow、main、operation=`deploy`、`expected_dataset_version`に記録した64桁の値を指定する。
4. build成果物・版を確認してEnvironmentを承認する。
5. receiptの`status=verified`とCloudFrontの画面を確認する。地区選択・検索・追加質問・カレンダー・粗大ごみを確認し、実機確認は別途行う。

concurrency groupは全公開・復旧で共通、実行中の処理は新要求でcancelしません。別PC等からの更新はETag／VersionIdと条件付きPUTで検出します。AWS CLIにはIf-Match/If-None-MatchとSHA-256 checksum対応が必要です（ローカル確認版2.36.28）。

ローカル実行も、まず書き込みなしで確認します。

```bash
python3 scripts/build_frontend_release.py \
  --api-base-url 'https://<公開API>' --expected-dataset-version '<確認した64桁の版>' \
  --release-id '<一意の小文字英数字・ハイフンの世代ID>' --git-sha '<40桁のコミット>' \
  --output .frontend-releases/new-release
python3 scripts/deploy_frontend.py deploy --target .frontend-releases/target.json \
  --release .frontend-releases/new-release --api-base-url 'https://<公開API>' \
  --expected-dataset-version '<確認した64桁の版>'
```

確認後のみ、deployに`--execute --confirm-target '<account>:<region>:<bucket>:<distribution_id>' --receipt .frontend-releases/<新規receipt名>.json`を追加します。既存出力・receiptは上書きしません。

## 5. 失敗・復旧

- 配置中・版確認中の失敗では入口は切り替わらない。不完全な世代ファイルは残る場合があるが、ルートから参照されない。
- 公開検証の失敗は、自分の入口VersionId/ETagとCloudFront設定が不変な場合だけ以前の入口へ条件付きで戻す。初回で旧入口がなければ「公開準備中」へ戻す。
- 競合や応答不明は、他の入口を上書きせず停止する。`needs_review`/`restore_needs_review`のreceipt、現在のS3 VersionId、CloudFront設定を確認し、同じ書き込みを盲目的に繰り返さない。

過去世代へ戻す場合はRun workflowでoperation=`rollback`、戻す`rollback_release_id`、確認した現在の`current_release_id`、現バックエンドの版を指定して承認します。古いUI版と現API版が違えば停止します。必要なら従来の手順で先にバックエンドを復旧し、整合するWebを選びます。CSV/NPZ・カレンダー再生成は不要です。

読み取りだけでの再確認:

```bash
python3 scripts/deploy_frontend.py verify --target .frontend-releases/target.json \
  --release-id '<確認する世代ID>' --api-base-url 'https://<公開API>' \
  --expected-dataset-version '<現APIと一致する64桁の版>' \
  --receipt .frontend-releases/<新規verification名>.json
```

S3の過去version・世代は自動削除しません。掃除は稼働世代・復旧対象・開いているタブへの影響を確認して別途実施します。稼働世代を経過日数だけで消すLifecycleは設定しません。GitHub成果物とreceiptは30日保持し、実際の公開データはS3へ残ります。

## 費用・制約・未検証事項

従量CloudFront＋S3 Standardです。無料枠はアカウント共有のため利用可能量を別途確認します。無料枠を除外した日本向け参考計算は10 GB＋10万HTTPS requestsで約US$1.26、100 GB＋100万requestsで約US$12.60。S3の2バケットの保存・GET/PUT・過去version等は別途です。通常のinvalidationは2 pathsで、無料枠超過時は課金されます。Lambda／API Gateway／Bedrock費用は別で、既存5 req/sは月額上限ではありません。定額プラン・WAF等は追加していません。

ログインAPIのlocalhost固定、Webネイティブ通知未対応、iCalテキスト共有は今回変更しません。GPSはHTTPSとブラウザーの許可が必要です。住所表のない14市町は手動選択を維持し、確認済みカレンダー期間も延長しません。

VercelとCloudFrontは別オリジンです。ブラウザーに保存した地区・テーマ・申込記録等は新ドメインへ自動移行されず、位置情報の許可も新しく必要になります。旧ドメイン側の保存データは削除しません。利用者向け移行案内やデータのexport/import機能は今回追加していません。

今回追加するAWS workflowは手動だけですが、既存VercelのGit連携は別設定です。連携が残っている場合はpushによるVercelの自動公開が続く可能性があります。AWS側の公開確認後に、操作者がVercel側の自動デプロイ停止・接続解除を判断してください。今回Vercel設定は確認・変更していません。

実AWSの作成権限、OIDC AssumeRole、S3条件付きPUT、CloudFront配信・invalidation、実GitHub Actions実行は未検証です。ローカルの模擬成功を実環境の成功とは扱いません。

## ローカル検証結果（2026-11-14）

- Terraform 1.17.2 / AWS provider 6.60.0: Web・bootstrap両rootのinit（backend無効）とvalidateに成功。mock providerのplanテスト2件成功。実AWSのplan/applyや既存state操作はしていない。
- actionlint 1.7.12と、全6個のrunブロックの`bash -n`に成功。pushトリガーなし、main限定、Environment、OIDC権限、固定Action SHA、非cancelのconcurrencyを単体テストでも確認した。
- バックエンド単体／公式データ照合: **831成功、失敗0・スキップ0**。新しい公開／復旧テスト35件は合成データとメモリー上のS3を使い、書き込み禁止の既定値、対象違い、破損成果物、配置失敗、版変更、ETag競合、公開検証失敗、初回の準備中ページへの復旧、応答不明、他人の更新の維持、インストール用起動先を検証した。AWS HTTP送信を遮断して実行した。
- Git管理外CSV・カレンダーのないclone相当の隔離コピーで、公開APIから20市町を取得し、世代別パスのWebリリースビルドに成功。92ファイル・52,187,645 bytes、データ版`ef752bae576210807fedc7c2a57e190ebb80179cb058985254e01c0632475012`。元の自治体データや索引を再生成していない。
- 隔離Flutter環境は原本なしの218テスト成功。原本照合用の読み取り参照を追加した別段階では全334テスト成功。解析は既存62件（warning7・info55・error0）から追加・解消0件。WebビルドのCupertinoIcons案内は既存のもの。
- ルートHTML＋世代別ファイルをローカルHTTPで再現し、Headless Chromeで初期画面を視覚確認した。起動JS・Wasm・フォント等はすべて世代別URLから200で取得した。実検索・実機GPS／通知・AWS上の配信は今回未実施。有料モデル呼び出し0回。

テストの再実行例:

```bash
python -m pytest backend/tests/test_frontend_hosting.py
terraform -chdir=infra/frontend init -backend=false
terraform -chdir=infra/frontend validate
terraform -chdir=infra/frontend test
terraform -chdir=infra/frontend/bootstrap init
terraform -chdir=infra/frontend/bootstrap validate
terraform -chdir=infra/frontend/bootstrap test
actionlint .github/workflows/deploy-frontend.yml
```

Terraformのmockテストはplanのみで、AWS認証や実リソースは使いません。既存バックエンドのTerraformディレクトリでは実行しないでください。

参照: [S3 stateとlockfile](https://developer.hashicorp.com/terraform/language/backend/s3)、[S3条件付き書き込み](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)、[OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)、[GitHub手動実行](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)、[OIDC subject](https://docs.github.com/en/actions/reference/security/oidc)、[Flutter Web公開](https://docs.flutter.dev/deployment/web)、[CloudFront料金](https://aws.amazon.com/cloudfront/pricing/pay-as-you-go/)。
