# 自治体データの配置と検証

松山市の2026年度データは `data/regions/matsuyama/` で管理します。公式PDF・加工CSV・生成カレンダーは既存のGit除外方針に従い、追跡しません。Gitには地区・カレンダーの対応表、出典URL、ハッシュ、検証記録、生成・検証スクリプトと既存のEmbedding索引を残します。公式資料と加工データの公開・再配布条件は未確認です。GitHubへの公開やアプリ・Lambdaへの同梱が認められる範囲を、公開前に確認してください。

## 2026年度の構成

| パス | 内容 | Git |
| --- | --- | --- |
| `registry.json` | 58収集地区、43カレンダー、松山・北条／中島の分別設定、旧地区IDの移行候補、公式URL・適用期間 | 追跡 |
| `calendar_reviews.json`、`knowledge_reviews.json` | 公式PDF・住所表のハッシュ、照合状態、抽出件数 | 追跡 |
| `auxiliary_sources.json` | 町名表・分別案内・品目辞典の取得時ハッシュ | 追跡 |
| `source/` | 公式カレンダーPDF、住所表HTML、分別資料、抽出中間データ | 除外 |
| `generated/calendar-2026.json` | PDFから整備した収集日共通原本。バックエンドが読む | 除外 |
| `generated/addresses.json` | 公式町名表から導いた住所候補。境界ポリゴンではない | 除外 |
| `generated/nakajima_items.csv` | 中島カレンダーに記載された分別例。網羅的な品目辞典ではない | 除外 |
| `common/knowledge/items.csv` | 松山・北条の既存1,756品目 | 除外 |
| `common/knowledge/item_embeddings.npz` | 既存のTitan Text Embeddings V2索引 | 追跡 |
| `common/knowledge/index_manifest.json` | CSV・索引のハッシュと整合性確認結果 | 追跡 |

`scripts/matsuyama_data.py build` は共通原本を `frontend/assets/data/municipality_calendar.json` にバイト単位で複製します。住所表も `frontend/assets/data/municipality_addresses.json` に生成します。Flutterへの組み込み前に必ず生成してください。`frontend/assets/data/municipality_registry.json` は `registry.json` の複製です。カレンダーは2026年4月1日から2027年3月31日までのみ有効で、翌年度へ繰り返しません。

43種類の公式カレンダーを複数の収集地区で共有します。地区ID、カレンダーID、分別設定IDを別々に扱います。旧ID `38201-08` は清水のままです。旧IDから新地区が一意に定まらない場合、保存設定は推測で移行せず再選択を求めます。

## 取得・生成・照合

公式資料は[2026年度の地区別カレンダー一覧](https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/gomicalender/r8gomicaletikubetu.html)、[松山・北条地域の分別案内](https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/kateigomi_matsuyama.html)、[中島地域の分別案内](https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/kateigomi_nakajima.html)、市の町名別地区検索表です。個別PDFのURLは `registry.json` に記録しています。

Python 3.12で `cd backend && uv sync --group dev && cd ..` を実行してから、リポジトリのルートで次を実行します。PyMuPDF 2.0.0は開発依存関係に固定しています。以下のコマンドはBedrockを呼びません。

```bash
backend/.venv/bin/python scripts/matsuyama_data.py fetch
backend/.venv/bin/python scripts/matsuyama_data.py fetch-aux
backend/.venv/bin/python scripts/matsuyama_data.py extract
backend/.venv/bin/python scripts/matsuyama_data.py restore-legacy
backend/.venv/bin/python scripts/matsuyama_data.py build
backend/.venv/bin/python scripts/matsuyama_data.py build-knowledge
backend/.venv/bin/python scripts/matsuyama_validation.py
backend/.venv/bin/python scripts/matsuyama_raster_audit.py
```

松山市の分別案内HTML2件だけは、CMSの1行の `div#lorecommend`（おすすめページ欄）を除いた内容が既存のハッシュと一致する場合も許容します。原本は加工せず、実際のSHA-256と照合方法を `source/auxiliary-verification.json` に記録します。本文・住所表・PDFの変更は許容しません。新規cloneから両自治体を利用するセットアップと、八幡浜市索引の受け渡しは[八幡浜市データガイド](yawatahama-data.md#新規cloneからの取得再生成)を参照してください。

公式PDFの色・凡例・日付セル・例外を `scripts/matsuyama_pdf.py` で読み取り、`calendar_reviews.json` のハッシュと照合します。抽出エラー、PDF更新、レビュー内容との差異があればビルドを停止します。公式データの照合は単体テストとは別のゲートです。検証記録なしに日付を「対応済み」として採用しないでください。`matsuyama_validation.py` は43 PDFを再読取し、生成物と全15,695日付セルを直接比較します。バックエンドとFlutterの同一性、品目例と住所表の件数も確認します。`matsuyama_raster_audit.py` は別経路の描画色検査で全15,695セルの収集色または色なしを確認します。日曜2,236セルと縮小表示344セルも含みます（両者は一部重複）。ただし、画像色検査は抽出済みの日付位置を使い、「休止」などの文字や中島の凡例グループに含まれる区分の意味を独立に読んではいません。例外表示・縮小セル・凡例の代表例と外れ値を優先して目視確認し、自動検査だけで人手の全日付監査を完了したとは扱わないでください。

住所表は710行で40地区に対応します。残る18地区（中島の17地区と泊）は住所のみでの確定に使わず、GPSも推測せず手動選択します。町名が複数地区に対応する場合も候補を提示します。元のGeoJSONは収集地区境界として使用しません。

中島の公式検索根拠79行は、カレンダーに明記された品目例68件と分別説明11件です。品目例には該当品目・区分だけを記録し、分別説明の全文は別のルール行に保持します。

### 中島地域での共通品目索引

[令和8年3月の松山市一般廃棄物処理基本計画](https://www.city.matsuyama.ehime.jp/kurashi/gomi/kanren/gomikeikaku.files/R8ippaikeikaku_honpenn.pdf)は、中島地域を松山・北条地域の金物・ガラス類を細分化した10種13分別と説明しています。そこで1,756件の既存ベクトル索引を**候補取得だけ**に両地域で利用します。中島の判定根拠には、松山・北条の分類コードと注意書きを直接渡しません。中島の公式79行を先に使用し、残りの候補は `nakajima_rule_service.py` の2026年度共通区分・地域差のルールで変換します。出し方は中島地域の[公式案内](https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/kateigomi_nakajima.html)と[2026年度カレンダー](https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/gomicalender/r8gomicaletikubetu.files/2026nakajimaoura.pdf)によります。粗大ごみの区分と収集方法は分けて扱います。

共通区分でも分類条件を含む品目、禁止品目、分類空欄品目は個別根拠なしに確定しません。缶・びんは飲料・食料品用か、スプレー缶・一斗缶・金属製キャップかを確認し、名称だけで一括置換しません。根拠や利用者の条件が足りなければ追加質問または判定保留とします。`backend/.venv/bin/python scripts/audit_nakajima_rules.py` で、既存CSVから地域別根拠を作れる行数と条件確認が必要な行数を再計算できます。この数は検索順位や質問内容を加味した**実際の回答成功数ではありません**。新しいベクトルや品目CSVは生成しません。

共通区分の判断は、松山・北条の品目辞典と、地域差を示す2026年の基本計画を組み合わせたものです。各品目が中島の資料へ個別に掲載されたことを意味しません。索引生成当時のCSVハッシュがない制限も残ります。基本計画の令和9年度以降の変更はこの2026年度ルールに含めず、別版の資料で再検証してください。

既存索引については1,756件のID・順序・モデル・次元・ベクトル長・有限値・正規化とファイルハッシュを検査しています。索引生成当時のCSVハッシュは記録されていないため、テキストとベクトルが当時完全に一致したことまでは立証できません。分類が条件付きで空欄の6品目は推測で埋めていません。

## 他自治体・年度への拡張

自治体を追加する場合は、独立した地区台帳、適用期間、分別設定、カレンダー原本、出典・検証記録を用意し、対応する検索索引を分けてください。バックエンドは `data/regions/catalog.json` で自治体ごとのデータを読み分けます。標準カタログには松山市・八幡浜市・伊予市・伊方町・新居浜市・四国中央市・東温市・上島町、[担当7自治体](assigned-municipalities-completion.md)、西予市・久万高原町・西条市・今治市の計19自治体を登録しています。追加する台帳・分類・索引の形式は[複数自治体バックエンドのデータ契約](multi-municipality-backend.md)を参照してください。公式期間外の日付は繰り返し生成せず、次年度は別バージョンの公式資料を取得・検証してから公開してください。

八幡浜市は[専用ガイド](yawatahama-data.md)、伊予市は[伊予市データガイド](iyo-data.md)、東温市は[東温市データガイド](toon-data.md)、上島町は[上島町データガイド](kamijima-data.md)、四国中央市は[四国中央市データガイド](shikokuchuo-data.md)に従って取得・生成・検証してください。未確認の収集日や搬出時刻を、別地区のデータで補完しません。

Flutterの自治体カタログ・分別表示設定を更新する場合は、公式データの整備後に次を実行します。
既存の松山市CSV・Embeddingは読み替え・再生成しません。

```bash
backend/.venv/bin/python scripts/generate_frontend_data.py
```

生成されるカタログと自治体別台帳はメタデータ、カレンダー・住所表は従来どおりGit管理外です。
新自治体の色・粗大ごみ案内などの追加項目と検証手順は
[Flutterの自治体データ契約](multi-municipality-flutter.md)を参照してください。

Knowledge Base連携・比較実験の入力形式は `infra/scripts/build_knowledge_records.py` と `backend/evaluation/README.md` を参照してください。現在の通常検索経路は両地域ともLambda同梱のTitan索引を候補取得に使います。中島の分類根拠は地域別ルールに切り替えます。

## AWS・アプリ反映前

上記の取得・生成・照合を済ませてから、`scripts/package_backend.sh` でLambda成果物を作成します。このスクリプトはバックエンドとFlutterのカレンダー原本のバイト一致も確認します。Terraformの `REGION_REGISTRY_PATH`、`CALENDAR_BUNDLE_PATH`、`NAKAJIMA_ITEMS_PATH` は同梱先を指す設定です。Terraform planとAPI回帰確認を行い、バックエンドの更新後に同じバージョンのFlutterをビルドして配布してください。APIとFlutterが別バージョンになる期間は地区・日付の不一致が起き得ます。公開環境への反映、Terraform apply、Bedrockの有償処理はこの手順の自動実行には含めません。

## 伊方町

伊方町の8公式PDF・全2,920日付セルと1,196公式品目の取得・検証・生成は[伊方町データガイド](ikata-data.md)を参照してください。専用CSV・NPZ・日付カレンダーはGit管理外で、原本URL・ハッシュ・補正記録・再生成スクリプトを追跡します。収集方法だけが決まっている粗大ごみを定期収集へ変換しません。大洲市・砥部町・愛南町を含む担当7自治体は、自治体専用索引の生成・検証後に有効化しました。件数、公式期間、Git管理外ファイル、再生成方法は[担当7自治体の接続ガイド](assigned-municipalities-completion.md)を参照してください。

## 新居浜市

新居浜市の1,349公式辞典行・15収集地区群・全5,475日付セルの取得・生成・照合は[新居浜市データガイド](niihama-data.md)を参照してください。新規cloneでは専用NPZの共有又は承認後の生成と、既存4自治体のGit管理外データも必要です。他メンバーの未登録自治体は有効化していません。

## 東温市

重信29・川内3の32公式PDF・全11,680日付と、辞典1,260行・説明例20行の取得・検証・再生成は[東温市データガイド](toon-data.md)を参照してください。両地域は市専用索引を共有し、体温計の収集区分と搬出時刻を切り替えます。一部計測器の収集日と重信の一部時刻は未確認として区別します。Git管理外のNPZとローカルOCRの再現・共有手順も記載しています。

## 上島町

弓削3・生名2・岩城2・魚島1の8選択地区、公式106品目例、全1,493日付レコードの取得・生成・照合は[上島町データガイド](kamijima-data.md)を参照してください。魚島だけは平日7:00～10:00のクリーンセンター持込として時刻を切り替えます。CSV・NPZ・公式原本・生成カレンダーはGit管理外で、専用索引を他自治体と共有しません。

## 四国中央市

川之江9・三島5・土居3・新宮3の20選択地区、公式402品目、全3,107日付レコードの取得・生成・照合は[四国中央市データガイド](shikokuchuo-data.md)を参照してください。公式表で太字・橙色の地区は朝7:00、それ以外は7:30とし、2026年度の公式休業日と三島地区の10月14日・15日収集例外を保持します。天候による臨時中止は事前生成しません。

## 久万高原町

公式辞典2,002行・説明例16行、23選択地区・22実日付カレンダーの取得・描画/OCR照合・再生成は[久万高原町データガイド](kumakogen-data.md)を参照してください。公式年度表と公式リンク先カレンダーを比較し、月別日付は年度表を優先します。2026年10月14日の電池案内を旧辞典より優先し、直接持込や現在の募集を確認する粗大ごみへ定期日付を付けません。CSV・NPZ・カレンダー・OCRバンドルはGit管理外で、他自治体の登録とデータは保持します。

## 西条市

公式分別表1,273行・説明例10行、39選択地区・25カレンダーの取得・独立検証・再生成は[西条市データガイド](saijo-data.md)を参照してください。新指定袋と2026年秋祭りの休止を反映します。随時収集3地区のびん・PET・スプレー缶は日付未確認として扱います。Git管理外のCSV・NPZ・カレンダー・OCRの共有／生成手順、承認済みの日付印字補正も記録しています。

## 今治市

通常地域855行＋説明例12行、関前203行＋説明例11行、233選択地区・44カレンダー（通常42・特別2）の取得・独立検証・再生成は[今治市データガイド](imabari-data.md)を参照してください。関前の現行ルールと通常地域の根拠を分離し、3島・鵜島の特別日程と搬出条件を保持します。2個のNPZ・OCRバンドルは共有可能ですが共有先は未固定です。CSV・カレンダー・Flutter資産は同じ原本から再生成できます。
