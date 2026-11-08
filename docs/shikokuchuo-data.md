# 四国中央市データガイド

四国中央市（自治体ID `38213`）の公式「廃棄物排出基準表」「地区別収集曜日」と分別別ガイドから、402品目、20選択地区、20カレンダーを整備します。対応期間は `2026-04-01`～`2027-03-31` です。別自治体の分類・Embedding索引・収集日を流用しません。

## 対応範囲

| 地域 | 選択地区 | 主な差分 |
| --- | ---: | --- |
| 川之江 | 9 | 5収集パターンを、朝7:00対象地区と7:30対象地区に分離 |
| 三島 | 5 | 3市街地パターンと金砂・富郷。祭礼日の10月14日・15日は収集継続 |
| 土居 | 3 | JR線路の南北を含む3収集パターン |
| 新宮 | 3 | 燃やすごみ曜日と資源・有害ごみ周期が異なる3グループ |

分別は、燃やすごみ、燃やさないごみ、有害ごみ、びん・かん・ペットボトル、新聞、雑誌、雑がみ、段ボール・牛乳パックを別の収集区分として扱います。粗大ごみ、家電リサイクル、市で処理できないごみ、拠点・店頭回収は定期収集日に変換しません。リチウムイオン電池は製品から外して有害ごみ、外せないスマートフォン・電子タバコ・モバイルバッテリー等は製品ごと有害ごみです。

カレンダーは公式の毎週・第N曜日規則を実日付へ展開します。2026年5月2日、8月15日、10月14・15・22・23日、12月31日、2027年1月1・2日は公式休業として除外します。ただし三島地区は公式案内どおり2026年10月14日・15日の収集を保持します。日曜収集はありません。台風、積雪、路面凍結等による臨時中止は予測できないため生成しません。

## 公式資料と確認方法

- [四国中央市：家庭ごみの分け方・出し方](https://www.city.shikokuchuo.ehime.jp/soshiki/15/1924.html)
- [地区別収集曜日](https://www.city.shikokuchuo.ehime.jp/uploaded/attachment/3293.pdf)
- [燃やすごみ](https://www.city.shikokuchuo.ehime.jp/uploaded/attachment/3294.pdf)
- [燃やさないごみ](https://www.city.shikokuchuo.ehime.jp/uploaded/attachment/3295.pdf)
- [資源ごみ](https://www.city.shikokuchuo.ehime.jp/uploaded/attachment/3296.pdf)
- [廃棄物排出基準表](https://www.city.shikokuchuo.ehime.jp/uploaded/attachment/3303.pdf)
- [リチウムイオン電池の処分](https://www.city.shikokuchuo.ehime.jp/uploaded/attachment/21712.pdf)
- [2026年度クリーンセンター休業日](https://www.city.shikokuchuo.ehime.jp/soshiki/15/51919.html)
- [著作権について](https://www.city.shikokuchuo.ehime.jp/site/userguide/12028.html)

取得URL、取得日、SHA-256は `data/regions/shikokuchuo/sources.json` に固定しています。地区表2ページ、排出基準表6ページ、分別別ガイドを200dpiで描画し、OCRは転記補助に限定して、地区名・曜日・第N週・搬出時刻・品目区分・注意点を画像と目視照合しました。

市サイトの著作権案内に従い、原本PDF・HTML、転記CSV、生成カレンダー、Embedding索引はGit管理外です。公開リポジトリ、配布アプリ、Lambdaへ同梱する前に利用条件を確認してください。追跡するのは、出典とハッシュ、再生成スクリプト、レビュー記録、台帳、Embedding manifestです。

## ファイル構成

| パス | 内容 | Git |
| --- | --- | --- |
| `data/regions/shikokuchuo/registry.json` | 20地区、3時刻・例外プロファイル、分類・粗大ごみ案内 | 追跡 |
| `sources.json`、`official_rules.json`、`areas.json`、`calendar_reviews.json`、`item_reviews.json` | 出典、公式ルール、照合記録 | 追跡 |
| `knowledge/index_manifest.json` | CSV・NPZ・モデル・次元の整合性 | 追跡 |
| `search_cases.json`、`search_evaluation.json` | 実検索の入力・期待・結果・費用 | 追跡 |
| `source/` | 公式PDF・HTML | 除外 |
| `generated/calendar-2026.json`、`generated/addresses.json` | バックエンド・Flutter共通生成物 | 除外 |
| `knowledge/items.csv`、`knowledge/item_embeddings.npz` | 402品目と四国中央市専用Titan索引 | 除外 |
| `frontend/assets/data/municipality_38213_*` | Flutter用台帳・カレンダー・住所候補 | 台帳は追跡、カレンダー・住所候補は除外 |

## 新規cloneでの再生成

Python依存関係を用意し、リポジトリのルートで実行します。`fetch`、`build`、`verify --without-index` はBedrockを呼びません。

```powershell
backend\.venv\Scripts\python.exe scripts\shikokuchuo_data.py fetch
backend\.venv\Scripts\python.exe scripts\shikokuchuo_data.py build
backend\.venv\Scripts\python.exe scripts\shikokuchuo_data.py verify --without-index
```

Embedding生成は有料です。事前承認後にTitan Text Embeddings V2（`amazon.titan-embed-text-v2:0`、1,024次元）を使用します。

```powershell
backend\.venv\Scripts\python.exe scripts\build_regional_embeddings.py `
  --source data\regions\shikokuchuo\knowledge\items.csv `
  --output data\regions\shikokuchuo\knowledge\item_embeddings.npz `
  --municipality 38213 --profile citywide `
  --checkpoint data\regions\shikokuchuo\generated\titan-checkpoint.jsonl `
  --max-calls 420 --budget-usd 0.05 --workers 4
backend\.venv\Scripts\python.exe scripts\shikokuchuo_data.py verify
backend\.venv\Scripts\python.exe scripts\generate_frontend_data.py `
  --municipality-id 38213 --merge-existing
```

## ローカル検証

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_shikokuchuo_data.py -q
backend\.venv\Scripts\python.exe -m pytest backend\official_tests\verify_shikokuchuo_runtime.py -q
cd frontend
flutter test tool\verify_shikokuchuo_data_test.dart
flutter analyze
flutter build web
```

Flutter検証は20地区、全3,107日付、地区表示名、朝7:00/7:30、休業日、三島の例外、粗大ごみ案内、通知・iCalが同じ生成データを使うことを確認します。AWSへのデプロイとTerraform操作は行いません。

## 実検索評価と費用

2026年11月8日に、四国中央市専用データだけを使ってBedrock上の実モデルを評価しました。通常品目に加え、リチウムイオン電池、家電リサイクル対象、市で処理できない物、牛乳パックの容量差、汚れた紙、サイズ条件、粗大ごみ、材質の追加確認を含む14ケースすべてが公式資料どおりの結果になりました。汚れと臭いのある紙箱は初回評価で安全側の追加確認になったため、公式ルールを品目データへ明記し、その1件だけを再Embedding・再評価しています。入力・期待結果・実回答・成否は `search_evaluation.json` に保存しています。

| 処理 | 成功呼び出し | 入力トークン | 結果 |
| --- | ---: | ---: | --- |
| Titan Text Embeddings V2 索引生成 | 403 | 41,199 | 402件・1,024次元（修正1件の再生成を含む） |
| Titan Text Embeddings V2 検索クエリ | 15 | - | 評価14件＋再評価1件 |
| Nova Lite 書き換え・回答 | 30 | - | 評価14件＋再評価1件、各2呼び出し |

成功したモデル呼び出しは合計448回、推定実費は `US$0.00446148`、失敗・再試行分も含む保守的な予約額は `US$0.03528690` です。いずれも承認上限 `US$0.08` 以内です。初回のAWS認証期限切れによる予約記録はモデルへ到達していませんが、保守的な予約額には含めています。
