# 砥部町データの再生成と検証

砥部町（自治体コード `38402`）の公式分別辞典と2026年度くらしのカレンダーから、品目検索用CSV、地区台帳、日付指定カレンダーを再生成する手順です。

現在はデータ生成基盤までの実装です。Embedding索引は未生成で、`data/regions/catalog.json` へも登録していません。そのため既存自治体の検索・カレンダーには影響せず、砥部町はまだアプリの選択肢に表示されません。

## 対象地区

公式カレンダーの3列と、列内に明記された例外地域を分けて管理します。

- 麻生小校区（田ノ浦を除く）
- 宮内小・砥部小校区（大平・鵜ノ崎を除く）
- 広田地域（可燃ごみ週1回）
- 広田地域（可燃ごみ週2回）
- 田ノ浦
- 大平
- 鵜ノ崎

田ノ浦・大平・鵜ノ崎の「すべて」は通常地区の曜日へ展開せず、公式カレンダーにその表記がある日だけを別カレンダーへ登録します。広田地域の可燃ごみは、`週1・週2` と `週2` の表記を分離します。

## 分別とカレンダーの対応

分別辞典の14区分は品目検索でそのまま保持します。一方、公式カレンダー上で同日に収集される区分は次の7収集種別へ対応付けます。

| カレンダー表示 | 品目側の分別 |
| --- | --- |
| 可燃ごみ | 可燃ごみ |
| 剪定枝・葉・草 | 剪定枝・葉・草 |
| プラ製容器包装 | プラスチック製容器包装 |
| びん・缶・金属くず・ペットボトル | 空きびん、空き缶、金属くず、ペットボトル |
| 紙類・古着・古布 | 段ボール、紙パック、新聞・チラシ、雑誌・雑がみ、古着・古布 |
| 危険ごみ | 危険ごみ |
| 雑ごみ | 雑ごみ |

美化センター等への持込、拠点回収、町では処理できない品目は、定期収集へ変換しません。

## Gitで管理するもの

- `data/regions/tobe/official_rules.json`: 14分別、持込・排出禁止、出し方
- `data/regions/tobe/sources.json`: 公式原本のURLとSHA-256（レビュー後に作成）
- `data/regions/tobe/calendar_reviews.json`: 公開済み月の抽出結果（レビュー後に作成）
- `data/regions/tobe/registry.json`: 7地区の台帳（ビルド時に生成）
- `scripts/tobe_data.py`: 取得、生成、検証のワークフロー
- `scripts/tobe_pdf.py`: 分別辞典表・月別カレンダー表の抽出

公式HTML/PDF、生成カレンダー、品目CSV、Embedding索引は `.gitignore` の対象です。公式原文をリポジトリへ転載せず、公開・再配布前に砥部町の利用条件を確認します。

## 再生成手順

### 1. 公式原本を取得

```bash
backend/.venv/bin/python scripts/tobe_data.py fetch
```

Windowsでは `backend/.venv/Scripts/python.exe` に読み替えます。分別ページ、カレンダー一覧、分別辞典、分別帳、持込案内、許可業者案内と、現在公開されている2026年度の月別カレンダーを `data/regions/tobe/source/` に保存します。

カレンダー一覧には前年度の11～3月も残るため、先頭の最新月から4月まで連続する2026年度ブロックだけを取得します。未公開月のURLや収集日を推測しません。

### 2. 抽出候補を確認

```bash
backend/.venv/bin/python scripts/tobe_data.py inspect
```

次の候補を生成します。

- `generated/sources-candidate.json`
- `generated/review-candidate.json`

分別辞典は罫線付きの4列（品名・備考・分別・リサイクル）を読み取ります。月別カレンダーは、日付行と麻生小校区、宮内小・砥部小校区、広田地域の3列を読み取ります。OCRや曜日の繰り返し規則による推測は行いません。

公式一覧は2026年11月2日の取得時点で4～11月号までです。各号には翌月冒頭の行も含まれるため、現在の検証済み有効期間は2026年4月1日～12月6日です。今後の号が公開された場合は、原本ハッシュと日付を再レビューしてデータ版を更新します。

### 3. 台帳・カレンダー・品目CSVを生成

レビュー済み候補を `sources.json` と `calendar_reviews.json` に反映した後、次を実行します。

```bash
backend/.venv/bin/python scripts/tobe_data.py build
backend/.venv/bin/python scripts/tobe_data.py verify
```

`build` は、取得原本とレビュー済みSHA-256、公開月、日付ハッシュが一致しない場合に停止します。`verify` は公式PDFから全データを再抽出し、地区台帳、カレンダー、CSVを比較します。

## Embeddingとアプリ登録

Embedding生成はAWS Bedrockへの有償呼び出しなので、このワークフローからは実行しません。CSVのレビュー後、明示的な承認を得た場合だけ `scripts/build_regional_embeddings.py` で砥部町専用索引を生成します。

索引・manifest・カレンダー・品目CSVがすべて検証できてから、`data/regions/catalog.json` へ `38402` を追加し、Flutter用データを生成します。索引がない現在の段階では登録しません。

## 公式資料

- [ごみの分別と出し方](https://www.town.tobe.ehime.jp/soshikikarasagasu/chominka/gomi/871.html)
- [ごみ分別辞典PDF](https://www.town.tobe.ehime.jp/material/files/group/12/22532.pdf)
- [くらしのカレンダー](https://www.town.tobe.ehime.jp/gomi_search/4959.html)
- [美化センター・千里埋立処分場に持ち込むごみ](https://www.town.tobe.ehime.jp/kurashi_tetsuzuki/gomi_risaikuru_kankyo/1/1745.html)
- [一般廃棄物収集運搬許可業者](https://www.town.tobe.ehime.jp/soshikikarasagasu/chominka/gomi/850.html)
