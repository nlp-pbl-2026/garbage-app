# 伊予市・2026年度データ

自治体IDは `38210`、版は `iyo-2026.1`、適用期間は2026-04-01～2027-03-31です。伊予・双海・中山の公式PDF3種類を、収集曜日・回数・例外の異なる16選択地区／16カレンダーに展開します。他市の品目・索引・分別規則は流用しません。

## 出典と対応範囲

- [収集日・2026年度カレンダー](https://www.city.iyo.lg.jp/shiminseikatsu/kurashi/gomi/shushubi/index.html)：伊予・双海・中山各2ページ。通常の曜日・第N回目の曜日、年末年始表と搬出期限を確認しました。
- [ごみ分別の手引き・辞典](https://www.city.iyo.lg.jp/kankyohozen/bunbetu.html)：50音順一覧は見出しを除いて1,697品目。分類・注意書き・PDFページ／セル座標を保持します。更新ページ等の確認済み説明例6件を加え、検索索引は1,703行です。分類が運搬条件で変わる家具の説明例は、固定分類を持たず条件付き分類コードを持ちます。
- [粗大ごみ申込方法](https://www.city.iyo.lg.jp/shiminseikatsu/kurashi/gomi/bunbetsu/sodai/dashikata/calendar.html)：偶数月14日／28日の地域別申込期限、翌奇数月の収集、はがき・電子申請、1回5点・年30点、通知はがきで指定日を確認する方式を案内します。公式PDFでは戸別収集無料。直接搬入・許可業者の費用は別です。
- [分別変更](https://www.city.iyo.lg.jp/kankyohozen/gomibunnbetu.html)、[充電池](https://www.city.iyo.lg.jp/kankyohozen/li-ion.html)、[FAQ](https://www.city.iyo.lg.jp/kankyohozen/gomidasi.html)：シュレッダー紙、取り外せる／外せない充電池、小型シール鉛蓄電池等を確認しました。

URL・取得日時・SHA-256は `data/regions/iyo/sources.json` に記録します。資料の利用・加工・再配布条件は未確認です。

定期収集9区分は燃えるごみ、プラスチック製容器包装、紙類、かん類、びん類、布類、ペットボトル、有害ごみ、燃えないその他ごみ。搬出期限はすべて **8:30** です。粗大ごみ・禁止品には定期収集日を付けません。粗大ごみの正確な収集日は通知はがきに従い、奇数月という規則から日付を推測しません。

**平岡・鵜崎（`38210-iyo-hiraoka`）**は「燃えないごみは毎月第2火曜」と注記されていますが、通常の第2回欄にある布類・かん類以外の区分との対応を一意に確認できません。燃えるごみ・プラ・布類・かん類は利用でき、びん・PET・燃えないその他・有害・紙類の5区分は収集日未確認です。分類の回答は可能ですが、該当区分の検索結果とカレンダーに未確認を表示し、通知・iCalは生成しません。環境政策課（089-909-6338）で確認できたら別版で更新します。地区選択画面には地名だけを表示します。

GPS・住所だけで収集地区を確定できる境界・住所表は整備していません。手動選択を利用し、別市や別地区から補完しません。粗大ごみの申込みは公式サイトで行い、アプリ内記録は手動管理です。

## 抽出・検証の方法

`scripts/collection_recurrence.py` はISO曜日と月内の第1～5回目を展開する共通処理です。ISO週番号は使いません。祝日は自動的に休みにせず、明示された休業日・日付ごとの置換を優先します。実行時のバックエンド・Flutterは展開済みの共通原本を読み、翌年度へ延長しません。

通常欄は規則から生成した日付と、PDFから別に読み取った実日付文字・区分色・文字を比較します。PDF内の隠れた古い背景色は描画画像で除外します。3 PDFの1,095日付文字を確認し、16地区の5,840日付を整備します。そのうち5,529地区日付は通常欄の描画色・文字、183地区日付は年末年始の明示表と照合します。同一マスに第5・6週を併記する128地区日付（各地区8日）は、色だけでは分離できないため、実日付文字と公式見出しの曜日・回数指定で確認します。これを128マス独立した色判定済みとは扱いません。平岡・鵜崎の未確認5区分は検証対象の収集日を作りません。

品目表は全分類セルを列挙し、文字・色・件数を照合します。凡例と異なる灰色の禁止55行も対象です。「租大」2件・「ブラ」1件は、元の文字を保持したうえで凡例・描画色と目視照合した箇所だけを補正します。原本更新・未知の分類・レイアウト変更は停止します。共通の出し方はEmbedding生成テキストに含めず、条件付き分類コードは品目固有の明示された区分だけから作ります。ふた・ラベルの分類を本体の選択肢へ自動追加しません。

`calendar_reviews.json` は照合結果を固定した記録です。`inspect` の候補を無条件に承認済みへコピーしたり、ハッシュだけ書き換えて更新を通したりしないでください。年度・公式資料の改訂は、資料と影響範囲を確認してから別版として扱います。

## Gitと生成物

| 対象 | Git | 用途／再現方法 |
| --- | --- | --- |
| `data/regions/iyo/{sources,calendar_rules,calendar_reviews,official_rules,registry}.json` | 含む | 出典、地区対応、規則、例外、検証記録、分別・粗大案内 |
| `knowledge/index_manifest.json` | 含む | CSV／索引ハッシュ、件数、モデル・次元 |
| `search_review.json` | 含む | 実API評価の件数、対象版、修正履歴、評価の限界（過去の生ログは含まない） |
| `source/` | 含まない | 公式HTML・PDF・画像24ファイル。`fetch` で取得 |
| `knowledge/items.csv` | 含まない | `build` で生成する1,703検索行 |
| `knowledge/item_embeddings.npz` | 含まない | 承認済みファイルの共有、又は別途承認した有償生成 |
| `generated/` | 含まない | 共通カレンダー、検証結果、抽出座標、生成チェックポイント・評価ログ |
| Flutterのカタログ・伊予市台帳 | 含む | `generate_frontend_data.py` で生成するメタデータ |
| Flutterの伊予市カレンダー | 含まない | バックエンド原本のバイト単位の複製 |

追跡対象にも公式資料を加工した設定・文章を含みます。除外ファイルを置くだけでは公開条件の確認が済んだことにはなりません。

## 新規cloneからの再生成

リポジトリルートから実行します。まず[既存2市のセットアップ](yawatahama-data.md#新規cloneからの取得再生成)の手順1～4に従い、Python環境・松山市データ・八幡浜市データを配置してください。標準カタログを処理するため、Flutter生成とパッケージ検査には全登録市のデータが必要です。既存2市のEmbeddingは再生成しません。

```bash
# Python 3.12 + backend/.venv（既存ガイドの uv sync --frozen --group dev）
backend/.venv/bin/python scripts/iyo_data.py fetch
backend/.venv/bin/python scripts/iyo_data.py build
backend/.venv/bin/python scripts/iyo_data.py verify --without-index
backend/.venv/bin/python scripts/generate_frontend_data.py
```

`fetch` は公式24ファイルを取得して既知のハッシュと照合し、差異があれば上書きを止めます。公式側で改訂された場合は、確認済み原本の共有又は新版の再検証が必要です。`verify --without-index` は資料・CSV・カレンダーの検査であり、バックエンド検索の準備完了を意味しません。Flutterカレンダーの表示だけなら索引は不要です。

ローカルバックエンドには、作成者から現在のマニフェストに対応する **伊予市のNPZ** を受け取り、次の場所に配置します。共有場所はリポジトリに含まれないため、この受け渡しは手作業です。原本・CSV・カレンダー・過去ログの受け渡しは不要です。

```bash
cp /path/to/shared/item_embeddings.npz data/regions/iyo/knowledge/item_embeddings.npz
backend/.venv/bin/python scripts/iyo_data.py verify
```

共有できない場合だけ、費用・認証を別途承認して有償生成します。通常のセットアップ・テストから呼びません。チェックポイントは同じEmbedding生成文の再計算を避けます。再生成した索引のバイト列は同一とは限らず、新しいCSV／NPZに対応するマニフェストも検証・管理してください。

```bash
# 有償。実行前に承認が必要。
backend/.venv/bin/python scripts/build_regional_embeddings.py \
  --source data/regions/iyo/knowledge/items.csv \
  --output data/regions/iyo/knowledge/item_embeddings.npz \
  --municipality 38210 --profile citywide \
  --checkpoint data/regions/iyo/generated/embedding-checkpoint.jsonl \
  --max-calls 1750 --budget-usd 0.70
backend/.venv/bin/python scripts/iyo_data.py verify
```

利用可能な自治体はカタログに登録済みです。将来の新規登録では `activate` がCSV・索引・全地区の検証を通してから登録します。未整備の索引や確認前のカレンダーで有効にしません。共通原本とFlutter資産の一致を確認して起動します。

```bash
backend/.venv/bin/python scripts/generate_frontend_data.py
cd backend
USE_BEDROCK_KNOWLEDGE_BASE=false LEXICAL_SEARCH_ENABLED=false \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# 別ターミナル
cd frontend
flutter pub get
flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

検索では実Bedrockへの接続・利用料が必要です。今回AWS側は更新していないため、既存の公開APIに接続するだけでは伊予市が使えるとは限りません。通知・GPS・共有シートの実機動作やアプリ配布は別途確認してください。

## テスト

通常の単体テストは外部資料・外部APIに依存しません。公式資料を配置した照合は明示的に別実行します。

```bash
backend/.venv/bin/python -m pytest backend/tests -q
backend/.venv/bin/python scripts/iyo_data.py verify
backend/.venv/bin/python -m pytest backend/official_tests/verify_iyo_runtime.py -q
cd frontend
flutter test
flutter test tool/verify_iyo_data_test.dart tool/verify_yawatahama_data_test.dart
flutter analyze
flutter build web
```

`verify_iyo_data_test.dart` は16地区・5,840日付の共通原本との一致、8:30期限、未確認5区分の予定除外、8月24日／31日の紙類を検査します。これはFlutterの読込結果と原本の整合性検査であり、公式PDFとの照合はPython側で別に行います。

実API評価は初回24例中20例、最初の修正後8例中6例でした。PET本体と付属品の混同、不要なプラマーク質問、家具の運搬条件を修正し、最終1,703行の索引ではストロー・運べる家具・運べない家具・PET本体の4例がすべて想定どおりでした。初回のガラスびんの「はい」、画像検索、既存2市の回帰例も確認していますが、最終版で全24例を再実行したわけではありません。画像評価は公式イラストを使用しています。全1,697品目の実検索精度や実物写真の精度を保証する評価ではありません。詳細は `search_review.json` を参照してください。
