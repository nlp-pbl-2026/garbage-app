# 上島町データガイド

上島町（自治体ID `38356`）の公式「家庭ごみの正しい出し方」と、弓削・生名・岩城・魚島の地区別案内から、分別品目、8選択地区、8カレンダーを整備します。対応期間は `2026-04-01`～`2027-03-31` です。別自治体の分類・索引・収集日を流用しません。

## 対応範囲

| 地域 | 選択地区 | 収集方法 |
| --- | ---: | --- |
| 弓削 | 3 | 燃やせるごみ、ビン・ガラス・陶器、缶、金属・有害、古紙、粗大ごみの地区別曜日 |
| 生名 | 2 | 南北で異なる燃やせるごみ曜日と、島内共通の各区分曜日 |
| 岩城 | 2 | A・Bで異なる燃やせるごみ曜日と、島内共通の各区分曜日 |
| 魚島 | 1 | 月～金曜日の7:00～10:00に魚島クリーンセンターへ持込 |

公式資料に名称がある106品目例を14分類へ整備しました。定期予定を持つ8収集区分と、家電リサイクル、最終処分場搬入、町で処理できない物を区別します。ペットボトルが燃やせるごみ、LED電球がガラス類、充電用電池が町収集外であることも自治体固有の根拠として保持します。植木鉢と段ボールなど8件は状態・量により分類が変わる条件付き品目です。

カレンダーは公式4地区表の毎週・第N曜日・奇数月・偶数月の規則を実日付へ展開し、8カレンダー・1,493日付レコードを生成します。公式表に祝日、年末年始、臨時変更の例外は記載されていないため、例外を推測していません。公式案内が更新された場合は、原本ハッシュと規則を再確認して再生成してください。

## 公式資料と確認方法

- [上島町：家庭ごみの正しい出し方](https://www.town.kamijima.lg.jp/soshiki/5/665.html)
- [弓削地区](https://www.town.kamijima.lg.jp/uploaded/attachment/6620.pdf)
- [生名地区](https://www.town.kamijima.lg.jp/uploaded/attachment/6621.pdf)
- [岩城地区](https://www.town.kamijima.lg.jp/uploaded/attachment/6622.pdf)
- [魚島地区](https://www.town.kamijima.lg.jp/uploaded/attachment/6623.pdf)
- [上島町サイトの著作権](https://www.town.kamijima.lg.jp/site/userguide/1434.html)

取得URL、取得日、SHA-256は `data/regions/kamijima/sources.json` に固定しています。4地区表を180dpiで描画して目視し、地区名、曜日、第N週、奇偶月、搬出・受入時刻を確認しました。品目は公式ガイドの名称例と明示された除外を転記し、PDFテキストとも照合しています。これは確認した資料内の名称例の全件であり、網羅的な品目辞典ではありません。

町サイトは掲載内容の転載・再利用に許可が必要と案内しています。原本PDF・HTML、転記CSV、生成カレンダー、Embedding索引はGit管理外です。公開リポジトリ、配布アプリ、Lambdaへ同梱する前に上島町へ利用条件を確認してください。

## ファイル構成

| パス | 内容 | Git |
| --- | --- | --- |
| `data/regions/kamijima/registry.json` | 8地区、2分別設定、分類・時刻・粗大ごみ案内 | 追跡 |
| `sources.json`、`official_rules.json`、`calendar_reviews.json`、`item_reviews.json` | 出典、公式ルール、照合記録 | 追跡 |
| `knowledge/index_manifest.json` | CSV・NPZ・モデル・次元の整合性 | 追跡 |
| `search_cases.json`、`search_evaluation.json` | 実検索の入力・期待・結果・費用 | 追跡 |
| `source/` | 公式PDF・HTML | 除外 |
| `generated/calendar-2026.json`、`generated/addresses.json` | バックエンド・Flutter共通の生成データ | 除外 |
| `knowledge/items.csv`、`knowledge/item_embeddings.npz` | 106品目と専用Titan索引 | 除外 |
| `frontend/assets/data/municipality_38356_*` | Flutter用台帳、カレンダー、住所候補 | 台帳は追跡、カレンダー・住所候補は除外 |

## 新規cloneでの再生成

Python依存関係を用意した後、リポジトリのルートで実行します。`fetch`、`build`、`verify --without-index` はBedrockを呼びません。

```powershell
backend\.venv\Scripts\python.exe scripts\kamijima_data.py fetch
backend\.venv\Scripts\python.exe scripts\kamijima_data.py build
backend\.venv\Scripts\python.exe scripts\kamijima_data.py verify --without-index
```

Embedding生成は有料です。事前承認後に Titan Text Embeddings V2（`amazon.titan-embed-text-v2:0`、1,024次元）を使用します。新規生成では106成功呼び出しを見込み、再試行を含む上限を112回、費用上限をUS$0.02とします。

```powershell
backend\.venv\Scripts\python.exe scripts\build_regional_embeddings.py `
  --source data\regions\kamijima\knowledge\items.csv `
  --output data\regions\kamijima\knowledge\item_embeddings.npz `
  --municipality 38356 --profile citywide `
  --checkpoint data\regions\kamijima\generated\titan-checkpoint.jsonl `
  --max-calls 112 --budget-usd 0.02 --workers 4
backend\.venv\Scripts\python.exe scripts\kamijima_data.py verify
backend\.venv\Scripts\python.exe scripts\generate_frontend_data.py `
  --municipality-id 38356 --merge-existing
```

今回の索引生成は106回成功、入力16,534トークン、推定US$0.00033068でした。認証期限切れでモデル到達前に9件の予約記録が残ったため、manifestの保守的予約値は115件・US$0.011477です。生成済みNPZを安全な経路で共有する場合は再生成不要ですが、`items.csv` とmanifestのSHA-256が一致することを必ず確認してください。

## 検索評価と残る確認

2026年11月7日に、Titan Text Embeddings V2とNova Lite（`amazon.nova-lite-v1:0`）を使い14件を実API経路で評価しました。全件HTTP 200で、ペットボトル、LED電球、びん、スプレー缶、充電池、蛍光管、乾湿段ボール、植木鉢の少量・多量、ガスコンロ、冷蔵庫、バイクの13件は期待どおりでした。

未指定量の「陶器の植木鉢」1件だけ、追加質問ではなく陶器類と回答しました。条件付き品目の量が未指定なら「少量ですか、それとも多量ですか？」と必ず確認するガードと回帰テストを追加しました。承認済み42モデル呼び出しを使い切ったため、修正後の実Bedrock追試は行っていません。追試には新たな費用承認が必要です。評価42回（Nova 28、Titan 14）と索引生成を合わせた推定実費はUS$0.00362488、保守的予約額はUS$0.0147712で、承認上限US$0.07以内です。

## ローカル検証

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_kamijima_data.py -q
backend\.venv\Scripts\python.exe -m pytest backend\official_tests\verify_kamijima_runtime.py -q
cd frontend
flutter test tool\verify_kamijima_data_test.dart
```

Flutter検証は8地区、全1,493日付、地区表示名、魚島の受入時間、住所候補の曖昧性、粗大ごみ案内、通知・iCalが同じ生成データを使うことを確認します。AWSへのデプロイとTerraform操作は、この対応に含めません。
