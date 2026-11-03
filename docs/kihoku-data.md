# 鬼北町データの再生成と検証

鬼北町（自治体コード `38488`）の公式「家庭ごみの分別早見表」と地区別収集曜日から、品目検索用CSV、8地区組合せの台帳、2026年4月以降の日付カレンダーを再生成する手順です。

現在はデータ生成基盤までの実装です。Embedding索引は未生成で、`data/regions/catalog.json` へも登録していません。そのため既存自治体の検索・カレンダーには影響せず、鬼北町はまだアプリの選択肢に表示されません。

## 対象地区

公式HTMLの燃えるごみ・燃えないごみ・ペットボトル・びん缶の組合せを崩さず、次の8区分で管理します。

1. 泉地区
2. 愛治地区
3. 好藤地区（年則を含む）
4. 三島地区
5. 日吉地区
6. 近永地区（栄町・旭町）
7. 近永地区（新町・本町・南町・鬼北の里）
8. 近永地区（牛野川・水分・北川・成川・今在家・奈良・芝・中野川・永野市）

燃えるごみと燃えないごみは毎週の曜日、ペットボトルは毎月第1・第3または第2・第4金曜日、びん・缶は全地区水曜日として、2026年4月1日から12月31日までの日付へ変換します。公式ページは年間の日付入りカレンダーではないため、休日・年末年始などの臨時変更は推測しません。地区は利用者自身で公式情報と照合できるよう、全件を `needs_local_confirmation` としています。

## 分別データ

公式PDFの3～31ページにある2列表をPopplerの座標付きTSVへ変換し、品名・分類・備考を抽出します。分類は次の8種類です。

- 可燃
- 不燃
- びん・缶
- ペットボトル
- 古紙
- 資源
- 粗大
- 禁止

さらに、令和8年4月から始まった「きれいなプラスチック」と「小型充電式電池」の現行ルールを分類規則へ追加しています。きれいなプラスチックは地区別拠点回収を利用できますが、公式案内どおり従来の可燃ごみも選べます。小型充電式電池は端子を絶縁し、膨らんだ電池は事務所へ直接持ち込むなど、専用資料の条件を保持します。

早見表より新しい公式案内を優先するため、充電式電池に該当する7品目は現行の専用回収へ補正します。また、公式資料の例示品と品名でプラスチック製と確認できる計125品目には、可燃を維持したまま「きれいなプラスチック」を条件付き候補として追加します。対象外条件や素材が不明なときは、拠点回収と断定せず確認が必要です。

## Gitで管理するもの

- `data/regions/kihoku/official_rules.json`: 分別、排出方法、2026年開始の追加ルール
- `data/regions/kihoku/sources.json`: 公式原本のURLとSHA-256
- `data/regions/kihoku/calendar_reviews.json`: 8地区の規則と生成日付のレビュー結果
- `data/regions/kihoku/item_reviews.json`: 1,219品目の件数・分類・内容ハッシュ
- `data/regions/kihoku/registry.json`: 8地区の台帳
- `scripts/kihoku_data.py`: 取得、生成、検証のワークフロー
- `scripts/kihoku_pdf.py`: 2列品目表の座標抽出

公式HTML/PDF、生成カレンダー、品目CSV、Embedding索引は `.gitignore` の対象です。鬼北町サイトの著作権表示に従い、公式原文をリポジトリへ転載しません。

## 再生成手順

### 1. 公式原本を取得

```bash
backend/.venv/bin/python scripts/kihoku_data.py fetch
```

Windowsでは `backend/.venv/Scripts/python.exe` に読み替えます。公式の分別ページ、資源回収、粗大ごみ、品目早見表、きれいなプラスチック、小型充電式電池、利用条件を `data/regions/kihoku/source/` に保存します。

### 2. 抽出候補を確認

```bash
backend/.venv/bin/python scripts/kihoku_data.py inspect
```

`generated/` にソース、カレンダー、品目のレビュー候補を生成します。候補を公式HTMLとPDFへ照合してから、`sources.json`、`calendar_reviews.json`、`item_reviews.json` へ反映します。

### 3. 台帳・カレンダー・品目CSVを生成

```bash
backend/.venv/bin/python scripts/kihoku_data.py build
backend/.venv/bin/python scripts/kihoku_data.py verify
```

`build` は原本ハッシュ、レビュー済み日付、レビュー済み品目ハッシュのいずれかが変わると停止します。`verify` は公式原本から再抽出した内容を、地区台帳、生成カレンダー、品目CSVと比較します。

## Embeddingとアプリ登録

Embedding生成はAWS Bedrockへの有償呼び出しなので、このワークフローからは実行しません。品目CSVのレビュー後、明示的な承認を得た場合だけ鬼北町専用索引を生成します。

索引、manifest、カレンダー、品目CSVがすべて検証できてから、`data/regions/catalog.json` へ `38488` を追加し、Flutter用データを生成します。索引がない現在の段階では登録しません。

## 公式資料

- [鬼北町：ごみの出し方・地区別収集曜日](https://www.town.kihoku.ehime.jp/soshiki/kankyou/58.html)
- [鬼北町：資源ごみの回収方法](https://www.town.kihoku.ehime.jp/soshiki/kankyou/264.html)
- [鬼北町：きれいなプラスチックごみ拠点回収](https://www.town.kihoku.ehime.jp/soshiki/kankyou/33929.html)
- [鬼北町：リチウムイオン電池等の分別回収](https://www.town.kihoku.ehime.jp/soshiki/kankyou/34157.html)
- [鬼北町：多量ごみ・粗大ごみ](https://www.town.kihoku.ehime.jp/soshiki/kankyou/15663.html)
- [鬼北町：ホームページの利用・著作権](https://www.town.kihoku.ehime.jp/site/userguide/info.html)
