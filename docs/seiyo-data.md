# 西予市データガイド

西予市（自治体ID `38214`）の公式ごみ分別辞典と令和8年度地区別カレンダーから、1,293品目、17選択地区、17カレンダーを整備します。対応期間は `2026-04-01`～`2027-03-31` です。他自治体の分類、Embedding索引、収集日は流用しません。

## 対応範囲

| 地域 | 選択地区 | 主な差分 |
| --- | ---: | --- |
| 明浜 | 1 | 俵津・渡江・狩浜・高山・宮野浦・田之浜。朝8:00まで |
| 宇和 | 3 | 卯之町等の公式3カレンダー。朝7:00まで |
| 野村 | 8 | 野村中心部のもやすごみ3コースと、中筋・渓筋・大成・惣川・大野ヶ原 |
| 城川 | 2 | 魚成・遊子川と土居・高川で資源ごみの週が異なる |
| 三瓶 | 3 | 東・南・北地区。朝8:00まで。月別の粗大・金属・小型家電が異なる |

分別は、もやすごみ、埋立ごみ、新聞、雑紙、紙パック、段ボール、容器包装プラスチック、その他プラスチック、金属、小型家電、古布、ペットボトル、びん、かん、廃食用油、有害ごみ、粗大ごみ、市で収集しない物を分けて保持します。材質、500ml、容器内側の色、45リットル袋に入る大きさ、汚れなどで区分が変わる品目は、辞典の備考を候補検索と追加質問に渡します。

明浜・宇和の公式PDFには小地区別の粗大ごみ日も載っていますが、公式索引だけでは住所から小地区への完全な対応を作れません。誤通知を避けるため、これらの日付は通知・iCalへ生成しません。野村・城川の清掃センター受入日は公式に掲載された日だけ収録します。臨時変更は推測しません。

## 公式資料と確認方法

- [西予市：ごみ収集カレンダー](https://www.city.seiyo.ehime.jp/kakuka/seikatsu_fukushi/kankyo_eisei/gomi/calenda/index.html)
- [西予市：家庭ごみの分け方・出し方](https://www.city.seiyo.ehime.jp/kakuka/seikatsu_fukushi/kankyo_eisei/gomi/311.html)
- [西予市ごみ分類辞典](https://www.city.seiyo.ehime.jp/material/files/group/15/gomijiten.pdf)
- [西予市サイトの著作権](https://www.city.seiyo.ehime.jp/kakuka/seisaku_kikaku/seisakusuishin/saitonitsuite/430.html)

取得URL、取得日、SHA-256は `data/regions/seiyo/sources.json` に固定しています。分別辞典27ページは300dpi画像にし、表の罫線と分類欄の色から1,293行を抽出しました。Windows OCRは品名・備考の転記補助に限り、空欄15品目とOCRの定型誤りは元画像で照合しています。令和8年度カレンダーは14地区PDFに加え、野村の3もやすごみコースと城川の2資源グループを分離して、曜日、第N週、休業日、月別区分を実日付へ展開しています。

市サイトの著作権案内に従い、原本、OCR転記、生成CSV・カレンダー・Embedding索引はGit管理外です。公開リポジトリ、配布アプリ、Lambdaへ同梱する前に利用条件を確認してください。Gitで追跡するのは、出典とハッシュ、再生成スクリプト、レビュー記録、台帳、Embedding manifestです。

## ファイル構成

| パス | 内容 | Git |
| --- | --- | --- |
| `data/regions/seiyo/registry.json` | 17地区、7:00/8:00プロファイル、分類・粗大ごみ案内 | 追跡 |
| `sources.json`、`official_rules.json`、`areas.json`、`calendar_reviews.json`、`item_reviews.json` | 出典、公式ルール、照合記録 | 追跡 |
| `knowledge/index_manifest.json` | CSV・NPZ・モデル・次元の整合性 | 追跡 |
| `search_cases.json`、`search_evaluation.json` | 実検索の入力・期待・結果・費用 | 追跡 |
| `source/` | 公式PDF・HTML、OCR転記JSON | 除外 |
| `generated/calendar-2026.json`、`generated/addresses.json` | バックエンド・Flutter共通生成物 | 除外 |
| `knowledge/items.csv`、`knowledge/item_embeddings.npz` | 1,293品目と西予市専用Titan索引 | 除外 |
| `frontend/assets/data/municipality_38214_*` | Flutter用台帳・カレンダー・住所候補 | 台帳は追跡、カレンダー・住所候補は除外 |

## 新規cloneでの再生成

Python依存関係を用意し、リポジトリのルートで実行します。`fetch`、`build`、`verify --without-index` はBedrockを呼びません。

```powershell
backend\.venv\Scripts\python.exe scripts\seiyo_data.py fetch
```

辞典PDFを `tmp/seiyo-source/render/dictionary-300/dictionary-01.png`～`dictionary-26.png` として300dpi描画した後、Windows上で次を実行します。

```powershell
backend\.venv\Scripts\python.exe scripts\seiyo_split_ocr_pages.py
powershell -ExecutionPolicy Bypass -File scripts\seiyo_windows_ocr.ps1 `
  -InputDirectory tmp\seiyo-source\render\dictionary-300-halves `
  -OutputDirectory tmp\seiyo-source\ocr-dictionary-300-halves
backend\.venv\Scripts\python.exe scripts\seiyo_dictionary_extract.py
backend\.venv\Scripts\python.exe scripts\seiyo_data.py build
backend\.venv\Scripts\python.exe scripts\seiyo_data.py verify --without-index
```

Embedding生成は有料です。事前承認後にTitan Text Embeddings V2（`amazon.titan-embed-text-v2:0`、1,024次元）を使用します。

```powershell
backend\.venv\Scripts\python.exe scripts\build_regional_embeddings.py `
  --source data\regions\seiyo\knowledge\items.csv `
  --output data\regions\seiyo\knowledge\item_embeddings.npz `
  --municipality 38214 --profile citywide `
  --checkpoint data\regions\seiyo\generated\titan-checkpoint.jsonl `
  --max-calls 1300 --budget-usd 0.10 --workers 4
backend\.venv\Scripts\python.exe scripts\seiyo_data.py verify
backend\.venv\Scripts\python.exe scripts\generate_frontend_data.py `
  --municipality-id 38214 --merge-existing
```

## ローカル検証

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_seiyo_data.py -q
backend\.venv\Scripts\python.exe -m pytest backend\official_tests\verify_seiyo_runtime.py -q
cd frontend
flutter test tool\verify_seiyo_data_test.dart
flutter analyze
flutter build web
```

Flutter検証は17地区、全3,052日付、地区表示名、朝7:00/8:00、年末年始・8月15日の休業、野村・城川の地区差、粗大ごみ案内、通知・iCalが同じ生成データを使うことを確認します。AWSへのデプロイとTerraform操作は行いません。

## 実検索評価と費用

通常品目、市で収集しない物、紙パックの色・容量差、サイズ条件、材質・部品の追加確認を含む14ケースを `search_cases.json` に定義しています。2026年11月10日に実Bedrockで評価し、14件すべてが公式資料に基づく期待結果と一致しました。一般的な「飲料用の紙パック」は内側の色を確認し、白色の場合は続けて500ml未満・以上を確認します。

Titan Text Embeddings V2の索引生成は1,293件成功（112,811入力トークン、予約試行1,298回）、実検索評価は48回（Titan 16回、Nova Lite 32回）でした。成功応答から算出した推定実費は合計US$0.00583766、失敗試行を含む保守的な予約額はUS$0.09426084で、承認上限US$0.15以内です。入力、期待結果、実回答、成否、呼び出し回数と推定費用は `search_evaluation.json` に記録しています。認証期限切れ時の9予約記録はモデル応答前に失敗したため索引生成数と推定実費には含めず、監査用ログだけをGit管理外に保持します。
