# APIからFlutter用データを取得して起動・ビルドする

## 現在の到達点と公開前の保留事項

この機能はローカル実装です。新APIはまだAWSへデプロイしていません。現在の公開API URLだけでは、このセットアップは完了しません。

また、公式資料を加工したUI用JSONのAPI配信・アプリ同梱・Vercelでの公衆送信に関する許諾は**全20市町について未確認**です。`data/regions/frontend_export_policy.json`を全件`pending`としており、公開環境の新APIは既定で503を返します。コードの完成と、公開・配布できる状態を区別してください。

既存の検索APIとの互換性、地域・地区ID、分別ルール、カレンダー原本、通知・iCalの計算を維持します。起動・ビルド前に新しい隔離作業ディレクトリへ同じ形式のアセットを用意する方式です。取得後は従来どおり同梱アセットを読み込みます。

## 配信するデータ

- `GET /api/frontend-data/manifest`: 全20市町のUIカタログ、ファイルサイズ・SHA-256、スナップショット全体のハッシュ版、再配布確認状態
- `GET /api/frontend-data/municipalities/{id}?version={版}`: その版の市町別台帳・区分名／色／搬出時刻・粗大ごみ案内・明示的な収集日・任意の公式住所表

CSV、Embedding索引、分類プロンプト、原資料PDF、OCR、認証情報、データのローカルパスは返しません。`generate_frontend_data.py`とAPIは同じUI変換処理を使います。カレンダーは確認済み原本のバイト列を保持し、住所表は表示・照合に必要な項目に限定します。生成JSONは原本の二重管理先ではありません。

これは新APIの配信範囲です。Flutterの従来のpubspecとGit管理済みアセットは維持するため、既存の`assets/choumei.csv`や旧JSON・GeoJSONもビルド対象に残ります。これらは現在のGPS候補の代用にせず、公開条件の確認時は従来同梱物も対象に含めてください。

取得処理はmanifest、20市町のデータ、最後に同じmanifestを順に取得します（通常22 GET、429/一時エラーは最大2再試行）。Bedrockは使いません。全20市町・プロフィール・地区／カレンダー参照、日付範囲、未確認区分・日付、住所参照、版・SHA-256・容量を検証し、最後まで同じ版・配信確認状態でなければ失敗します。過年度・期間外へ曜日規則で補完しません。

## ローカルAPIでの検証（現在利用できる手順）

データ保有者がバックエンドをループバックで起動します。以下は元のデータを読み取るだけで、再生成しません。

```bash
cd backend
FRONTEND_DATA_ALLOW_UNREVIEWED_LOCAL=1 \
  .venv/bin/python -m uvicorn app.lambda_main:app --host 127.0.0.1 --port 8000
```

この解除は未確認資料を外部公開する承認ではありません。接続元とHostがループバックであり、Forwardedヘッダーがなく、Lambda実行環境でもない場合にのみ有効です。0.0.0.0への公開、外部プロキシ経由の共有、公開トンネルは使わないでください。解除フラグをLambdaへ設定しても配信は有効になりません。

別ターミナルでリポジトリルートから実行します。

```bash
# 元のfrontendは変更せず、新しい一時作業コピーでChrome起動
python3 scripts/flutter_with_data.py \
  --api-base-url http://127.0.0.1:8000 --allow-unreviewed-local \
  -- run -d chrome

# ローカル確認用Webビルド。既存ディレクトリの上書きは拒否する
python3 scripts/flutter_with_data.py \
  --api-base-url http://127.0.0.1:8000 --allow-unreviewed-local \
  --work-dir /tmp/gomisapo-web-new \
  -- build web --release
```

実際の自然文／画像検索は既存どおりBedrock料金が発生します。上記のデータ取得・ビルド・画面のデータ読み込み自体はBedrockを呼びません。

通常はデータ保有者PC内でローカルAPI検証します。新規cloneした他メンバーがデータ受領なしで使うには、後述の条件確認・承認記録・新APIのAWS反映が必要です。

初回画面ではログインをスキップし、自治体と地区を選んでゲスト利用できます。認証APIのクラウド対応は今回の対象に含めていません。

## 公開条件確認・AWS反映後の新規clone手順

Python 3.10以上と、プロジェクトで動作確認した版のFlutter SDKをインストールします。バックエンドvenvやAWS認証情報、自治体CSV・NPZ・原資料はメンバー側に不要です。

```bash
git clone <リポジトリURL>
cd garbage-app

python3 scripts/flutter_with_data.py \
  --api-base-url https://<公開APIのホスト> \
  -- run -d chrome

python3 scripts/flutter_with_data.py \
  --api-base-url https://<公開APIのホスト> \
  --work-dir /tmp/gomisapo-release-new \
  -- build web --release
```

スクリプトは取得・検証、frontendの作業コピー作成、`flutter pub get`、指定したFlutterコマンドを順に実行し、`API_BASE_URL`をDart定義へ渡します。データ不足や公開未承認ならFlutter実行前に停止します。元のfrontendや未コミットのlockfile、既存のGit管理外JSONを変更しません。既存作業先は上書きせず、毎回新しい名前にしてください。通常の`flutter run`を直接使う場合は自動取得されません。

JSON取得だけなら次の標準ライブラリ専用スクリプトも使えます。出力先は新規ディレクトリに限定します。

```bash
python3 scripts/fetch_frontend_data.py \
  --api-base-url https://<公開APIのホスト> --output /tmp/gomisapo-ui-data-new
```

## AWSとFlutterの更新順序

1. 各市町について、この加工JSONのAPI配信・端末同梱・Web配信の範囲を確認する。対象資料への適用、出典表示、加工表示、第三者権利を確認し、承認根拠を記録する。
2. `frontend_export_policy.json`の各市町を`approved`にし、`evidence_url`、`reviewed_by`、`reviewed_on`を埋める。根拠がなければpendingのままにする。スクリプトは法的な許可の有無そのものを判断しない。
3. 管理者環境で全20市町の原本と6住所表を配置する。`catalog.json`の`addresses_path`がnullなら手動選択、パスがあれば必須ファイルとして検証する。ファイル欠落を「住所対応なし」に読み替えない。
4. 隔離した出力先でLambdaをパッケージングし、API用ルーター・共通UI変換／検証モジュール・配信確認ポリシー・住所表が含まれることを確認する。原資料や索引の再生成は不要。
5. [既存の安全なS3コード更新手順](lambda-s3-deploy.md)でprepare・対象／Revision確認・承認後のデプロイを行う。環境変数変更やTerraformでこの確認を迂回しない。
6. 更新後、新APIのmanifestと全市町データを公開URLから取得して検証し、既存検索APIも確認する。今回、この実AWS検証は未実施。
7. 同じmanifest版でFlutterをビルドし、APIとアセットの版を記録してからWeb／モバイル配布する。バックエンド更新時は対応するFlutterも再ビルドし、古いアセットを最新APIと混在させない。

旧ZIPを保持したままパッケージを作る例です（ローカル操作のみ）。

```bash
PACKAGE_OUTPUT=$(mktemp -d /tmp/gomisapo-lambda-XXXXXX)
BACKEND_PACKAGE_DIST_DIR="$PACKAGE_OUTPUT" ./scripts/package_backend.sh
```

続くS3デプロイのprepareには`--zip "$PACKAGE_OUTPUT/backend-lambda.zip"`と、新しいバックアップ先を指定します。既存plan・receipt・旧ZIPを書き換えません。デプロイスクリプトの変更は新APIモジュールを同梱必須一覧へ追加するだけで、対象確認・ハッシュ・RevisionId・ランタイム・ロールバックの安全チェックは維持します。

端末はビルド時点のスナップショットを使います。新しいFlutterは検索の各POSTに任意項目`ui_dataset_version`を付け、サーバーはモデル呼び出し前に現行版と比較します。不一致は409、版を確認できない場合は503で停止します。既存の版を送らないクライアントのAPI互換性は維持します。追加のHTTPヘッダーやAPI Gateway設定変更は不要です。

バックエンドだけが将来のカレンダー・地区IDを変更した場合、自動で全端末を更新する仕組みではありません。新アプリの検索は不一致を案内するため、対応するFlutterの再ビルド・更新が必要です。実行時の自動同期は今回追加しません。

## Vercelでの設定案（デプロイ未実施）

- Framework Preset: Other
- Root Directory: リポジトリルート
- Build Command: `python3 scripts/flutter_with_data.py --api-base-url "$API_BASE_URL" --work-dir .frontend-build -- build web --release`
- Output Directory: `.frontend-build/frontend/build/web`
- Environment Variables: `API_BASE_URL`に新API反映・配信条件確認済みのHTTPS URL。Preview/Productionそれぞれ設定する。
- ビルド前に検証済みFlutter SDKの固定版とPythonを用意し、FlutterをPATHへ追加する。今回の確認環境はFlutter 3.47.1 / Dart 3.13.1。SDKを暗黙の最新版にしない。SDKの依存制約によりpubspec.lockを更新する場合も、作業コピー内だけに限定される。

`.frontend-build/`はGit除外対象です。Vercelのクリーン環境では存在しない状態から始めます。カレンダー・住所表の前ビルドキャッシュを正しいデータの代用にしません。Vercelの環境変数はスクリプトが`--dart-define`へ渡します。AWS認証情報や秘密キーはFlutterへ渡しません。公開API未承認／取得失敗／版の混在時はビルドを失敗させます。

## 維持する制約

- 住所表は松山・新居浜・東温・上島・四国中央・西予の6市町。他14市町は手動選択で、旧GeoJSON・地区名の類似だけから候補を推測しない。
- 未確認区分・未確認日・期限不明の搬出時刻は既存の扱いを維持。通知／iCalに未確認日を登録しない。
- 砥部町は2026-12-06、愛南町・鬼北町・内子町は2026-12-31まで。新しい取得経路で有効期間は延長されない。
- Webのネイティブ通知未対応、WebのiCalテキスト共有、ログインAPIのlocalhost固定とLambdaの認証ルート未整備は今回変更しない。検索等のゲスト利用と認証対応を分けて判断する。
- 新規cloneの通常のFlutter試験は取得したアセットで実施できる。原本照合用の既存`tool/verify_*_data_test.dart`の一部は管理者のバックエンド原本を必要とする。`tool/verify_downloaded_ui_data_test.dart`はバックエンド原本を使わず全20市町を検証する。

## 利用・再配布条件の確認記録

2026-11-13に以下の公式一般条件を読み取った範囲では、この加工JSONの外部配信を承認済みとは判断できません。全20市町の個別カレンダー・町名表・案内文への適用や許諾の確認は未完了です。法令上の例外が今回の用途に適用されるとも、オープンデータの条件が通常ページの添付PDFまで適用されるとも推測していません。

| 公式資料 | 読み取った内容と残る確認 |
| --- | --- |
| [松山市・著作権](https://www.city.matsuyama.ehime.jp/aboutweb/copyright.html) | 原則帰属、転用・改変に関する制限。個別の例外・許諾が対象データに適用されるか確認が必要 |
| [松野町・著作権](https://www.town.matsuno.ehime.jp/soshiki/1/1176.html) | 法令で認められる場合などを除く無断使用・複製・改変・配布の制限。対象加工データの利用根拠は未確認 |
| [西予市・サイトポリシー](https://www.city.seiyo.ehime.jp/kakuka/seisaku_kikaku/seisakusuishin/saitonitsuite/430.html) | 転載申請の案内がある。今回の配信範囲の許可は未確認 |
| [東温市・著作権](https://www.city.toon.ehime.jp/site/guide/51.html) | 著作権帰属とリンク条件の案内。リンク可能であることを加工JSONの再配布許可とは扱わない |

残る16市町も既存データガイドでは未確認であり、今回許諾を取得していません。原本の実日付・町名対応と案内文の利用範囲を市町別に確認してください。UI向けデータに限定しても、Git管理外にしても、Web/APIへ配信する際の確認が不要になるわけではありません。

## ローカル検証結果（2026-11-13）

- 全20市町・43プロフィール・706選択地区・6住所表から47個のUI JSONを取得し、別途manifestを保存した。データ原本の再生成やEmbedding API呼び出しは行っていない。
- `git archive`と今回の変更から作った新規clone相当のコピーでは、Git管理外のバックエンドCSV・カレンダーとFlutterカレンダーが存在しないことを確認した。ローカルAPIからの取得だけでWeb releaseビルドと、バックエンド原本を参照しないFlutterテスト218件に成功した。
- 原本照合を含む全体検証は別段階で行い、Flutter `test`＋`tool`の334件に成功した。この段階のみ管理者の原本を参照した。初回の照合で八幡浜市の公開カレンダー対応番号の省略を検出し、既存の検証と互換な公開出典項目を保持するよう修正した。
- Flutter静的解析はエラー0・warning7・info55。既存の解析記録と指摘内容を比較し、追加・解消とも0件だった。元の未コミットの解析設定・lockfileは変更していない。
- バックエンド単体／公式照合テスト777件に成功した。未承認配信の拒否、欠損・ハッシュ不一致・版の途中変更・自治体をまたぐ参照・未確認日・検索前の版チェックを外部APIなしで検証した。
- 一時出力先のLambda ZIPについて全20市町・43プロフィール・21索引・112実行時データファイルの一致を検証した。ZIP全体は3,640ファイル、圧縮後92,491,073 bytes（約88.2 MiB）、展開後155,549,768 bytes（約148.3 MiB）。既存ZIPのLinux依存ライブラリを再利用し、今回のコード・データを重ねたローカル検証用パッケージであり、依存ライブラリの再インストールは実施していない。アップロードは従来どおりS3経由とする。
- ネットワークを無効にしたPython 3.12 / Linux ARM64コンテナで、Lambdaハンドラー、全20市町の取得API、43プロフィールの品目API、21索引の読み込み、公開配信拒否と検索の版不一致停止を確認した。

AWS公開URLでの新API取得、Vercelへのデプロイ、実Bedrock検索、スマートフォン実機でのGPS・通知・iCalは今回未実施。公開条件の確認も未完了であり、これらを検証済み・配布可能とは扱わない。
