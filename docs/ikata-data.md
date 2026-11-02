# 伊方町の2026年度データ

伊方町（`38442`、データ版 `ikata-2026.1`）の分別辞典、地区台帳、カレンダーを既存の共通基盤へ追加します。適用期間は **2026-04-01～2027-03-31** です。別年度を曜日の繰り返しで補完しません。

## 対応範囲と公式資料

- [2026年度収集カレンダー](https://www.town.ikata.ehime.jp/soshiki/32/26164.html)：伊方3・瀬戸2・三崎3、計8 PDF。アプリの選択肢も同じ8収集地区群です。64件の小地域名を保持します。行政上の境界データではありません。
- [分別ガイドブック](https://www.town.ikata.ehime.jp/soshiki/32/11452.html)：辞典23～48ページの **1,196品目**と、公式説明ページに基づく補助根拠11件、合計1,207検索行を利用します。全ページ版と5分冊で品目・分類・注記を照合します。
- [第11期分別収集計画](https://www.town.ikata.ehime.jp/soshiki/32/6871.html)：2025年11月策定、2026～2030年度。資源区分と現在の収集体制の継続を確認しました。品目別案内は現在掲載のガイドを使用します。
- [家電リサイクル4品目](https://www.town.ikata.ehime.jp/soshiki/32/11415.html)：2023年更新。町の収集・町施設への搬入とも不可です。
- [可燃ごみの直接搬入](https://www.town.ikata.ehime.jp/soshiki/32/269.html)、[許可業者](https://www.town.ikata.ehime.jp/soshiki/32/11475.html)、[小型家電回収](https://www.town.ikata.ehime.jp/soshiki/32/8171.html)、[手数料の規則](https://www.town.ikata.ehime.jp/reiki_int/reiki_honbun/r099RG00000646.html)も確認しました。

取得・確認日は2026年11月3日です。原本39ファイルのURL・SHA-256を `data/regions/ikata/sources.json` に記録します。2022年公開ページでも添付PDFの差し替えがあり、可燃ごみの補助事業には「令和6年度終了」の追記があります。この補助事業は案内しません。充電池を定期回収へ変更する新しい案内は調査範囲では確認できず、現行公開ガイドの排出禁止を維持します。

9つの定期収集区分は可燃、埋立、びん、かん、ペット、プラ、発泡スチロール、古紙・古着、有害です。全て当日 **8時まで**。分類11区分のうち粗大・排出禁止には定期収集IDを割り当てません。

地区一覧は地域名と地名だけを表示します。瀬戸と三崎にある「高浦」は地域名で区別します。公式索引の「平磯」はリンク先PDFでは「平礒」、与侈・串・正野のPDF管理記号は「C-2」です。原表記と照合記録を `areas.json` に保持し、管理記号を地名の代わりに表示しません。同じPDF内で地区別に異なる区分や日付は確認されませんでした。

## 辞典の矛盾・条件付き品目

- 辞典27ページの「乾電池（ボタン型・充電式）」は文字が有害・背景が禁止色・注記が販売店相談です。ガイド14・49ページ及び別の辞典行の明示的な禁止指定に基づき、**排出禁止へ補正**します。元の分類文字は抽出記録とCSVの `source_category` に残します。
- 辞典39ページの入浴剤プラ容器は、文字プラ・背景埋立色です。文字と9ページのプラ容器包装案内を採用します。色の例外をこのセルだけに限定し、ほかの色の不一致は失敗させます。
- 「汚れが落ちないもの」の一部には、共通案内の可燃とは異なる埋立指定があります。個別注記を保持・優先し、一括で置換しません。
- 古着と明記された辞典行には、13ページの濡れ・汚れ・ひどい破れの条件を補足します。全ての紙・衣類に一律適用しません。
- 材質・袋サイズ・色・汚れの条件を `category_options` と注記へ保持します。金具・ふた等の部品の分類を、本体の代替分類へ無条件に変換しません。クエリ変換・Titan意味検索・Nova分類の既存経路を維持します。

## 粗大ごみ

30リットルの町指定埋立ごみ袋に入らないもの等は、禁止品を除き粗大ごみです。町窓口への申込み、許可業者への依頼、最終処分場への直接搬入を案内します。2026年度カレンダーは申込制・有料と記載する一方、粗大ごみの収集日を掲載していません。収集日・条件・料金は申込先で確認します。一般のごみ収集日や搬入受付日を粗大ごみの収集日に変換せず、**通知・iCal予定を生成しません**。

最終処分場は金曜14～16時（祝日を除く）、10kgごと20円・端数切上げです。可燃・禁止品は搬入できません。可燃ごみの八幡浜市環境センター搬入は、前営業日までの事前申請と別の手数料が必要です。品目ごとの料金を網羅的に登録しておらず、粗大一覧の料金は未確認として公式資料へ案内します。アプリの申込記録は従来どおり端末内の手動記録です。

## Git内とGit管理外

| 管理 | 内容 |
| --- | --- |
| Git内 | `areas.json`、`official_rules.json`、`sources.json`、地区台帳 `registry.json`、検証要約 `calendar_reviews.json` / `item_reviews.json`、索引整合性 `knowledge/index_manifest.json`、検索評価ケースと要約、生成・検証スクリプト、Flutterカタログ・台帳、テスト |
| Git管理外・取得可能 | `source/` の公式HTML/PDF（39件）。URLとハッシュはGit内 |
| Git管理外・無償生成 | `knowledge/items.csv`、`generated/calendar-2026.json`、抽出記録、Flutterの `municipality_38442_0_calendar.json` |
| Git管理外・共有又は有償生成 | `knowledge/item_embeddings.npz`（Titan V2、1024次元、伊方町専用） |
| 実行時不要・Git管理外 | `generated/titan-checkpoint.jsonl`、実APIの呼出し・応答ログ、各検査の中間出力 |

原本・加工データの公開・再配布条件は **未確認** として記録しています。Gitに含むルール・台帳等も加工メタデータであり、公開条件が確認済みという意味ではありません。

## 新規cloneでの再現

リポジトリのルートで実行します。Python 3.12を推奨します。既存の環境を使う場合、仮想環境の作り直しは不要です。

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt numpy 'pymupdf==2.0.0' Pillow
backend/.venv/bin/python scripts/ikata_data.py fetch
backend/.venv/bin/python scripts/ikata_data.py build
backend/.venv/bin/python scripts/ikata_data.py verify --without-index
```

`build` はレビュー済みハッシュ・抽出要約と一致した場合だけCSV・カレンダー・台帳を生成します。`fetch` は原本変更時に停止し、既存原本を上書きしません。HTMLの人口表示やページ更新だけでもハッシュが変わり得るため、変更時は本文と添付資料を確認してレビューを更新してください。`inspect` は候補を生成するだけで、レビューを自動承認しません。

バックエンドには、メンバーから **Git内manifestと対応する伊方町NPZ** を受け取り、`data/regions/ikata/knowledge/item_embeddings.npz` に配置します。共通の配布先は未設定です。共有の代わりに再生成する場合は費用の承認・AWSログイン後にだけ実行します。

```bash
# 有償。別途承認を得た場合だけ実行する。
backend/.venv/bin/python scripts/build_regional_embeddings.py \
  --source data/regions/ikata/knowledge/items.csv \
  --output data/regions/ikata/knowledge/item_embeddings.npz \
  --municipality 38442 --profile townwide \
  --checkpoint data/regions/ikata/generated/titan-checkpoint.jsonl \
  --max-calls 1250 --budget-usd 0.40
```

再生成では新しい索引hashを含むmanifestが更新されるため、CSV・モデル・次元・ID順序を再検証します。既存3市の索引はこのコマンドの対象外です。

```bash
backend/.venv/bin/python scripts/ikata_data.py verify
backend/.venv/bin/python scripts/generate_frontend_data.py
backend/.venv/bin/python -m pytest backend/tests -q
backend/.venv/bin/python -m pytest backend/official_tests/verify_ikata_runtime.py backend/official_tests/verify_iyo_runtime.py -q
cd frontend
flutter pub get
flutter test
flutter test tool/verify_ikata_data_test.dart tool/verify_ikata_ui_test.dart tool/verify_iyo_data_test.dart tool/verify_iyo_ui_test.dart tool/verify_yawatahama_data_test.dart
flutter analyze
flutter build web
```

標準カタログは既存3市も参照します。**新規cloneでは松山市・八幡浜市・伊予市のGit管理外カレンダーも、各市のガイドに従って生成・配置してください**。全自治体のバックエンド検索・パッケージングには各市のCSV・索引と松山市の中島根拠CSVも必要です。伊方町だけを生成して他市の不足を補うことはしません。Flutterだけでデプロイ済みAPIへ接続する場合、NPZ・AWS認証は不要ですが、対応版APIの反映が別途必要です。

ローカルAPIはルートから `cd backend` 後、次のように起動します。移動した仮想環境でも古いuvicornシバンを避けるため `python -m` を使います。

```bash
USE_BEDROCK_KNOWLEDGE_BASE=false LEXICAL_SEARCH_ENABLED=false \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# 別ターミナル、frontend/ で実行
flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

## 検証の方法と限界

辞典26ページは、全ページ版と分冊の品目・分類・注記の一致、全分類文字数と独立した行矩形数の一致、凡例の色と各行の描画色を照合します。既知の2セルだけ例外とします。OCRで全1,196行の日本語を独立に読み直した検査ではありません。

8 PDFの全2,920日付セルは、印刷された日付・収集記号から抽出します。別途、月・曜日・週から計算した位置で描画画像の背景色を凡例と照合します。空欄、土日、祝日、1月1～3日の休止、年末も含み、生成物同士の一致だけを検証するものではありません。各PDFの全体像、年末年始と凡例を目視でも確認しました。全日付を人が一つずつ監査したことや、町の校閲を受けたことを意味しません。

通常の単体テストは合成データのみです。`official_tests/` と `frontend/tool/verify_*` は生成・配置後に明示実行する実データテストです。通知は計画データ、iCalは生成文字列を検査します。スマートフォンでの通知到達・共有シート、実ブラウザでの手動操作、GPSによる地区確定は未検証です。伊方町の公式住所対応表・収集境界は登録せず、手動選択を使います。

検索評価は `search_cases.json` の24例（伊方町21、既存3市各1）を使います。画像2例は公式の缶のイラスト1点の経路検査で、実写全般の精度評価ではありません。`scripts/ikata_evaluate.py --confirm-paid` は有償であり、事前承認なしに通常テストへ組み込まないでください。初回の失敗も残し、修正後に再実施した範囲を評価要約へ区別して記録します。

## 今回の検証結果

- バックエンド：合成データ245件＋実データ/API30件、計275件成功（既存の非推奨警告4件）。
- Flutter：既存187件、実データ/UI18件が成功。解析はエラー0・既存warning7・info55、今回の追加指摘なし。Webビルド成功。
- 全8 PDF・2,920セルの文字/画像検査、辞典1,196行の全ページ版/分冊・行数・凡例検査が成功。
- 実Bedrock：初回24例中20例成功。修正後、関連8例（4・12・13・14・18・19・20・21）は8例成功。**最終版で全24例を再実施した結果ではありません**。初回に既存3市を各1例確認しています。詳細は `data/regions/ikata/search_review.json`。
- Titan索引：最終1,207行、成功呼出し1,215回（差分10回を含む）＋認証期限切れ3回の試行を記録。検索評価はNova64回・クエリEmbedding32回。合計費用の保守的な見積りはUS$0.1868048で、承認上限US$1以内です。実請求額は照会していません。
- ローカルでのLambda実行データのステージング22ファイルが成功。原本PDF・評価ログ・認証情報を含みません。AWSへの反映は行っていません。

新規ローカルcloneでも、伊方町の原本39件を公式URLから新規取得し、CSV・台帳・バックエンド/Flutterカレンダーを再生成して元作業環境とのバイト一致を確認しました。既存3市の検証済み実行データと伊方町NPZは共有配置しています。既存の松山市GPS案内を保つには、バックエンド用パッケージに含まれない `data/regions/matsuyama/generated/addresses.json` も、松山市の手順で生成又は共有配置してからFlutterデータ生成を行ってください。このファイルを配置して自治体カタログ全体の一致も確認しました。バックエンドの実データ/API16件とFlutterの伊方町6件が成功しています。Pythonは元環境の3.12依存関係、Flutterは既存のpubキャッシュを利用しており、空の端末へのSDK再インストールまでを検証したものではありません。
