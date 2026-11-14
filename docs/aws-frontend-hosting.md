# Flutter WebのAWS公開・更新手順

## 現在の運用

Web専用S3＋CloudFrontの初回構築とFlutter Webの初回公開は完了しています。**通常更新はローカルのAWS CLI認証で行い、Terraform applyやbootstrapの再実行は不要です。** GitHub Actionsは将来用として保持していますが、現在は使用しません。mainへのpush・マージでAWSへ自動公開しません。

| 項目 | 現在の公開先 |
| --- | --- |
| Web | https://d1up4ijatag29i.cloudfront.net |
| アカウント／リージョン | `088066169748` / `ap-northeast-1` |
| Web専用S3 | `garbage-guide-web-dev-088066169748-ap-northeast-1` |
| CloudFront | `E39F2A660XV8UP` |
| API | https://620bktqeq9.execute-api.ap-northeast-1.amazonaws.com |
| Web専用state | `s3://garbage-guide-web-state-088066169748-ap-northeast-1/frontend/dev/terraform.tfstate` |

初回公開では全20市町・43プロフィールのUIデータを取得し、93世代別ファイル＋入口HTMLの計94オブジェクトを配置しました。receiptは`verified`、CloudFront invalidationは`Completed`、公開HTTP 200と初期画面を確認済みです。時刻はUTCで2026-11-14、日本時間では2026-11-15です。通常のprepareでは過去のデータ版を固定せず、選択したAPIから現在の版を取得・検証します。

## 1. メンバーの事前準備（初回のみ）

Python 3.10以上、Git、AWS CLI v2、Flutter **3.47.1**（revision **6655482ec06e547f90abf8ae7590466f4415978d**）をPATHへ設定します。公開用コマンドはPython標準ライブラリだけで動き、backendのvenv・自治体CSV・NPZ・カレンダー原本・Terraformは不要です。必要なUIデータはAPIから取得します。AWS CLIは条件付きPUTとSHA-256 checksum対応版を使います（初回確認版2.36.28）。

```bash
aws login  # ログイン方式を利用している場合。既存の認証方式は変更しない
aws --profile default sts get-caller-identity
flutter --version
```

通常の公開権限はWeb専用バケットと対象Distributionに限定します。構築用IAMやstateへのアクセスは通常更新には不要です。

| 対象 | スクリプトが使う権限 |
| --- | --- |
| 認証主体 | `sts:GetCallerIdentity` |
| Webバケット構成 | `s3:GetBucketLocation`, `s3:GetBucketTagging`, `s3:GetBucketVersioning`, `s3:GetBucketPublicAccessBlock`, `s3:GetEncryptionConfiguration`, `s3:GetBucketOwnershipControls`, `s3:GetBucketPolicyStatus` |
| Webオブジェクト | `s3:GetObject`, `s3:GetObjectVersion`, `s3:PutObject`（`releases/*`と`index.html`） |
| CloudFront参照 | `cloudfront:GetDistribution`, `cloudfront:ListTagsForResource`, `cloudfront:GetOriginAccessControl`, `cloudfront:GetCachePolicy` |
| CloudFront反映 | 対象Distributionの`cloudfront:CreateInvalidation`, `cloudfront:GetInvalidation` |

`ListBucket`はスクリプトでは列挙しませんが、初回の不存在オブジェクトに対するHEADで404を得るため、対象Webバケットに必要です。権限不足なら停止し、公開ブロックの解除や長期アクセスキーの追加で回避しません。dry-run成功だけではPutObject／CreateInvalidation権限の証明になりません。

### 公開先を一度だけ保存する

構築担当者から`terraform output -json web_target`の保存済み`target.json`を受け取ります。対象アカウント・リージョン・Webバケット・Distribution・所有タグを担当者と照合してください。stateを初期化済みの構築担当者だけが、このoutputを取得します。通常担当者がTerraform init/applyを行う必要はありません。

現在のtargetの内容（秘密情報は含みません）:

```json
{
  "account": "088066169748",
  "region": "ap-northeast-1",
  "bucket": "garbage-guide-web-dev-088066169748-ap-northeast-1",
  "distribution_id": "E39F2A660XV8UP",
  "environment": "dev",
  "project_tag": "U-22"
}
```

リポジトリルートで次を実行します。`--target`は受け取ったファイルのパスに置き換えます。

```bash
python3 scripts/frontend.py configure --target /path/to/target.json \
  --api-base-url https://620bktqeq9.execute-api.ap-northeast-1.amazonaws.com \
  --profile default
```

Git除外済みの`.frontend-releases/deploy-config.json`へ保存します。既存設定は上書きしません。別環境の設定を作る場合は新しい`--config`パスを指定し、prepareにも同じパスを指定します。AWS認証情報は保存せず、profile名だけ記録します。`--profile`省略時は既存AWS認証チェーンを使います。公開先を他のAWSリソースから自動推定したり、スクリプト内へ本番IDを埋め込んだりしません。

## 2. 通常の更新：準備 → 確認 → 公開

先に[バックエンドの更新・検証](lambda-s3-deploy.md)を完了させます。WebのスクリプトはLambda・API Gatewayを変更しません。GitHubへマージ済みのmainだけを公開します。

### 準備・dry-run（AWSへ書き込まない）

```bash
git fetch origin main
python3 scripts/frontend.py prepare
```

prepareは次を行います。

1. `git ls-remote`と`origin/main`のSHA一致を確認。古ければ停止し、ブランチ切り替えや自動マージはしない。
2. AWSアカウント・リージョン・タグ・S3非公開設定・OAC・CloudFront構成・現在の入口を読み取り検証する。
3. 公開APIのhealth・manifestを確認し、現在の`dataset_version`を取得する。
4. mainのGit管理済みビルド入力だけを新しい`.frontend-releases/manual-.../source/`へ取り出す。未コミット変更・Git管理外データ・バックエンド索引をビルドへ持ち込まない。
5. 既存の`build_frontend_release.py`で全20市町を取得・検証し、隔離ビルドする。バージョン・ハッシュ・自治体／地区参照・日付範囲・未確認日・公開状態のチェックを維持する。
6. 同じmainの`deploy_frontend.py`をdry-runで実行し、準備中にmain・API版・入口・CloudFrontが変わっていないことを再確認する。

`deployment-ready.json`、`target.json`、ビルド成果物、ログ、`dry-run/receipt.json`を新しい実行フォルダへ保存します。既存の作業・state・バックアップは触りません。API取得やビルドはBedrockを呼びません。ビルド途中で失敗したフォルダも診断用に保持し、準備が完了していない成果物は公開しません。

### 表示された実行フォルダを指定して公開する

```bash
python3 scripts/frontend.py deploy .frontend-releases/manual-... --execute
```

画面のAWSアカウント・リージョン・bucket・Distribution・API・main SHA・データ版を確認し、`deploy`と入力します。`--execute`と対話確認が揃うまでAWSへ書き込みません。CloudFront IDやデータ版を再入力する必要はなく、確認後に検証済みの宛先トークンを既存スクリプトへ渡します。`--execute`を省略した場合は、もう一度dry-runするだけです。

TTYを使えない手動運用では、表示内容の確認後に`--confirm-target '<account>:<region>:<bucket>:<distribution_id>'`を明示できます。`--yes`相当の宛先確認省略はありません。GitHub Actionsには接続しません。

prepare後にmain・API版・公開先・入口が変わった場合は停止し、確認後に新しくprepareします。成果物とビルド入力のハッシュも照合します。公開先はreadyに保存された設定を使い、その後のconfig変更を既存の準備へ混ぜません。

書き込み開始前に`deploy-started.json`を排他的に保存します。同じ実行フォルダからの書き込みは1回だけです。各呼び出しには新しいログ・終了コード・receipt保存先を作り、過去の記録を上書きしません。公開成功は子スクリプトのreceiptの`status=verified`で確認します。

```bash
# 公開後の再検証。読み取りのみ。毎回新しいreceiptを残す
python3 scripts/frontend.py verify .frontend-releases/manual-...
```

ブラウザで地域選択、検索・追加質問、カレンダー・次回収集日、粗大ごみ案内を確認してください。実検索は従来どおりBedrock料金が発生します。

## 3. 失敗時の確認・復旧

1. まず実行フォルダの`*-started.json`、各`command.log`、`result.json`、`receipt.json`を確認する。入口切替前の失敗では子スクリプトのreceiptがない場合があり、ログと終了コードを見る。
2. アップロード途中の失敗では不完全な世代が残る場合があるが、入口は切り替わらない。入口切替後に検証が失敗した場合は、既存スクリプトが自分の入口とCloudFront設定が不変な場合だけ条件付きで旧入口へ戻す。
3. `entry_restored`は旧入口への復旧済み、`needs_review`／`restore_needs_review`は要調査。応答不明・競合時に同じ書き込みを盲目的に繰り返さない。マーカーやreceiptを消して再実行しない。
4. 更新自体が成功した可能性がある場合は`frontend.py verify <実行フォルダ>`で読み取り検証を再開する。旧receiptは変更せず、新しい検証receiptを残す。他人の更新・API版変更は成功扱いにしない。

その実行より前の世代へ明示的に戻す場合:

```bash
# まず読み取り検証のみ。readyに記録した旧世代へ戻せるか確認
python3 scripts/frontend.py rollback .frontend-releases/manual-...
# 内容確認後、対話確認でrollbackと入力して実行
python3 scripts/frontend.py rollback .frontend-releases/manual-... --execute
```

現在の公開世代がそのreadyの世代と一致し、旧世代のデータ版が現APIと一致する場合だけ戻せます。初回公開など旧世代がない場合、この簡略コマンドは停止します。復旧の書き込みも同じフォルダから1回に限定します。自動復旧で既に旧世代へ戻っている場合は重ねて書き込みません。

別の保存世代の確認や、簡略コマンド導入前の初回公開の検証には、既存の低レベルコマンドを使えます。必ず新しいreceipt名を指定してください。

```bash
python3 scripts/deploy_frontend.py verify --target /path/to/target.json \
  --release-id '<確認した世代ID>' --api-base-url 'https://<公開API>' \
  --expected-dataset-version '<現APIと一致する64桁の版>' \
  --profile default --receipt .frontend-releases/verification-new.json
```

任意世代への`deploy_frontend.py rollback`には`--release-id`と`--expected-current-release-id`が必須です。既定はdry-run、実行は`--execute --confirm-target`が必要です。API版が一致しない旧Webへ無理に戻さず、必要ならバックエンドも別手順で整合させます。

S3の旧世代・過去versionは自動削除しません。開いているタブ・復旧対象への影響を確認して別作業で整理します。`.frontend-releases/`のready・receipt・ログ・設定はGit管理外として保護し、担当者間で必要な記録を安全に共有します。認証情報・state・バックアップをWebバケットへ置かないでください。

## 4. 配置・キャッシュ・安全チェック

- 既存の`deploy_frontend.py`が世代別`releases/<ID>/`へ条件付き新規作成し、全ファイルのSHA-256・サイズ・Content-Type・Cache-Controlを確認する。
- API版・CloudFront ETag・入口ETag／VersionIdを再確認して、入口`index.html`だけをIf-Match（初回はIf-None-Match）で切り替える。他の操作者の更新を上書きしない。
- `/`と`/index.html`をinvalidateし、完了を待って公開HTML・UIデータ・起動JSのハッシュとAPI版を照合する。構成・入口の途中変更も検出する。
- 入口HTMLは`no-cache,max-age=0,must-revalidate`、世代別ファイルは`public,max-age=31536000,immutable`。HTMLのbase hrefで同じ世代のアセットを読む。Web manifestのid/start_url/scopeは`/`とし、インストール済みアプリの起動先を旧世代に固定しない。
- S3は全公開ブロック、ACL無効、SSE-S3、versioningを維持し、OAC署名付きCloudFrontからだけ配信する。404を一律HTMLへ置換しない。
- CSV・Embedding索引・原資料・環境変数・stateは公開しない。既存pubspecのGit管理済みUIアセット（`assets/choumei.csv`等）は引き続き同梱する。

ローカルの多重起動はマーカーで拒否し、別PC／別prepareからの競合は既存のETag／VersionIdと条件付きPUTで検出します。Terraform操作や他メンバーのデプロイとは事前に調整してください。

## 5. Terraform stateの管理（通常公開とは別）

| パス | 管理対象 |
| --- | --- |
| `infra/frontend/bootstrap/` | 構築済みWeb専用stateバケット6リソース、bootstrapローカルstate |
| `infra/frontend/` | Web専用S3、CloudFront、OAC、キャッシュ／ヘッダーポリシー等10リソース |
| `infra/terraform/` | 既存バックエンド。Webの作業対象外 |

Web本体は専用S3 backendの同じbucket/keyを共同利用します。SSE-S3・versioning・全公開ブロック・HTTPS限定、`use_lockfile=true`のS3ロックを維持します。別メンバーが新しい空のstateで既存Webリソースを作り直さないでください。環境追加は別keyとリソース名で行い、workspaceとは混在させません。

`backend.hcl.example`はTerraform 1.17.2のS3 backendが受け付ける`allowed_account_ids`を使います。未対応の`expected_bucket_owner`を除き、stateのbucket/key/region・暗号化・ロックは変えていません。これは認証先アカウントの制限であり、S3 APIのExpectedBucketOwnerと同じ機能ではありません。バケットの所有者は構築時の確認記録・専用ポリシーでも確認します。既存の正しく初期化済みローカル設定やstateは変更・移行不要です。

インフラ担当者の権限は`state-access-policy.example.json`を参照します。stateはGet/Put、`.tflock`だけGet/Put/Deleteで、state本体のDeleteは不要です。競合時は他メンバーを確認し、force-unlockやロック削除で回避しません。

bootstrapのローカルstateは初期構築担当者がGit管理外でバックアップを保持します。共有Web stateとは混ぜません。Web stateのバックアップは新しい名前へ`terraform state pull`で保存し、S3 VersionIdも記録します。既存バックアップは上書きせず、権限を制限した共有先で管理します。通常公開スクリプトはTerraformを一切呼びません。

### 別環境の初回構築・既存環境の構成変更

このアカウントのbootstrapとWeb本体は構築済みです。以下は新環境だけの参考手順です。構築時はS3・CloudFrontの作成／設定／タグ／ポリシー操作が別途必要です。plan成功を作成権限の証明にしません。

```bash
cp -n infra/frontend/terraform.tfvars.example infra/frontend/terraform.tfvars
cp -n infra/frontend/backend.hcl.example infra/frontend/backend.hcl
# bucket/key/account/regionとenable_github_actions=falseを環境ごとに確認
export AWS_PROFILE=default
terraform -chdir=infra/frontend init -backend-config=backend.hcl
terraform -chdir=infra/frontend validate
terraform -chdir=infra/frontend plan -out=web-new.tfplan
# 差分の確認・承認後だけ実行（通常公開では実行しない）
terraform -chdir=infra/frontend apply web-new.tfplan
terraform -chdir=infra/frontend output -json web_target
```

未構築の別アカウントでstateバケットが必要な場合だけ、先に`bootstrap/`の6新規リソースのplanをレビューして構築します。構築済みリソースの再作成、既存stateの移行・上書きは行いません。初回の手動モードはWeb関連10追加・変更削除0件、IAM/OIDCなしです。既存環境の構成変更はそのstateの実際の差分を優先します。各rootのlockfileはGit管理し、バケットの`force_destroy=false`／`prevent_destroy=true`を維持します。

### 将来GitHub Actionsへ移行する場合（現在は保留）

`.github/workflows/deploy-frontend.yml`はmainからの`workflow_dispatch`だけを許可します。ローカル公開にOIDCやGitHub用IAMは不要です。移行時はEnvironment `frontend-production`のmain制限を確認し、既存OIDC providerをGetで確認後、同じWeb stateで`enable_github_actions=true`をplanします。既存Webリソースを保ち、IAM追加だけかをレビューします。AccessDeniedをprovider未登録と判断しません。明確に未登録と確認した場合だけprovider作成を検討します。

完全一致の`github_oidc_subject`（immutable owner/repository IDを含む）とaudienceを使い、長期アクセスキーをGitHubへ保存しません。Required reviewersは任意で、未設定なら手動起動後に追加の承認待ちはありません。`FRONTEND_API_BASE_URL`、`FRONTEND_TARGET_JSON`、`FRONTEND_DEPLOY_ROLE_ARN`を設定してから運用します。buildにはAWS認証なし、deploy/rollbackだけOIDC、共通concurrencyを維持します。通常のデプロイロールにはstate権限を与えません。

旧Actionsロールを管理するstateでは`enable_github_actions=true`を明示します。`migrations.tf`のアドレス移行を確認し、既存ロール・OIDCの削除をprevent_destroy解除で回避しません。Vercelの既存Git連携はAWS workflowと別で、停止・切り替えは操作者が判断します。

## 制約・今後の確認事項

- 検索から結果表示までが以前より遅く感じられるとの報告あり。今回性能変更は行わず、後日ブラウザ計測、API／モデル処理時間、コールドスタート等を分けて調査する。
- Webネイティブ通知は未対応、Web iCalはテキスト共有。ログインAPIのlocalhost固定も残る。スマートフォン実機でのGPS・通知・iCalは別途確認が必要。
- GPSはHTTPSとブラウザ許可が必要。住所表のある6市町のみ候補を提示し、他14市町は手動選択する。
- 砥部町は2026-12-06、愛南町・鬼北町・内子町は2026-12-31までのデータ。取得・再ビルドで有効期間や未確認日を延長／確定しない。
- バックエンド変更後は対応するWeb更新が必要。開いたままの旧タブは自動更新されず、検索時の版不一致は409で停止する。
- VercelとCloudFrontは別オリジンで、保存済み地域・設定・GPS許可は自動移行しない。
- 資料の利用・再配布条件は全20市町とも別管理の未確認記録を維持する。公開判断を許諾確認済みと扱わない（[確認記録](frontend-data-setup.md#利用再配布条件の確認記録)）。
- 費用はS3保存・リクエスト・過去version、CloudFront転送・リクエスト・invalidation。無料枠はアカウント共有で確認する。API Gateway／Lambda／Bedrock料金は別で、スロットリングは請求額上限ではない。旧世代は自動削除せず、保管量も監視する。

## ローカル検証

```bash
python -m pytest backend/tests/test_frontend_operator.py backend/tests/test_frontend_hosting.py
```

Terraformは**stateやローカル設定を含まない隔離コピー**で`init -backend=false`、`validate`、mock providerの`test`を行います。bootstrapも同様です。mock testはplanのみで実AWSを変更しません。実環境のapply、S3配置、invalidation、実Bedrock、Actionsは保守変更の検証として実行しません。

### 運用整理時の確認（2026-11-15）

- バックエンド全体769件成功、失敗・スキップ0件（既存の非推奨警告21件）。外部ネットワークを遮断し、有料APIは使用していません。既存venvの不足・版違いは、専用フォルダにPillow／Mangumとリポジトリ指定のbcrypt 4.0.1を配置して解消し、venv自体は変更していません。
- 通常Flutterテスト216件＋原本不要の全20市町データ検証2件成功。mainの隔離コピーと今回APIから取得したアセットで実行しました。解析はエラー0・warning 7・info 55で、既存指摘は残しています。
- Terraform 1.17.2の両rootでvalidate・fmtとmock plan計9件成功。backend例もローカル模擬S3/STSへのinitで受理し、別アカウントを拒否することを確認しました。既存stateを使ったinit／plan／applyは実施していません。
- 新しいprepareで実AWSの読み取り確認、公開APIから全20市町・43プロフィール取得、mainのクリーンな入力からのWebビルド、dry-runが成功しました。新しいdeployも`--execute`なしで`dry_run`となることを確認しました。CupertinoIconsフォントの既存案内は未解消です。
- 新コマンドからの実アップロード・invalidation・復旧書き込みは未実施です。確認入力、途中変更、重複実行拒否、復旧先の固定、検証再開は模擬テストで検証し、既存の低レベル公開・復旧処理は変更していません。

参照: [S3 backendのaccount制限・lockfile](https://developer.hashicorp.com/terraform/language/backend/s3)、[S3条件付き書き込み](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)、[OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)、[CloudFront料金](https://aws.amazon.com/cloudfront/pricing/pay-as-you-go/)。
