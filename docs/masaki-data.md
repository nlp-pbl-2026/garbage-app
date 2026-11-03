# 松前町データの再生成と検証

松前町（自治体コード `38401`）の公式分別資料と令和8年度ごみカレンダーから、品目検索用CSV、地区台帳、日付指定カレンダーを再生成する手順です。

現在はデータ生成基盤までの実装です。Embedding索引は未生成で、`data/regions/catalog.json` へも登録していません。そのため既存自治体の検索・カレンダーには影響せず、松前町はまだアプリの選択肢に表示されません。

## 対象地区

公式カレンダーと令和8年度一般廃棄物処理実施計画に合わせ、次の2地区を管理します。

- 松前校区
- 北伊予・岡田校区

可燃ごみ、紙類、かん、びん、金属・スプレー缶、古着・古布、有害ごみ、埋立ごみは共通です。ペットボトル、プラスチック類、せんてい枝の曜日だけが地区により異なります。

住所から校区を確定する公式対応表は今回の資料に含まれないため、両地区とも `needs_local_confirmation` を設定しています。地区選択時は利用者が公式資料または現地で校区を確認します。

## 分別品目と現行ルール

令和3年度改訂版「ごみ分別の手引き」の物理ページ20～38にある罫線付き早見表から、1,384品目を抽出します。PDFの一部フォントは通常のPDFライブラリで文字化けするため、PopplerでUnicode文字を取得し、PyMuPDFで罫線座標を取得して各セルを対応付けます。OCRは使いません。

手引きの品目名と主分類は保持しますが、令和5年4月から変更されたプラスチック製容器包装のルールを優先します。旧手引きに残る「汚れが取れないときは可燃」などの記述32件は検索データから除き、次の現行案内へ置き換えます。

> 中身を使い切り、汚れを取り除いてプラスチック類へ出す。紙・金属など異素材の部品は材質別に分ける。

紙製部品やプラマークのない非容器包装など、材質そのものにより可燃となる別条件は維持します。

## カレンダーの検証

令和8年度カレンダーの月別グリッド（PDF物理ページ3、5、7～10）を2地区とも目視確認し、令和8年度実施計画の毎週・第N曜日規則から日付を生成します。カレンダーに「収集休み」と印刷された次の日付は明示的な例外として除外します。

| 日付 | 松前校区 | 北伊予・岡田校区 |
| --- | --- | --- |
| 2026-12-31 | 可燃ごみ休み | 可燃ごみ休み |
| 2027-01-01 | ペットボトル休み | プラスチック類休み |
| 2027-01-02 | かん類休み | かん類休み |
| 2027-01-16 | 有害ごみ休み | 有害ごみ休み |

祝日でも「収集休み」の表示がない日は公式カレンダーどおり収集日に残します。臨時の天候・運用変更は推測せず、町の最新案内を確認します。

## Gitで管理するもの

- `data/regions/masaki/official_rules.json`: 現行分別ルールと17分類
- `data/regions/masaki/sources.json`: 公式原本のURLとSHA-256
- `data/regions/masaki/calendar_reviews.json`: 2地区の規則、例外日、生成結果ハッシュ
- `data/regions/masaki/item_reviews.json`: 1,384品目の抽出監査結果
- `data/regions/masaki/registry.json`: 2地区の台帳
- `scripts/masaki_data.py`: 取得、生成、検証ワークフロー
- `scripts/masaki_pdf.py`: 分別早見表の抽出

公式HTML/PDF、生成カレンダー、品目CSV、Embedding索引は `.gitignore` の対象です。公式原文をリポジトリへ転載せず、公開・再配布前に松前町へ利用条件を確認します。

## 再生成手順

Windowsでは次を実行します。

```powershell
backend/.venv/Scripts/python.exe scripts/masaki_data.py fetch
backend/.venv/Scripts/python.exe scripts/masaki_data.py inspect
backend/.venv/Scripts/python.exe scripts/masaki_data.py build
backend/.venv/Scripts/python.exe scripts/masaki_data.py verify
```

`inspect` はレビュー候補を `data/regions/masaki/generated/` に作成します。レビュー済みの `sources.json`、`calendar_reviews.json`、`item_reviews.json` と候補が一致しない限り、`build` と `verify` は成功しません。

## Embeddingとアプリ登録

Embedding生成はAWS Bedrockへの有償呼び出しなので、このワークフローからは実行しません。品目CSVの確認後、明示的な承認を得た場合だけ松前町専用索引を生成します。

索引、manifest、カレンダー、品目CSVがすべて検証できてから `data/regions/catalog.json` へ自治体コード `38401` を追加し、Flutter用データを生成します。索引がない現在の段階では登録しません。

## 公式資料

- [令和8年度ごみカレンダー](https://www.town.masaki.ehime.jp/site/hikkoshisumai/gomi-calendar-h30.html)
- [ごみ分別の手引き](https://www.town.masaki.ehime.jp/uploaded/attachment/16014.pdf)
- [ごみ分別表（日本語版）](https://www.town.masaki.ehime.jp/uploaded/attachment/21989.pdf)
- [令和8年度一般廃棄物処理実施計画](https://www.town.masaki.ehime.jp/uploaded/attachment/24411.pdf)
- [粗大ごみの申込み](https://www.town.masaki.ehime.jp/site/gomi/10385.html)
