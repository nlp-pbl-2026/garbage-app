# 担当7自治体の検索・カレンダー接続

大洲市、砥部町、愛南町、鬼北町、松野町、内子町、松前町を、既存の複数自治体対応基盤へ接続するための検証・再生成手順です。公式資料から生成した品目CSVと実日付カレンダーを自治体ごとに保持し、Titan Text Embeddings V2の索引を共有しません。

## 対応範囲

| 自治体 | 自治体ID | 品目数 | 収集地区数 | カレンダー数 | 公式期間 |
| --- | --- | ---: | ---: | ---: | --- |
| 大洲市 | 38207 | 632 | 29 | 29 | 2026-04-01～2027-03-31 |
| 砥部町 | 38402 | 806 | 7 | 7 | 2026-04-01～2026-12-06 |
| 愛南町 | 38506 | 977 | 8 | 8 | 2026-01-01～2026-12-31 |
| 鬼北町 | 38488 | 1,219 | 8 | 8 | 2026-04-01～2026-12-31 |
| 松野町 | 38484 | 1,434 | 11 | 11 | 2026-04-01～2027-03-31 |
| 内子町 | 38422 | 876 | 26 | 26 | 2026-01-01～2026-12-31 |
| 松前町 | 38401 | 1,384 | 2 | 2 | 2026-04-01～2027-03-31 |
| 合計 | - | 7,328 | 91 | 91 | - |

2026年11月5日に各生成スクリプトの `fetch` を再実行し、公式サイトから取得した全ファイルが追跡中のSHA-256と一致することを確認しました。続けて `build` と `verify` を実行し、レビュー済みの品目数、地区対応、日付セル、例外と生成物が一致しました。検証は各自治体の `sources.json`、`calendar_reviews.json`、`item_reviews.json`（存在する自治体）、`official_rules.json` を基準にします。

砥部町は、公式に公開・照合できた月刊カレンダーだけを採用するため、現在の有効期限が2026年12月6日です。それより後の日付は推測して生成せず、通知・iCalにも含めません。新しい月号が公開された場合は、取得・レビュー記録と有効期限を更新してから再生成します。

## 検索と追加質問

各自治体の `registry.json` は `knowledge/items.csv`、`knowledge/item_embeddings.npz`、`generated/calendar-2026.json` を参照します。全プロファイルの `index_profile_id` は自治体内共有を表す `citywide` ですが、ファイルは自治体ディレクトリ内に分離されています。他自治体のCSV・索引へフォールバックしません。

検索は既存経路を利用します。

1. Nova Liteがテキストと任意画像を検索文へ言い換える。
2. Titan Text Embeddings V2が検索文を1,024次元へ変換し、選択自治体のNPZだけから候補を取得する。
3. Nova Liteが公式品目行・注記・自治体ルールを使って分類し、素材、大きさ、用途、汚れ、電池などが不足する場合は一度に1点だけ追加質問する。
4. 分類コードの `collection_type_id` がある場合だけ、選択地区の次回収集日を返す。粗大ごみ、持込、回収ボックス、収集禁止などを通常収集日に変換しない。

実API評価の入力は `data/regions/assigned_search_cases.json`、結果は `data/regions/assigned_search_review.json` に記録します。通常品目、収集対象外、大きさの追加質問と回答後の分類、材質・電池・現行プラスチックルールを各自治体6件、計42件確認します。生のモデル応答と呼び出し記録は `backend/evaluation/artifacts/assigned-municipalities/` に置き、Gitには含めません。

2026年11月5日の初回実API評価は42件中27件成功、15件失敗でした。失敗ログを調べると、主因はNovaの言い換えで公式品目名が欠落・誤変換されたこと（例: `ペットボトル` が `空のボトル`、`石製のうす` が `石製筆削り`）、モデルが引用した品目と追加質問ガードが参照する品目の不一致、品目固有注記より区分共通説明を優先した不要な質問でした。

修正後は、元入力に同じ自治体の公式品目名がある場合だけCSVの一致候補を意味検索へ加え、品目固有注記に記録された素材・袋サイズ・汚れ条件を優先して質問・確定します。別自治体のCSVや索引へはフォールバックしません。初回失敗を再現する公式CSV条件テスト17件は17件すべて成功しています。承認済みの評価上限126回を初回評価で使い切ったため、修正後のBedrock再評価は未実施です。初回結果は監査記録として書き換えず保持します。

## Bedrock実行実績と費用

- Embedding: `amazon.titan-embed-text-v2:0`、1,024次元、7,328ベクトル
- 索引生成: 7,523試行、成功入力385,931トークン。DNS到達前の失敗を含む195試行も安全側に呼び出し予約として計上
- 検索評価: 126回（Nova Lite 84回、Titan V2 42回）
- 合計: 7,649試行、推定実費 US$0.01754144、保守的予約額 US$0.39478762
- 承認上限: 合計7,726回、US$0.60

## 最終検証結果

- バックエンド全テスト: 313件成功（既存Pydantic非推奨警告3件）
- 担当7自治体の実CSV・NPZ・manifest・カレンダー・API統合: 15件成功
- 公式CSVの完全一致・条件分岐補正: 17件成功
- Flutter全テスト: 187件成功
- 担当7自治体のFlutterカタログ・カレンダー・通知・iCal・粗大ごみ統合: 4件成功
- Flutter Webビルド: 成功
- `flutter analyze`: コンパイルエラー0件。既存lint 62件（info 55件、warning 7件）のため通常コマンドは終了コード1

## Flutter接続

`data/regions/catalog.json` への登録後、`scripts/generate_frontend_data.py` が同じ台帳から次を生成します。

- `frontend/assets/data/municipality_catalog.json`
- `frontend/assets/data/municipality_{自治体ID}_registry.json`
- `frontend/assets/data/municipality_{自治体ID}_0_calendar.json`（Git管理外）

地域選択画面はカタログの自治体名と台帳の `display_name` を表示します。カレンダー番号やPDF名は表示しません。検索、追加質問、カレンダー、通知、iCal、粗大ごみ案内は既存の共通サービスへ接続し、自治体IDと地区IDを保持します。今回の7自治体は公式住所対応表や境界GeoJSONを用意していないため、GPSによる地区自動確定は行わず手動選択を使用します。

## 新規cloneからの再生成

Windows PowerShellの例です。Python依存関係を準備した後、公式資料、CSV、カレンダーを自治体単位で再生成します。

```powershell
cd backend
uv sync
cd ..

$municipalities = 'ozu','tobe','ainan','kihoku','matsuno','uchiko','masaki'
foreach ($municipality in $municipalities) {
  & backend/.venv/Scripts/python.exe "scripts/${municipality}_data.py" fetch
  & backend/.venv/Scripts/python.exe "scripts/${municipality}_data.py" build
  & backend/.venv/Scripts/python.exe "scripts/${municipality}_data.py" verify
}
```

Embedding生成は有料です。実行前にモデル、呼び出し回数、費用上限の承認を得てから、AWSへログインし、合計ガード付きのコマンドを使います。

```powershell
aws login
& backend/.venv/Scripts/python.exe scripts/build_assigned_embeddings.py `
  --confirm-paid --max-calls 7600 --budget-usd 0.48 --workers 4
```

索引生成後にFlutterアセットを生成します。標準カタログ全14自治体のGit管理外データを用意できる場合は通常生成を使います。

```powershell
& backend/.venv/Scripts/python.exe scripts/generate_frontend_data.py
```

既存5自治体のGit管理外カレンダーを再生成せず、担当7自治体だけを既存Flutterカタログへ追加する場合は次を使います。既存カタログ項目と既存アセットは保持されます。

```powershell
& backend/.venv/Scripts/python.exe scripts/generate_frontend_data.py `
  --merge-existing `
  --municipality-id 38207 --municipality-id 38402 `
  --municipality-id 38506 --municipality-id 38488 `
  --municipality-id 38484 --municipality-id 38422 `
  --municipality-id 38401
```

次のファイルは `.gitignore` の対象であり、新規cloneには含まれません。

- `data/regions/{自治体}/source/` の公式PDF・HTML
- `data/regions/{自治体}/generated/` のカレンダー、住所表、監査候補、Embeddingチェックポイント
- `data/regions/{自治体}/knowledge/items.csv`
- `data/regions/{自治体}/knowledge/item_embeddings.npz`
- `frontend/assets/data/municipality_*_calendar.json`
- `backend/evaluation/artifacts/` の有料評価ログ

Gitで追跡する `index_manifest.json` はCSV・NPZのハッシュ、件数、モデル、次元、呼び出し実績を記録します。新規環境でCSVまたはNPZを再生成した場合は、必ず同じ組からmanifestも再生成してください。

## 検証コマンド

```powershell
$env:PYTHONPATH = 'backend'
$env:PYTHONUTF8 = '1'
& backend/.venv/Scripts/python.exe -m pytest backend/tests `
  backend/official_tests/verify_assigned_municipalities_runtime.py -q

cd frontend
flutter pub get
flutter test
flutter test tool/verify_assigned_municipalities_data_test.dart
flutter analyze
flutter build web
```

通知の実配信、GPS権限、共有シート、iCalを受け取る外部アプリの挙動は、Webビルドや単体テストでは確認できません。最終配布前にAndroid/iOS実機で確認してください。公式資料の再配布条件も自治体ごとに最終確認が必要です。

この作業ではAWSへのデプロイ、Terraform、Lambda、S3、Knowledge Baseを操作しません。
