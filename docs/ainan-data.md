# 愛南町データの再生成と検証

愛南町（自治体コード `38506`）の公式「家庭ごみの分別早見表」と2026年収集日程から、品目検索用CSV、8ブロックの地区台帳、日付指定カレンダーを再生成する手順です。

現在はデータ生成基盤までの実装です。Embedding索引は未生成で、`data/regions/catalog.json` へも登録していません。そのため既存自治体の検索・カレンダーには影響せず、愛南町はまだアプリの選択肢に表示されません。

## 対象地区

公式ページの8ブロックをそのまま地区台帳として管理します。

1. 長月第1～4、上・下永ノ岡、和口第1・2、馬場、上町、本町、寺新町、栄町、貝塚、八幡野
2. 菊川第1～4、平山、長洲、長崎、節崎、馬瀬、深泥、防城成川、赤水、高畑、尻貝、奥の谷、中の谷、高手、灘前、左右水、猿鳴
3. 僧都、山出、梶郷上・下、大道上・下、樫床、樋口、西柳、岡、中緑、当時、下緑、左谷、太場、土居、三島団地、蓮乗寺、東浜、中組、奥前、西浜、鼻前、垣内、岩水、敦盛、柿ノ浦、大浜、中玉、脇本
4. 豊田、石井手、神越、中の谷、鼻、下長野、伊勢町
5. 矢ノ町1～3、中町上・下、北裡、後1～3、清水、沖1・2、中原、松本、久保、鳥越、古月、鯆越、日土、大寿浦、真浦、西真浦、新浦
6. 一本松全域
7. 内海全域
8. 西海全域

ブロック6はブロック2、ブロック7はブロック4、ブロック8はブロック1と同じ収集規則です。可燃ごみは週3回、びん・缶、ペットボトル、不燃物は毎月第N曜日の規則から2026年の日付を生成します。

新聞・雑誌・ダンボール・廃乾電池は、8ブロックとは別の10収集地区と集積場所で管理されています。対応関係を推測できないため、8ブロックのカレンダーには混在させず、検索回答で公式の別日程を確認するよう案内します。

## 分別データ

公式PDFの4～36ページにある罫線付き表を200dpiで画像化し、Windows日本語OCRの座標と分類欄の公式色を組み合わせて977品目を抽出します。分類は次の9種類です。

- 可燃
- びん・缶
- ペットボトル
- 不燃
- 古紙
- 資源（乾電池）
- 小型家電
- 粗大
- 禁止

複数色の分類欄は主分類だけに丸めず、`category_options` に代替区分を保持します。公式Webページに掲載された訂正11件も適用します。OCRで誤認しやすい濁点、長音、複雑な品名は、ページ番号付きの明示的な補正表で原本どおりに直します。

## Gitで管理するもの

- `data/regions/ainan/official_rules.json`: 分別、排出方法、収集上の注意
- `data/regions/ainan/sources.json`: 公式原本のURLとSHA-256
- `data/regions/ainan/calendar_reviews.json`: 8ブロックの規則と生成日付のレビュー結果
- `data/regions/ainan/item_reviews.json`: 977品目の件数・分類・内容ハッシュ
- `data/regions/ainan/registry.json`: 8ブロックの地区台帳
- `scripts/ainan_data.py`: 取得、抽出、生成、検証のワークフロー
- `scripts/ainan_pdf.py`: 罫線、OCR座標、分類色による分別表の抽出
- `scripts/ainan_windows_ocr.ps1`: Windows日本語OCRの座標出力

公式HTML/PDF、生成カレンダー、品目CSV、Embedding索引は `.gitignore` の対象です。愛南町Webサイトの利用条件に従い、公式原文をリポジトリへ転載しません。

## 再生成手順

### 1. 公式原本を取得

```bash
backend/.venv/bin/python scripts/ainan_data.py fetch
```

Windowsでは `backend/.venv/Scripts/python.exe` に読み替えます。公式の収集日程、分別ページ、分別早見表、分別ガイド、古紙・廃乾電池日程、利用条件を `data/regions/ainan/source/` に保存します。

### 2. 抽出候補を確認

```bash
backend/.venv/bin/python scripts/ainan_data.py inspect
```

次の候補を生成します。

- `generated/sources-candidate.json`
- `generated/calendar-review-candidate.json`
- `generated/item-review-candidate.json`
- `generated/items-candidate.json`

候補の原本ハッシュ、8ブロック、収集規則、件数、OCR品名、分類色、備考を公式資料と照合します。レビュー後の内容だけを `sources.json`、`calendar_reviews.json`、`item_reviews.json` に反映します。

### 3. 台帳・カレンダー・品目CSVを生成

```bash
backend/.venv/bin/python scripts/ainan_data.py build
backend/.venv/bin/python scripts/ainan_data.py verify
```

`build` は公式原本のSHA-256、レビュー済みカレンダー、レビュー済み品目ハッシュのいずれかが変わると停止します。`verify` は公式原本から再抽出した内容を、地区台帳、生成カレンダー、品目CSVと比較します。

## Embeddingとアプリ登録

Embedding生成はAWS Bedrockへの有償呼び出しなので、このワークフローからは実行しません。品目CSVのレビュー後、明示的な承認を得た場合だけ `scripts/build_regional_embeddings.py` で愛南町専用索引を生成します。

索引、manifest、カレンダー、品目CSVがすべて検証できてから、`data/regions/catalog.json` へ `38506` を追加し、Flutter用データを生成します。索引がない現在の段階では登録しません。

## 公式資料

- [愛南町：ごみ収集日程](https://www.town.ainan.ehime.jp/kurashi/tetsuduki/kankyoeisei/gomi/gomishushunittei.html)
- [愛南町：家庭ごみ分別早見表と訂正](https://www.town.ainan.ehime.jp/kurashi/tetsuduki/kankyoeisei/gomi/R412bunbetsu.html)
- [愛南町：ホームページの著作権・リンク](https://www.town.ainan.ehime.jp/kurashi/hpnitsuite/chosakuken/)
