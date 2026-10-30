# 自治体データの配置と検証

松山市の2026年度データは `data/regions/matsuyama/` で管理します。自治体資料とその加工結果は既存のGit除外方針に従い、追跡しません。Gitには地区・カレンダーの対応表、出典URL、ハッシュ、検証記録、生成・検証スクリプトを残します。公式資料の加工・再配布条件は未確認です。公開・配布前に松山市へ確認してください。

## 2026年度の構成

| パス | 内容 | Git |
| --- | --- | --- |
| `registry.json` | 58収集地区、43カレンダー、松山・北条／中島の分別設定、旧地区IDの移行候補、公式URL・適用期間 | 追跡 |
| `calendar_reviews.json`、`knowledge_reviews.json` | 公式PDF・住所表のハッシュ、照合状態、抽出件数 | 追跡 |
| `source/` | 公式カレンダーPDF、住所表HTML、分別資料、抽出中間データ | 除外 |
| `generated/calendar-2026.json` | PDFから整備した収集日共通原本。バックエンドが読む | 除外 |
| `generated/addresses.json` | 公式町名表から導いた住所候補。境界ポリゴンではない | 除外 |
| `generated/nakajima_items.csv` | 中島カレンダーに記載された分別例。網羅的な品目辞典ではない | 除外 |
| `common/knowledge/items.csv` | 松山・北条の既存1,756品目 | 除外 |
| `common/knowledge/item_embeddings.npz` | 既存のTitan Text Embeddings V2索引 | 除外 |
| `common/knowledge/index_manifest.json` | CSV・索引のハッシュと整合性確認結果 | 追跡 |

`scripts/matsuyama_data.py build` は共通原本を `frontend/assets/data/municipality_calendar.json` にバイト単位で複製します。住所表も `frontend/assets/data/municipality_addresses.json` に生成します。Flutterへの組み込み前に必ず生成してください。`frontend/assets/data/municipality_registry.json` は `registry.json` の複製です。カレンダーは2026年4月1日から2027年3月31日までのみ有効で、翌年度へ繰り返しません。

43種類の公式カレンダーを複数の収集地区で共有します。地区ID、カレンダーID、分別設定IDを別々に扱います。旧ID `38201-08` は清水のままです。旧IDから新地区が一意に定まらない場合、保存設定は推測で移行せず再選択を求めます。

## 取得・生成・照合

公式資料は[2026年度の地区別カレンダー一覧](https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/gomicalender/r8gomicaletikubetu.html)、[松山・北条地域の分別案内](https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/kateigomi_matsuyama.html)、[中島地域の分別案内](https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/kateigomi_nakajima.html)、市の町名別地区検索表です。個別PDFのURLは `registry.json` に記録しています。

リポジトリのルートから実行します。Python環境に `numpy` と `PyMuPDF` が必要です。以下のコマンドはBedrockを呼びません。

```bash
backend/.venv/bin/python scripts/matsuyama_data.py fetch
backend/.venv/bin/python scripts/matsuyama_data.py fetch-aux
backend/.venv/bin/python scripts/matsuyama_data.py extract
backend/.venv/bin/python scripts/matsuyama_data.py restore-legacy
backend/.venv/bin/python scripts/matsuyama_data.py build
backend/.venv/bin/python scripts/matsuyama_data.py build-knowledge
backend/.venv/bin/python scripts/matsuyama_validation.py
```

公式PDFの色・凡例・日付セル・例外を `scripts/matsuyama_pdf.py` で読み取り、`calendar_reviews.json` のハッシュと照合します。抽出エラー、PDF更新、レビュー内容との差異があればビルドを停止します。公式データの照合は単体テストとは別のゲートです。検証記録なしに日付を「対応済み」として採用しないでください。`matsuyama_validation.py` は58地区、43カレンダー、15,695日付セル、バックエンドとFlutterの同一性、品目例と住所表の件数を確認します。レビュー記録は自動抽出だけで正確性を保証するものではないため、公式PDFとの目視照合記録と併せて扱います。

住所表は710行で40地区に対応します。残る18地区（中島の17地区と泊）は住所のみでの確定に使わず、GPSも推測せず手動選択します。町名が複数地区に対応する場合も候補を提示します。元のGeoJSONは収集地区境界として使用しません。

中島の分別例は公式カレンダーに明記された79例に限ります。松山・北条の1,756品目やそのベクトル索引を中島の根拠として流用しません。中島用の網羅的な品目辞典とEmbedding索引は未整備で、正式な追加には公式資料の確認と、費用を伴う新しいEmbedding生成が必要です。

既存索引については1,756件のID・順序・モデル・次元・ベクトル長・有限値・正規化とファイルハッシュを検査しています。索引生成当時のCSVハッシュは記録されていないため、テキストとベクトルが当時完全に一致したことまでは立証できません。分類が条件付きで空欄の6品目は推測で埋めていません。

## 他自治体・年度への拡張

自治体を追加する場合は、独立した地区台帳、適用期間、分別設定、カレンダー原本、出典・検証記録を用意し、対応する検索索引を分けてください。現時点のAPIは松山市のみを受け付けます。松山市でも2027年度は別バージョンの公式資料を取得・検証してから公開してください。

旧Knowledge Base連携・比較実験の入力形式は `infra/scripts/build_knowledge_records.py` と `backend/evaluation/README.md` を参照してください。現在の松山・北条の本番検索経路はLambda同梱のTitan索引です。

## AWS・アプリ反映前

公式資料の利用条件を確認し、上記の取得・生成・照合を済ませてから、`scripts/package_backend.sh` でLambda成果物を作成します。このスクリプトはバックエンドとFlutterのカレンダー原本のバイト一致も確認します。Terraformの `REGION_REGISTRY_PATH`、`CALENDAR_BUNDLE_PATH`、`NAKAJIMA_ITEMS_PATH` は同梱先を指す設定です。Terraform planとAPI回帰確認を行い、バックエンドの更新後に同じバージョンのFlutterをビルドして配布してください。APIとFlutterが別バージョンになる期間は地区・日付の不一致が起き得ます。公開環境への反映、Terraform apply、Bedrockの有償処理はこの手順の自動実行には含めません。
