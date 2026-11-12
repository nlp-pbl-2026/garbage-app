# S3経由で既存Lambdaのコードだけを更新する

Terraformを実行せず、既存のPython 3.12 / ARM64 Lambdaを更新します。環境変数、Bedrock設定、実行ロール、Layer、API Gateway、バケット設定は変更しません。`aws-up.sh`はTerraformやKnowledge Base取り込みも実行するため、この用途では使用しません。

## 容量・前提・必要な権限

2026-11-12に確認した全20市町のZIPは92,808,542 bytes（88.5 MiB）、展開後155,229,970 bytes（148.0 MiB）、3,630ファイルです。43プロフィール・21索引・105実行時データファイルを含みます。現行LambdaはLayerなしでした。

直接アップロードの50 MB制限を超えるため、同一リージョンの既存S3バケットを使います。展開後はLayerを含め250 MB以内である必要があります。S3を使っても展開後制限は緩和されません。[AWS Lambdaクォータ](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html)、[UpdateFunctionCode](https://docs.aws.amazon.com/cli/latest/reference/lambda/update-function-code.html)

Python 3.12、バックエンドの依存パッケージ、認証済みAWS CLI v2が必要です。CLIは`put-object --if-none-match`とSHA-256チェックサムに対応する版を使用してください。全20市町のGit管理外データを配置し、Flutterと同じデータ版であることを先に確認します。データ再生成・Embedding生成・Bedrock呼び出しは含みません。

既存バケットは同一アカウント・リージョン、公開アクセスブロック4項目有効、バージョニング有効、SSE-S3（AES256）、BucketOwnerEnforcedを必須とし、公開ポリシーがあれば停止します。ポリシーなしは許容します。スクリプトはバケット設定を変更しません。API Gatewayのデフォルトルートが、対象Lambdaをバージョン・alias指定なしで参照することも確認します。

ZIPの保存先は`deployments/lambda/<関数名>/`、旧コードはその下の`backups/`です。既存Knowledge Base資料を上書きせず、取り込みジョブも開始しません。既存バケットの用途も確認してください。Terraformには資料用prefix `knowledge/matsuyama/common/records`が定義されていますが、実環境のデータソースはManaged Knowledge Base connectorであり、単純なS3取り込みprefixを取得して確認できたわけではありません。

操作者に必要な権限は以下です。Lambda実行ロールにZIP取得権限を追加する手順ではありません。

| 対象 | 必要な操作 |
| --- | --- |
| 対象Lambda | `lambda:GetFunction`、`lambda:GetFunctionConfiguration`、`lambda:UpdateFunctionCode` |
| 使用中のLayer（存在する場合） | `lambda:GetLayerVersion` |
| 既存バケット | `s3:GetBucketLocation`、`s3:GetBucketPublicAccessBlock`、`s3:GetBucketVersioning`、`s3:GetEncryptionConfiguration`、`s3:GetBucketOwnershipControls`、`s3:GetBucketPolicyStatus` |
| デプロイprefixのオブジェクト | `s3:PutObject`、`s3:GetObject`、`s3:GetObjectVersion` |
| HTTP API | 対象APIのintegrationsとroutesに対する`apigateway:GET` |
| アカウント確認 | `sts get-caller-identity`で確認 |

`CreateBucket`、`PutBucket*`、`DeleteObject`、`UpdateFunctionConfiguration`、`iam:PassRole`は使用しません。SSE-S3なのでこの手順にKMS権限は不要です。[PutObjectの権限と条件付き作成](https://docs.aws.amazon.com/cli/latest/reference/s3api/put-object.html)

2026-11-12の調査では必要な情報を読み取れましたが、`iam:SimulatePrincipalPolicy`はAccessDeniedでした。**S3書き込み・Lambdaコード更新権限は未確認です。** 読み取り成功だけで更新可能とは判断せず、管理者に対象prefixと関数への許可を確認してください。権限を試すための書き込みは実施していません。

## 1. パッケージ確認とバックアップ（AWS読み取りのみ）

リポジトリルートから、直前に確認した対象値を明示します。

```bash
backend/.venv/bin/python scripts/deploy_lambda_s3.py prepare \
  --account '<12桁のAWSアカウントID>' \
  --region ap-northeast-1 \
  --function '<既存Lambda関数名>' \
  --bucket '<同一リージョンの既存非公開バケット>' \
  --api-url 'https://<API ID>.execute-api.ap-northeast-1.amazonaws.com' \
  --zip backend/dist/backend-lambda.zip \
  --backup-dir backend/dist/lambda-deploy/<今回専用の新しいディレクトリ>
```

名前付き認証プロファイルは`--profile <名前>`で指定できます。既存バックアップ先を再利用しないでください。認証期限切れなら操作者が`aws login`などで認証し直します。スクリプトは認証情報を変更しません。

`prepare`は次を行います。

1. 全20市町のCSV・NPZ・manifest・カレンダーを検証し、ZIPの実行時データを原本と、収録コードをチェックアウトと照合する。PDF・OCR画像・ログなどを含めない。
2. アカウント・関数ARN・ランタイム・状態・API接続・S3設定を確認する。Nova Lite/Titanの通常検索経路と異なる設定や独自データパス指定があれば停止する。
3. 現行コードをダウンロードして`CodeSha256`を確認する。Layerがあれば取得し、展開後の合計容量を計算する。
4. 候補ZIP、`previous.zip`、`configuration-before.json`、`plan.json`を保存する。取得前後でRevisionId・コード・設定が変わっていないことを再確認する。

バックアップディレクトリは0700、機密ファイルは0600です。**`configuration-before.json`は秘密情報を含むため、Gitへの追加・無造作な共有・全内容表示をしないでください。** リポジトリ内では既存のGit除外先に限定します。バックアップとplanは同じディレクトリで保管します。

生成済みZIPの再ビルドは不要です。コードやデータを変更した場合だけ`package_backend.sh`で再生成し、新たにprepareします。ファイル検証はLinuxでの実行の代わりにはなりません。依存関係を更新したZIPは公式Lambda Python 3.12 ARM64環境でも確認してください。今回のZIPは[全市町統合時のLinux/ARM64検証](municipality-data-integration.md)と同じハッシュです。

## 2. 書き込みなしの直前確認

```bash
backend/.venv/bin/python scripts/deploy_lambda_s3.py deploy \
  --plan backend/dist/lambda-deploy/<今回のディレクトリ>/plan.json
```

`--execute`がなければS3への書き込み・Lambda更新をしません。対象と候補ZIP、現行RevisionId・CodeSha256・設定を再照合します。想定外の更新があれば止まり、自動追従しません。変更理由を確認してから新たにprepareしてください。

## 3. 承認後だけコードを更新

**以下はAWSへの書き込みを行います。承認前に実行しないでください。** `prepare`が表示した`target`を完全一致で指定します。

```bash
backend/.venv/bin/python scripts/deploy_lambda_s3.py deploy \
  --plan backend/dist/lambda-deploy/<今回のディレクトリ>/plan.json \
  --execute \
  --confirm-target '<アカウントID>:ap-northeast-1:<関数名>:<バケット名>'
```

旧コードと候補をS3へ条件付き作成し、サイズ・SHA-256・暗号化・VersionIdを確認します。キーが存在すれば内容一致のバージョンだけを利用します。その後、`aws lambda update-function-code --s3-bucket ... --s3-key ... --s3-object-version ... --revision-id ... --no-publish`を実行します。

S3のVersionIdを固定し、LambdaのRevisionIdによる条件付き更新を使います。並行作業でコードや設定が変われば停止します。完了待ち後にコードSHA・RevisionId・環境変数を含む設定の指紋を照合します。環境変数・ロール・API設定を上書きせず、バージョン公開・alias更新もしません。経過はローカルの`receipt.json`に保存します。

途中で失敗してもS3オブジェクトを自動削除しません。過去バージョンを含む保管料金が発生するため、不要になった世代の整理は別途承認して実施してください。

## 4. 更新後の公開API確認

更新成功後、ヘルス1件と43プロフィールの品目一覧を公開APIで照合します。期待するJSONは同じローカルハンドラーと実データから生成します。20市町・中島・関前などの切り替えを確認し、約2 req/s以下に抑えます。Bedrockは呼びませんがLambda/API Gateway実行料金は発生し得ます。

再確認は以下です。候補コードの導入を先に確認するため、更新前のAPIを成功扱いにはしません。

```bash
backend/.venv/bin/python scripts/deploy_lambda_s3.py verify \
  --plan backend/dist/lambda-deploy/<今回のディレクトリ>/plan.json
```

RAGの正解率・画像理解・追加質問・次回収集日の実API評価は含みません。別途承認した費用枠で20市町の代表検索を評価し、Flutterを同じ地区台帳・カレンダー版で接続して確認します。通知・GPS・iCalはスマートフォンでも確認が必要です。データ有効期限や未確認日は更新だけで解消しません。

API照合失敗時はコード更新済みと明示して停止します。他作業を上書きする自動復旧は行いません。原因を確認し、必要ならロールバックします。

## 5. ロールバック

まず書き込みなしで確認します。

```bash
backend/.venv/bin/python scripts/deploy_lambda_s3.py rollback \
  --plan backend/dist/lambda-deploy/<今回のディレクトリ>/plan.json
```

承認後、同じコマンドに`--execute --confirm-target '<prepareのtarget>'`を追加すると、旧コードのS3バージョンでコードだけを戻します。旧ZIPのSHAと現行設定を検査し、今回のreceiptと異なるRevisionId・コード・設定なら停止します。環境変数は復元・変更しません。旧コードが導入済みなら書き込みません。復旧後は旧版のヘルス・既存地域の検索を確認します（旧版には20市町がない可能性があります）。

通信断などで要求が受理されたか不明なら、繰り返し実行せず確認します。次は秘密情報を表示しない読み取りです。

```bash
aws --region ap-northeast-1 lambda get-function \
  --function-name '<関数名>' \
  --query 'Configuration.{CodeSha256:CodeSha256,RevisionId:RevisionId,State:State,LastUpdateStatus:LastUpdateStatus}'
```

receipt保存前に中断した場合、スクリプトは更新の所有者を判断できず復旧を拒否します。plan・旧コード・現行SHA/RevisionId・設定を管理者が照合し、別更新がないことを確かめてから個別に復旧を判断します。planやreceiptの手編集で拒否を迂回しないでください。

## 今回確認した範囲

2026-11-12時点で現行LambdaはPython 3.12 / ARM64、Layerなし、512 MiB・30秒、通常のNova Lite/Titan検索設定でした。既存プロジェクト用S3バケットは前述の条件を満たしました。現行コードと設定をGit除外領域にバックアップ済みです。具体的な対象識別子は作業時のローカルplanを参照してください。

**実アップロード・Lambda更新・更新後の公開API照合は未実施です。** 書き込み権限確認、実Bedrock横断評価、実機検証、公式資料の利用・再配布条件確認は残っています。

ローカル検証結果（AWS HTTP送信を遮断したバックエンド試験、Flutterは隔離コピーで実行）:

| 検証 | 結果 |
| --- | --- |
| データ整合性 | 20市町・43プロフィール・21索引・706地区、モデルAPI 0回 |
| ZIP | 実行時データ105ファイル・収録コード一致、原資料・生ログなし、Layer込み148.0 MiB |
| バックエンド | 716成功（既存684＋今回32）、失敗0・スキップ0 |
| スクリプト試験 | 既定で書込禁止、対象違い、ZIP改変、権限不足、S3不一致、更新競合、API失敗、復旧拒否・成功をモックで検証 |
| API照合処理 | 実データ＋ローカルASGI経由でhealth 1件・43プロフィールを照合。公開APIへの送信0回 |
| Flutter全テスト | 327成功、失敗0・スキップ0 |
| Flutter解析 | 62件（warning 7・info 55）、error 0、前回比追加0 |
| Webリリースビルド | 成功。既存のCupertinoIconsフォント案内あり |

`prepare`と`deploy`の書き込みなしモードは実AWSへの読み取りで実行し、コード・RevisionId・設定の不変を確認しました。CLI v2.36.28が条件付きPutObject・チェックサム用の引数に対応することもローカルで確認しました。これらは実際の書き込み成功を保証する検証ではありません。
