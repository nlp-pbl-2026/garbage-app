# Flutter WebをS3＋CloudFrontで手動公開する

既定は**ローカルのAWS CLI認証による手動公開**です。OIDCやGitHub用IAMロールの作成・参照は行いません。将来Actionsへ移行する場合だけ明示的に有効化します。

対象アカウントでは2026-11-14にstate用bootstrapを構築済みです。Web本体・Webアプリは未公開で、今回の手動方式への変更ではAWSへの書き込みを行っていません。以下の変更コマンドは、別途承認・内容確認後に操作者が実行します。

## 管理範囲

| パス | 用途 |
| --- | --- |
| `infra/frontend/bootstrap/` | Web専用のstateバケットを一度だけ新設 |
| `infra/frontend/` | Web専用S3、CloudFront、OAC、キャッシュ／ヘッダーポリシー。Actions用IAMは任意 |
| `.github/workflows/deploy-frontend.yml` | 将来用に保持。mainからの`workflow_dispatch`だけで公開・復旧 |
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

構築にはWeb専用S3の作成・読み取り・タグ・公開ブロック・versioning・暗号化・ownership・bucket policy、CloudFront Distribution/OAC/cache policy/response headers policyの作成・読み取り・タグが必要です。通常公開にはWebオブジェクトのGet/GetVersion/Put、対象CloudFrontの参照・CreateInvalidation/GetInvalidationを使います。既存スクリプトのpreflightで必要な構成参照権限も維持してください。

現在の認証ではS3 bootstrap作成とCloudFront参照の実績がありますが、IAMシミュレーションがAccessDeniedのため、CloudFront作成・ファイル配置・invalidationの許可は未確定です。planの成功も作成権限の証明にはなりません。権限不足なら停止し、既存バックエンドや公開ブロックを変更して回避しません。

**このアカウントではbootstrapを繰り返さないでください。** 専用バケット`garbage-guide-web-state-088066169748-ap-northeast-1`と既存bootstrap state・バックアップをそのまま使用します。bootstrapのローカルstateは初期担当者がGit管理外で保持し、別PCからの再作成やWeb用stateへの混在を避けます。別アカウントで初めて構築する場合のみ、`infra/frontend/bootstrap/`のplanをレビューして新規作成します。

以下はWeb本体の初回構築です。既存の設定ファイルがあれば上書きせず確認します。認証は既存の`default`プロファイルを使い、OIDCの権限追加は不要です。

```bash
cp -n infra/frontend/terraform.tfvars.example infra/frontend/terraform.tfvars
cp -n infra/frontend/backend.hcl.example infra/frontend/backend.hcl
# アカウント、リージョン、state保存先、enable_github_actions=falseを確認
aws --profile default sts get-caller-identity
export AWS_PROFILE=default
terraform -chdir=infra/frontend init -backend-config=backend.hcl
terraform -chdir=infra/frontend validate
terraform -chdir=infra/frontend plan -out=web-initial.tfplan
```

新規Web関連10件のみ、変更・削除0件、IAM/OIDCの参照・作成なしを確認します。既存Web stateがある場合の件数は異なるため、個々の差分を確認します。**レビューと別途承認後にのみ**、保存したplanを適用します。

```bash
terraform -chdir=infra/frontend apply web-initial.tfplan
terraform -chdir=infra/frontend output -raw web_url
```

S3 backendのinit・planでは専用stateやロックへの書き込みが発生し得るため、読み取り専用の調査中には実行しません。planは新しい出力名を使い、既存planを上書きしません。Web・stateバケットの`force_destroy=false`と`prevent_destroy=true`は維持しています。

`enable_github_actions=false`ではOIDCのdata source、OIDCリソース、GitHub用IAMロール・inline policyはすべて0件です。`github_oidc_subject`も不要で、`deploy_role_arn`はnull（outputには表示されない）です。`web_target`とビルド・公開・復旧のデータ形式は同じです。

## 2. stateの共同管理

`backend.hcl.example`の専用S3・`frontend/dev/terraform.tfstate`を共用し、SSE-S3・versioning・全公開ブロック・HTTPS限定とします。`use_lockfile=true`でS3ロックを使い、DynamoDBを追加しません。

インフラ運用者には`state-access-policy.example.json`相当の権限を別途付与します。stateはGet/Put、`.tflock`だけGet/Put/Delete。state本体のDeleteは不要です。ロック競合時は他メンバーの処理を確認し、無効化・force-unlock・S3でのロック削除を日常運用にしません。環境追加は別keyとリソース名で行い、Terraform workspaceとは混ぜません。

通常のGitHubデプロイ用ロールにはstate権限を与えません。

## 3. 将来GitHub Actionsへ移行する場合（現在は保留）

ローカル公開だけならGitHub設定は不要です。既存workflowは手動実行のみで保持しますが、IAMロール未構築の間は実行しません。将来は同じWebリソース・state・世代データを使って移行できます。

1. Actionsを利用可能にし、固定コミットの公式Actionsを許可する。
2. Environment **frontend-production**をmainブランチのみに制限し、保護を確認してからOIDCロールを構築する。Required reviewersは任意。設定しない場合、workflowの手動起動後はビルドから公開まで承認待ちなく進む。
3. `iam:GetOpenIDConnectProvider`で既存登録・audienceを確認する。登録済みなら`create_github_oidc_provider=false`、明確にNoSuchEntityの場合だけ`true`を検討する。AccessDeniedを不存在と判断しない。
4. `enable_github_actions=true`と完全一致の`github_oidc_subject`を設定する。例は`terraform.tfvars.example`を参照。subjectのimmutable owner/repository IDを確認し、JWT全体はログへ出さない。
5. 同じWeb用stateでplanし、既存Webリソースが維持され、Actions用IAMだけが追加されることを確認して別途承認後にapplyする。
6. Repository Variablesの`FRONTEND_API_BASE_URL`、Environment Variablesの`FRONTEND_TARGET_JSON`と`FRONTEND_DEPLOY_ROLE_ARN`を登録する。後者のARNは有効化後の`terraform output -raw deploy_role_arn`から取得する。

既に旧版でActions用IAMを管理しているstateでは`enable_github_actions=true`を明示してください。`migrations.tf`が旧ロール・policyのアドレスをcount付きへ移し、再作成を避けます。作成済みロール・OIDCを無効化して削除する変更は`prevent_destroy`で停止します。自動削除を解除せず、必要なら別途レビューします。今回、既存stateの移行・編集はしていません。

長期アクセスキーはGitHubへ登録しません。build jobはAWS認証なし、deploy/rollback jobだけOIDCを使用します。main限定・公開前のmain SHA確認・共通concurrencyは維持します。

## 4. ローカルからの手動公開

1. 従来の安全な手順でバックエンドを更新・確認する。Webスクリプトはバックエンドを変更しない。
2. healthとmanifestを確認し、確認した64桁の`dataset_version`を記録する。実Bedrock評価は別途費用承認を得る。
3. 公開するコミットのclean checkoutでビルドする。未コミット変更がある作業場所は保持し、別worktree等を使う。Flutter 3.47.1を用意する。
4. 対象アカウント・リージョン・bucket・distributionを確認し、まずdry-runする。
5. 別途承認後に`--execute`で公開し、receiptの`status=verified`と実画面を確認する。

ローカル・別PC・将来のActionsからの競合はETag／VersionIdと条件付きPUTで検出します。ローカル実行ではActionsのconcurrency待ちはないため、構築用Terraform操作や他の公開と事前に調整します。AWS CLIにはIf-Match/If-None-MatchとSHA-256 checksum対応が必要です（確認版2.36.28）。

以下はリポジトリrootで実行します。`set -eu`で途中の失敗時に停止するシェルを使い、作業フォルダが既にあれば先へ進みません。`--profile default`は既存認証を利用し、GitHub用IAMロール・OIDCの作成・参照を必要としません。`--profile`省略時はAWS CLIの通常の認証チェーンです。

```bash
set -eu
FRONTEND_AWS_PROFILE=default
API_BASE_URL='https://<公開API>'
DATASET_VERSION='<確認した64桁の版>'
RELEASE_ID="manual-$(date -u +%Y%m%d-%H%M%S)"
RUN_DIR=".frontend-releases/$RELEASE_ID"
mkdir -p .frontend-releases
mkdir "$RUN_DIR"
aws --profile "$FRONTEND_AWS_PROFILE" sts get-caller-identity
AWS_PROFILE="$FRONTEND_AWS_PROFILE" terraform -chdir=infra/frontend output -json web_target > "$RUN_DIR/target.json"
python3 scripts/build_frontend_release.py \
  --api-base-url "$API_BASE_URL" --expected-dataset-version "$DATASET_VERSION" \
  --release-id "$RELEASE_ID" --git-sha "$(git rev-parse HEAD)" --output "$RUN_DIR/release"
python3 scripts/deploy_frontend.py deploy --target "$RUN_DIR/target.json" \
  --release "$RUN_DIR/release" --api-base-url "$API_BASE_URL" \
  --expected-dataset-version "$DATASET_VERSION" --profile "$FRONTEND_AWS_PROFILE" \
  --receipt "$RUN_DIR/dry-run.json"
```

dry-runは構成・版の読み取り確認であり、PutObject／CreateInvalidationの許可を保証しません。確認・承認後のみ、同じdeployコマンドのreceiptを`"$RUN_DIR/deploy.json"`に変え、`--execute --confirm-target '<account>:<region>:<bucket>:<distribution_id>'`を追加します。既存出力・receiptを上書きせず、AccessDeniedなら停止します。デプロイ後に地区選択・検索・追加質問・カレンダー・粗大ごみを画面から確認します。

スクリプトは指定WebオブジェクトのPutObjectとinvalidationだけを書き込み対象にします。ローカル認証が広い権限を持っていても、IAM・Lambda・削除操作は呼びません。新しいアクセスキーを設定する必要はありません。

## 5. 失敗・復旧

- 配置中・版確認中の失敗では入口は切り替わらない。不完全な世代ファイルは残る場合があるが、ルートから参照されない。
- 公開検証の失敗は、自分の入口VersionId/ETagとCloudFront設定が不変な場合だけ以前の入口へ条件付きで戻す。初回で旧入口がなければ「公開準備中」へ戻す。
- 競合や応答不明は、他の入口を上書きせず停止する。`needs_review`/`restore_needs_review`のreceipt、現在のS3 VersionId、CloudFront設定を確認し、同じ書き込みを盲目的に繰り返さない。
- 復旧後も公開HTMLのハッシュ、入口VersionId／ETag、CloudFront ETagを再確認する。復旧の検証中に別の更新が入った場合は、復旧完了とは報告せず`restore_needs_review`で止め、追加の上書きをしない。

過去世代への復旧も同じローカル認証を使います。まず次のコマンドを`--execute`なしで確認します。

```bash
python3 scripts/deploy_frontend.py rollback --target "$RUN_DIR/target.json" \
  --release-id '<戻す世代ID>' --expected-current-release-id '<確認した現世代ID>' \
  --api-base-url "$API_BASE_URL" --expected-dataset-version "$DATASET_VERSION" \
  --profile "$FRONTEND_AWS_PROFILE" --receipt "$RUN_DIR/rollback-dry-run.json"
```

承認後のみ新規receipt名と`--execute --confirm-target '<account>:<region>:<bucket>:<distribution_id>'`を指定します。古いUI版と現API版が違えば停止します。必要なら従来の手順で先にバックエンドを復旧し、整合するWebを選びます。CSV/NPZ・カレンダー再生成は不要です。将来のActionsではoperation=`rollback`で同じ処理を実行します。

読み取りだけでの再確認:

```bash
python3 scripts/deploy_frontend.py verify --target "$RUN_DIR/target.json" \
  --release-id '<確認する世代ID>' --api-base-url 'https://<公開API>' \
  --expected-dataset-version '<現APIと一致する64桁の版>' \
  --profile "$FRONTEND_AWS_PROFILE" --receipt "$RUN_DIR/verification.json"
```

`verify`は入口のS3 checksum・キャッシュ設定と公開ファイルを照合し、公開検証の前後でバックエンド版を確認します。途中で版や入口が変わった場合は成功扱いにせず、AWSへの書き込みもしません。初回構築と異なるパス別behavior、エッジ関数、独自エラーページ、署名付き閲覧等が追加されていた場合も、deploy／rollback／verifyの事前確認で停止します。意図した構成変更なら、先にTerraform・この検証・手順書を一緒にレビューしてください。

S3の過去version・世代は自動削除しません。掃除は稼働世代・復旧対象・開いているタブへの影響を確認して別途実施します。稼働世代を経過日数だけで消すLifecycleは設定しません。GitHub成果物とreceiptは30日保持し、実際の公開データはS3へ残ります。

## 費用・制約・未検証事項

従量CloudFront＋S3 Standardです。無料枠はアカウント共有のため利用可能量を別途確認します。無料枠を除外した日本向け参考計算は10 GB＋10万HTTPS requestsで約US$1.26、100 GB＋100万requestsで約US$12.60。S3の2バケットの保存・GET/PUT・過去version等は別途です。通常のinvalidationは2 pathsで、無料枠超過時は課金されます。Lambda／API Gateway／Bedrock費用は別で、既存5 req/sは月額上限ではありません。定額プラン・WAF等は追加していません。

ログインAPIのlocalhost固定、Webネイティブ通知未対応、iCalテキスト共有は今回変更しません。GPSはHTTPSとブラウザーの許可が必要です。住所表のない14市町は手動選択を維持し、確認済みカレンダー期間も延長しません。

VercelとCloudFrontは別オリジンです。ブラウザーに保存した地区・テーマ・申込記録等は新ドメインへ自動移行されず、位置情報の許可も新しく必要になります。旧ドメイン側の保存データは削除しません。利用者向け移行案内やデータのexport/import機能は今回追加していません。

今回追加するAWS workflowは手動だけですが、既存VercelのGit連携は別設定です。連携が残っている場合はpushによるVercelの自動公開が続く可能性があります。AWS側の公開確認後に、操作者がVercel側の自動デプロイ停止・接続解除を判断してください。今回Vercel設定は確認・変更していません。

実AWSの作成権限、OIDC AssumeRole、S3条件付きPUT、CloudFront配信・invalidation、実GitHub Actions実行は未検証です。ローカルの模擬成功を実環境の成功とは扱いません。

## 初回実装時のローカル検証結果（2026-11-14）

- Terraform 1.17.2 / AWS provider 6.60.0: Web・bootstrap両rootのinit（backend無効）とvalidateに成功。mock providerのplanテスト2件成功。実AWSのplan/applyや既存state操作はしていない。
- actionlint 1.7.12と、全6個のrunブロックの`bash -n`に成功。pushトリガーなし、main限定、Environment、OIDC権限、固定Action SHA、非cancelのconcurrencyを単体テストでも確認した。
- バックエンド単体／公式データ照合: **831成功、失敗0・スキップ0**。新しい公開／復旧テスト35件は合成データとメモリー上のS3を使い、書き込み禁止の既定値、対象違い、破損成果物、配置失敗、版変更、ETag競合、公開検証失敗、初回の準備中ページへの復旧、応答不明、他人の更新の維持、インストール用起動先を検証した。AWS HTTP送信を遮断して実行した。
- Git管理外CSV・カレンダーのないclone相当の隔離コピーで、公開APIから20市町を取得し、世代別パスのWebリリースビルドに成功。92ファイル・52,187,645 bytes、データ版`ef752bae576210807fedc7c2a57e190ebb80179cb058985254e01c0632475012`。元の自治体データや索引を再生成していない。
- 隔離Flutter環境は原本なしの218テスト成功。原本照合用の読み取り参照を追加した別段階では全334テスト成功。解析は既存62件（warning7・info55・error0）から追加・解消0件。WebビルドのCupertinoIcons案内は既存のもの。
- ルートHTML＋世代別ファイルをローカルHTTPで再現し、Headless Chromeで初期画面を視覚確認した。起動JS・Wasm・フォント等はすべて世代別URLから200で取得した。実検索・実機GPS／通知・AWS上の配信は今回未実施。有料モデル呼び出し0回。

## 最終レビュー（2026-11-14）

- 再確認時のバックエンド版変更を見逃す可能性、想定外のCloudFront routing／エッジ処理を受け入れる可能性、復旧検証中の競合を完了扱いにする可能性を修正した。AWSの操作許可やIAM権限は増やしていない。
- Environmentのmain制限・reviewer設定をWeb用IAMロール作成より前に行うよう、初期構築の順序を明確にした。
- バックエンド全体は**851成功・失敗0・スキップ0**（既存warning21件）。うち公開・復旧テストは**55成功**。AWS HTTP送信を遮断して実行した。
- Terraformは両rootのvalidateとmock plan **4件成功**で、正常構成に加え、wildcard subjectとEnvironmentなしのsubjectの拒否を検証した。actionlint・全6個のrunブロックの`bash -n`も成功した。
- 隔離コピーでFlutterの`test`＋`tool` **334件成功**。静的解析は既存62件（warning7・info55・error0）と完全に同じで、追加指摘0件だった。元の未コミット設定は使わず、原本照合は読み取り参照で行った。
- 前回の隔離Webビルド成果物92ファイル・52,187,645 bytesを現在の検証処理で再照合した。今回はFlutterソース・ビルド処理を変更しておらず、新しいWebビルドや実AWS公開テストは行っていない。

## ローカル手動方式への対応（2026-11-14）

- `enable_github_actions=false`を既定とし、OIDCの参照・作成とGitHub用IAMロールを任意化した。ビルド・公開スクリプトの動作、安全チェック、Web用リソースと共有stateの構成は維持した。
- 実際のAWS認証で、**S3 backendを除いた新規の隔離コピー**のplanに成功した。追加10・変更0・削除0で、IAMの参照・作成はない。これはローカルbackendによる構造検証であり、本番共有stateのplanや適用用planではない。既存のstate・ロックへの書き込みは行っていない。
- Terraform validate、Webのmock plan 8件とbootstrapのmock plan 1件に成功。手動／Actions両モード、subject・provider opt-inの制約を確認した。旧Actions実stateの移行は未実施・未検証なので、既存stateを使う際は差分を必ず確認する。
- AWS HTTP送信を遮断したバックエンド全体は**854成功・失敗0・スキップ0**（既存warning21件）。公開・復旧テストは**58成功**で、既存認証・名前付きprofile・ローカルCLIのdry-runを追加検証した。
- actionlintと手順書のシェル構文検査に成功。Flutterコードとビルド・デプロイスクリプトは変更していない。前回の隔離Webビルド92ファイルを再照合し、新しいFlutterビルド・全テストは再実行していない。
- 実際のCloudFront作成、S3ファイル配置、invalidationの権限・動作は未検証。構築済みbootstrap state・バックアップ・全自治体データは保持し、今回AWSへの書き込み・有料モデル呼び出しは0回。

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
