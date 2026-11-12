# 宇和島市（38203）2026年度データ

`uwajima-2026.1` は2026年4月1日～2027年3月31日だけに適用します。通常収集、自治会別資源回収、随時の拠点持込、粗大ごみ・直接搬入、市で処理できないものを区別します。他自治体のCSV・索引・分別ルールは使いません。既存19自治体の登録を保持し、カタログは20自治体・706選択地区です。

## 対応範囲と出典

- 公式早見表は令和6年4月現在の23ページ、見出しを除く**1,124品目**。同名重複・置換文字は0件。現行の市の案内と2026年度裏面を照合し、確認済み説明例20件を加えた**1,144行**の専用CSV・1024次元Titan V2索引を使います。
- 公式資料は市のHTML 21件・PDF127件と、内閣府の祝日CSV1件の**149資料**。URL・取得日（2026年11月12日）・SHA-256は `sources.json`、採用ルールは `official_rules.json`、修正箇所は `item_reviews.json` に記録しています。原資料が変わると取得・生成は停止し、無条件に新しい内容を採用しません。
- 収集カレンダーのリンクは**118PDF**（宇和島100・吉田6・三間4・津島8）。内容ハッシュは**33種類**です。複数地区が同じカレンダーを参照する関係を保持します。戸島・日振島・竹ヶ島はPDFがないため、2026年度HTML日程を使います。
- **123選択地区**（宇和島102・吉田6・三間6・津島9）、古紙・地域別条件を含む**56カレンダーデータ（実日付54パターン）**。三間の通常収集4区域と古紙回収4区域の集落名を突き合わせ、6つの組合せに分けます。
- 宇和島地区の古紙は、公式の自治会名と通常収集地区名が一致する**18地区**だけを対応付けます。町名だけで自治会を確定しません。通常のびん・缶収集へ自治会の資源回収日を混ぜません。
- 乾電池・充電池は拠点回収として案内します。三間の年2回の乾電池回収は公式に「予定」とあるため確定日を作りません。自治会の乾電池回収をすべて通知・iCalへ組み込んだ実装ではありません。

主な市公式ページ：

- [家庭ごみの分類と出し方](https://www.city.uwajima.ehime.jp/soshiki/15/gomi-sutekata.html)
- [きれいなプラスチック](https://www.city.uwajima.ehime.jp/soshiki/15/plastic-jissyou.html)
- [宇和島](https://www.city.uwajima.ehime.jp/soshiki/15/gomi-u-shushubi2026.html)・[吉田](https://www.city.uwajima.ehime.jp/soshiki/15/gomi-y2026.html)・[三間](https://www.city.uwajima.ehime.jp/soshiki/15/gomi-m2026.html)・[津島](https://www.city.uwajima.ehime.jp/soshiki/15/gomi-t2026.html)の2026年度日程
- [宇和島地区の自治会別資源回収](https://www.city.uwajima.ehime.jp/soshiki/15/gomi-u-shigen.html)・[11月振替](https://www.city.uwajima.ehime.jp/info/shigen-furikae11.html)

## 独立照合と未確認の扱い

1,124行すべてを、可視文字の位置と、別に数えた分類欄の描画矩形・背景色で照合しました。通常の文字抽出で長音・句読点が行末へ移動する箇所は、可視文字の座標順に読みます。非表示・透明文字や重複描画を品目に加えません。

33種類のPDFの**12,045日付セル・6,034収集マーク**を色・位置から検査しました。日付数字は独立OCR・拡大OCRで10,936、OCRでラベルを確認した画像テンプレートで1,001、残る108は3枚の拡大一覧画像を目視して一致を確認しました。5週目の斜線共有セルも区別します。`image_reviews.json` と原資料ハッシュ付きの `manual_image_reviews.json` に記録しています。

HTMLの公式曜日ルールとの別比較では74日付行の差があり、祝日振替・PDFに明記された例外と未解決の矛盾を分けました。`calendar_comparison.json` に比較結果を保持しています。生成データの一致テスト44,895地区日付はバックエンド・Flutter間の契約検査であり、独立したPDF照合件数とは区別します。

- 三間PDFの後半見出しは「令和9年度」ですが、掲載ページは令和8年度、全日付・曜日は2026年10月～2027年3月です。ユーザー承認に基づき年度を解釈し、印字日付は書き換えていません。
- 伊吹町北通の一部・北宇和島町の9月30日可燃は、PDF空欄とHTMLの毎週水曜が不一致なので、**その日・区分だけ未確認**です。
- 高光（平駄場）のPETは、HTMLの第2・4木曜とPDFの第2・4金曜が不一致なので未確認。他の確認済み区分は使えます。
- 戸島・日振島のPET「月末」は具体的な日付へ置き換えません。離島で明記のない年始日程・搬出場所・船便時刻も推測しません。期限不明の区分は朝通知を作らず、前日通知・iCalに確認案内を付けます。
- 10月振替URLはHTTP404で、検索には2026年版と2025年版のキャッシュが混在します。確認済み資料として採用しません。祝日に当たる自治会資源回収の未確認振替は保留します。
- 11月23日→19日の古紙振替は、区域を一致確認した堀端町に適用しています。他の掲載自治会の情報も保持しますが、通常収集の広い町域へ一律に適用しません。11月3日→5日を全市の通常収集へ適用していません。
- 吉田の古紙は雨天中止、津島の古紙は雨・祝日の延期条件、竹ヶ島は船便・雨天の条件を案内します。雨を予測して日付を動かしません。

未確認日は `unverified_dates` で保持し、次の確認済み日より前なら検索結果を「収集日未確認」とします。カレンダーでは該当月・日で案内し、通知・iCalへは登録しません。他の確認済み日は利用できます。年度外へ日付を展開しません。

## 分別と検索

きれいなプラスチックは通常の可燃収集とは別の拠点回収です。洗浄・乾燥、製品は100%プラ、一辺50cm未満、異素材・事業系・汚れの除外、拠点による容器包装限定を保持します。50cmちょうどは対象外で、通常の指定袋に入れば可燃、入らなければ粗大の直接搬入等です。粗大の一般基準を50cmに変更していません。

PET本体と外したキャップ・ラベル、割れたびんと耐熱ガラス、取外し不能な充電池内蔵機器を分けます。スプレー缶は使い切り、安全な場所で穴を開ける市の案内に従います。粗大ごみは市の定期・戸別収集がなく、環境センターへ直接搬入又は許可業者へ依頼します。拠点や施設の受付日を定期収集へ変換しません。

Nova Lite・Titan Text Embeddings V2、自前索引、top8・類似度0.15・確信度0.75、KB=false・LEXICAL=falseは維持しています。同市内の各プロフィールは専用の共通索引を共有します。

| 実API評価 | 結果 |
|---|---|
| 初回48例（宇和島39＋既存9自治体各1） | 45成功、3失敗 |
| 修正後の関連8例 | 8成功 |
| 最新コードでの最終48例 | 48成功 |

初回の食品トレー（拠点希望を旧可燃行で上書き）、50cm境界、取外し不能ファンへの不要な袋サイズ質問を修正しました。索引は該当3文書だけ差分生成しています。初回1例ではTitanクエリEmbeddingがServiceUnavailableとなり、公式品目名一致の根拠で回答できました。最終評価では再確認できています。保存応答の再生を実API評価として数えていません。

索引生成は認証失敗9試行を含む1,156試行・1,147成功（初回1,144＋差分3）。評価は104ケース、Nova206呼出し・Titanクエリ104呼出し。索引と評価を合わせた保守的推定は **US$0.4759792**、承認はUS$1・索引最大1,250試行・評価112ケース/350呼出しです。AWS請求額の厳密な上限ではありません。`search_cases.json` と `search_evaluation.json` に入力・期待値・出典・フェーズ・結果・コード/データのハッシュ・費用を記録し、生応答はGit管理外に保持しています。全1,144行の実検索、実画像入力でのBedrock評価は今回行っていません。

## 新規cloneでの準備

Python 3.12、バックエンド依存関係、PyMuPDF 2.0.0、Pillowが必要です。既存READMEのPython環境を構築し、Pillowが未導入なら `uv pip install --python backend/.venv/bin/python Pillow` で追加してください。画像のOCRを再実行する場合はmacOS・Swiftコンパイラを使います。`generated/renders/`・`generated/ocr/`・OCR manifest類のハッシュ確認済みバンドルを共有すればOCR再実行を省けます。

```bash
backend/.venv/bin/python scripts/uwajima_data.py fetch
backend/.venv/bin/python scripts/uwajima_image_audit.py --ocr
backend/.venv/bin/python scripts/uwajima_data.py build
# NPZを共有配置した後。ここまでとverifyは課金なし
backend/.venv/bin/python scripts/uwajima_data.py verify
backend/.venv/bin/python scripts/generate_frontend_data.py --municipality-id 38203 --merge-existing
backend/.venv/bin/python -m pytest backend/tests/test_uwajima_data.py \
  backend/tests/test_uwajima_search_conditions.py backend/tests/test_unverified_calendar_dates.py \
  backend/official_tests/verify_uwajima_runtime.py -q
backend/.venv/bin/python scripts/verify_uwajima_package.py
cd frontend
flutter pub get
flutter test test/unit/unverified_dates_test.dart tool/verify_uwajima_data_test.dart tool/verify_uwajima_ui_test.dart
```

NPZは `data/regions/uwajima/knowledge/item_embeddings.npz` に配置し、Git内の `knowledge/index_manifest.json` とハッシュを照合します。共有先はまだ未定です。索引・実API評価を自分で再実行する場合は**別途費用承認**が必要です。今回の承認を他環境での再生成許可として扱わないでください。`activate` は初回登録用で、clone後に再実行する必要はありません。無指定で全自治体を再生成せず、必ず `--municipality-id 38203 --merge-existing` を付けます。

Git管理外の必要ファイルは `source/`、`knowledge/items.csv`、`knowledge/item_embeddings.npz`、`generated/calendar-2026.json` と、画像再検査を行う場合のOCRバンドルです。PDF・CSV・NPZ・実日付原本・checkpoint・API生ログをGitへ追加しません。資料の利用・加工・公開・再配布条件は未確認です。

## 検証と公開前の注意

通常テストは小さな合成フィクスチャで外部APIなし、公式データ照合は `backend/official_tests/verify_uwajima_runtime.py` とFlutterの `tool/verify_uwajima_*` で別実行します。バックエンド全体は624成功・43失敗で、失敗は追加前と同じ既存10自治体の不足データです。削除・スキップ・ダミー補完はしていません。

宇和島市単体のLambda用データは6ファイル・4,330,621バイト。移設先からhealth・6プロフィールの品目API・専用索引を確認しました。全カタログのパッケージは大洲市等の不足データで停止します。Linux/ARM・AWSデプロイは未実施です。

Flutterは地区選択、未確認日の月限定表示、粗大ごみ案内をwidgetテストで確認し、カレンダー・通知計画・iCalのサービスも検査しています。OSの通知許可・GPS・共有操作、実ブラウザとスマートフォンからの手操作は別途必要です。地域の境界データは作らず、GPS/住所から確定できない場合は手動選択を使います。今回ビルドの公開・配布やAWSへの反映はしていません。

全20自治体の登録保持は確認済みですが、10自治体のCSV・NPZ・カレンダーがこの環境に不足しているため、全20自治体の実データ動作検証が完了したとは扱いません。


コミット `b37691b` のみを展開した新規clone相当の隔離環境から149資料を再取得し、画像/OCRを再実行しました。台帳・CSV・カレンダー、共有した実NPZとmanifest、Flutterのカタログ・台帳・カレンダーがすべてバイト一致し、独立画像照合も再現しました。隔離環境のバックエンド27件・Flutter9件は全件成功、追加の有料APIは0回です。`reproduction_verification.json` に記録しています。検証JSONの `calendar_patterns` はカレンダーID数（56）を表し、実日付だけの組合せ数（54）とは区別します。

最終Flutter全体は259成功・11失敗（既存の不足データ）、静的解析は既存62件（7 warning・55 info、error 0）で、行番号を除いて追加前と同じ指摘です。既存6ファイルを変更しないため、HEADの解析設定を使った隔離コピーで実行しました。Webリリースビルドも成功しています。

ローカル操作時は、同じデータを配置したバックエンドへ接続してください。既存AWS環境には今回のコードを反映していません。別々のターミナルで起動します（実際の検索はBedrock利用料が発生します）。

```bash
cd backend
USE_BEDROCK_KNOWLEDGE_BASE=false LEXICAL_SEARCH_ENABLED=false \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
cd frontend
flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

NPZのチーム共有先の決定、他自治体の不足ファイルの準備、未確認地区・区分の市への照会、実端末での確認、AWSと配布物への反映が残ります。未確認の日付を対応済みとして公開しないでください。
