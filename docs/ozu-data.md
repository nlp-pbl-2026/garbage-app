# 大洲市データの再生成と検証

大洲市（自治体コード `38207`）の令和8年度データを、公式ページとPDFから再生成する手順です。対象は大洲地域14、長浜地域2、肱川地域12、河辺地域1の計29地区です。

現時点では、地区台帳・収集カレンダー・分別辞典の検索レコードまで実装しています。Titan Text Embeddings V2の索引は未生成で、`data/regions/catalog.json` への登録も行っていません。そのため、既存の松山市・八幡浜市環境には影響せず、大洲市はまだアプリの選択肢に表示されません。

## Gitで管理するもの

- `data/regions/ozu/official_rules.json`: 大洲市固有の7種分別、出し方、粗大ごみ窓口
- `data/regions/ozu/sources.json`: 取得元URL、SHA-256、取得時刻、利用条件の状態
- `data/regions/ozu/calendar_reviews.json`: 29 PDFの抽出結果ハッシュとレビュー範囲
- `data/regions/ozu/registry.json`: 29地区と2ルールプロファイルの台帳
- `scripts/ozu_data.py`: 取得、分別辞典抽出、生成、検証
- `scripts/ozu_pdf.py`: PDF罫線とアイコンから収集日を復元する処理

公式HTML/PDF、生成カレンダー、品目CSV、Embedding索引は `.gitignore` の対象です。大洲市ホームページの著作権ページでは、私的利用・引用等を除く転載や二次利用には許可が必要とされています。原本や原文をリポジトリへ収録せず、公開・再配布前に大洲市へ利用条件を確認してください。

## 必要なツール

バックエンドのPython依存関係に加えて、分別辞典の列位置付き抽出にPopplerの `pdftotext` が必要です。

```bash
pdftotext -v
backend/.venv/bin/python -c "import pymupdf; print(pymupdf.__version__)"
```

WindowsではPython部分を `backend/.venv/Scripts/python.exe` に読み替えます。

## 再生成手順

### 1. 公式原本を取得

```bash
backend/.venv/bin/python scripts/ozu_data.py fetch
```

5ページのHTML、分別辞典PDF、29カレンダーPDFの計35ファイルを `data/regions/ozu/source/` に保存します。ホスト、カレンダー件数、番号の連続性、添付IDの一意性を検査します。

### 2. カレンダー抽出結果を確認

```bash
backend/.venv/bin/python scripts/ozu_data.py inspect
```

以下を生成します。

- `generated/sources-candidate.json`
- `generated/review-candidate.json`

大洲・長浜・河辺版はPDFのベクター罫線とアイコン形状、肱川版は罫線と埋め込みアイコン画像を使います。各月の曜日列は等幅とは限らないため、日付文字と8本の縦罫線を照合してセルを復元します。OCRによる日本語ラベルの推測は行いません。

現在のレビューでは、29 PDF×365日＝10,585日付セルを生成し、大洲・長浜・肱川・河辺の代表PDFについて2026年4月を日付単位で公式画像と照合しています。気象・災害等による年間カレンダー公開後の臨時変更は推測しません。

### 3. 台帳・カレンダー・品目CSVを生成

```bash
backend/.venv/bin/python scripts/ozu_data.py build
backend/.venv/bin/python scripts/ozu_data.py verify
```

`build` はレビュー済みハッシュと一致しない原本・日付データを拒否します。分別辞典の6～25ページから624分類行を抽出し、8件の共通ルール行を加えた632検索レコードを作ります。素材別の行、指定袋に入る場合の代替分類、市では収集しない品目、回収ボックスを一律の7種分別へ潰しません。

`verify` は公式原本から再抽出し、ソースハッシュ、29地区、10,585日付セル、CSVの全行を生成物と比較します。

## Embedding生成とアプリへの登録

Embedding生成はAWS Bedrockへの有償呼び出しです。通常の取得・ビルド・テストからは実行しません。費用と認証を明示的に承認した場合のみ、次を実行します。

```bash
backend/.venv/bin/python scripts/build_regional_embeddings.py \
  --source data/regions/ozu/knowledge/items.csv \
  --output data/regions/ozu/knowledge/item_embeddings.npz \
  --municipality 38207 --profile citywide \
  --checkpoint data/regions/ozu/generated/embedding-checkpoint.jsonl \
  --max-calls 700 --budget-usd 0.30
```

生成後はCSVとNPZのID順、モデルID、次元、有限値、正規化、SHA-256を確認します。確認済みの `index_manifest.json` とNPZが揃ってから、次の順で有効化します。

1. `data/regions/catalog.json` に `38207` と `ozu/registry.json` を追加する。
2. `scripts/generate_frontend_data.py` でFlutter用地区台帳・カレンダーを生成する。
3. バックエンド、Flutter、配布パッケージの回帰テストを実行する。
4. 実Bedrock検索で代表品目・条件分岐・画像検索を評価する。

索引がない状態でカタログだけ登録すると、大洲市の検索経路が不完全になるため行いません。

## 粗大ごみの地区差

大洲・肱川・河辺地域は `standard`、長浜地域は `nagahama` プロファイルを使います。分別品目と検索索引は市内共通ですが、粗大ごみの予約電話番号が異なります。

- 大洲・肱川・河辺地域: 0893-24-0530
- 長浜地域: 0893-52-1113

受付は月～金9:00～17:00（祝日を除く）、処理券は1個1,050円です。カレンダーに粗大ごみ日がある長浜・河辺地域でも、予約なしで出せる定期収集として案内しません。
