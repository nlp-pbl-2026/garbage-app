# 松野町データの再生成と検証

松野町（自治体コード `38484`）の公式「家庭ごみ分別・分類ブック（令和8年4月版）」から、品目検索用CSV、地区台帳、2026年度の日付カレンダーを再生成する手順です。

現在はデータ生成基盤までの実装です。Embedding索引は未生成で、`data/regions/catalog.json` へも登録していません。そのため既存自治体の検索・カレンダーには影響せず、松野町はまだアプリの選択肢に表示されません。

## 公式資料の扱い

松野町のごみ案内ページは、2026年4月1日改定の分別・分類ブックと、2017年7月開始の単独カレンダーを同時に掲載しています。収集曜日や年末年始の休止日は新しい分別・分類ブックの3ページ目を正とし、古い単独カレンダーから2026年度の日付を生成しません。

公式PDFとHTMLは再現性確認のため取得しますが、松野町サイトの著作権表示に従い `source/` 配下をGit管理しません。URL、取得時のSHA-256、資料の役割だけを `sources.json` に記録します。

## 対象地区とカレンダー

公式表にある10部落と、吉野の例外地区である葛川を別の選択肢として管理します。

1. 松丸
2. 延野々
3. 豊岡後
4. 豊岡前
5. 富岡
6. 上家地
7. 目黒
8. 吉野（葛川地区を除く）
9. 葛川地区（吉野内）
10. 蕨生
11. 奥野川

毎週の曜日、毎月第1・第3、第2・第4などの規則を、2026年4月1日から2027年3月31日までの日付へ変換します。公式資料に記載された8月15日と12月31日～1月3日の休止日も反映します。

古紙は雨天時に収集されません。また、積雪やその他の事情による臨時変更は回覧・防災無線等で案内されるため、日付データから推測しません。全地区に `needs_local_confirmation` を設定し、利用者が最新情報を確認できる状態にしています。

## 分別データ

公式PDFの22～63ページにある罫線付き品目表を `pdfplumber` で抽出し、品名・分類・備考を1,434件の構造化データにします。PDF上で分類セルが次行へ結合されている場合も、同一品目へ戻してから分類を確定します。

公式の10分類をそのまま保持します。

- 可燃
- 不燃
- PET
- びん・かん
- 古紙
- 資源
- プラ
- 家電
- 粗大
- 禁止

「指定袋に入れば不燃」「汚れが落ちなければ可燃」のように備考で条件分岐する品目は、主分類を維持しながら `category_options` に候補を残します。素材、汚れ、袋に入る大きさ、電池の有無などが不明な場合、検索側で断定せず確認質問できる形です。

## Gitで管理するもの

- `data/regions/matsuno/official_rules.json`: 分類、排出方法、回答時の確認事項
- `data/regions/matsuno/sources.json`: 公式原本のURLとSHA-256
- `data/regions/matsuno/calendar_reviews.json`: 11地区の規則と生成日付のレビュー結果
- `data/regions/matsuno/item_reviews.json`: 1,434品目の件数・分類・内容ハッシュ
- `data/regions/matsuno/registry.json`: 地区台帳とルールプロファイル
- `scripts/matsuno_data.py`: 取得、生成、検証のワークフロー
- `scripts/matsuno_pdf.py`: 罫線付き品目表の抽出処理

公式HTML/PDF、生成カレンダー、品目CSV、Embedding索引は `.gitignore` の対象です。

## 再生成手順

### 1. 公式原本を取得

```bash
backend/.venv/bin/python scripts/matsuno_data.py fetch
```

Windowsでは `backend/.venv/Scripts/python.exe` に読み替えます。公式案内、現行の分別・分類ブック、比較用の旧カレンダー、著作権ページを `data/regions/matsuno/source/` に保存します。

### 2. 抽出候補を確認

```bash
backend/.venv/bin/python scripts/matsuno_data.py inspect
```

`generated/` にソース、カレンダー、品目のレビュー候補を生成します。候補を公式PDFへ照合してから、`sources.json`、`calendar_reviews.json`、`item_reviews.json` へ反映します。

### 3. 台帳・カレンダー・品目CSVを生成

```bash
backend/.venv/bin/python scripts/matsuno_data.py build
backend/.venv/bin/python scripts/matsuno_data.py verify
```

`build` は原本ハッシュ、レビュー済み日付、レビュー済み品目ハッシュのいずれかが変わると停止します。`verify` は公式原本から再抽出した内容を、地区台帳、生成カレンダー、品目CSVと比較します。

## Embeddingとアプリ登録

Embedding生成はAWS Bedrockへの有償呼び出しなので、このワークフローからは実行しません。品目CSVのレビュー後、明示的な承認を得た場合だけ松野町専用索引を生成します。

索引、manifest、カレンダー、品目CSVがすべて検証できてから、`data/regions/catalog.json` へ `38484` を追加し、Flutter用データを生成します。索引がない現在の段階では登録しません。

## 公式資料

- [松野町：家庭ごみの収集及び直接搬入について](https://www.town.matsuno.ehime.jp/soshiki/9/1333.html)
- [松野町：家庭ごみ分別・分類ブック（令和8年4月版）](https://www.town.matsuno.ehime.jp/uploaded/attachment/7083.pdf)
- [松野町：ホームページの著作権](https://www.town.matsuno.ehime.jp/soshiki/1/1176.html)
