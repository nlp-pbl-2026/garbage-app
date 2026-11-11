# 今治市の2026年度データ

今治市（`38202`、版 `imabari-2026.1`）の233選択地区・44カレンダーに対応します。期間は2026-04-01〜2027-03-31です。233は住所別索引の区域条件ごとの選択肢数で、44は番号付き42 PDFと離島向け特別2 PDFの合計です。来島・小島は索引と同じ一つの選択肢、馬島は別の選択肢です。住所ではなく**集積所の位置**による公式索引なので、住所やGPSだけで自動確定しません。

## 出典と地域の違い

2026-11-12取得の75資料（HTML10・PDF65）のURLとSHA-256を `data/regions/imabari/sources.json` に記録しています。HTMLは `main` 本文だけを固定し、フッターのキャッシュコメントの変動を除外します。本文やPDFが変更された場合は再生成を停止します。

- [2026年度カレンダー](https://www.city.imabari.ehime.jp/recycle/calendar/R08/)と[住所別索引](https://www.city.imabari.ehime.jp/recycle/calendar/sakuin.pdf?R7)：索引の `?R7` はリンクの実際のパラメータです。これだけで年度を判断せず、全44種類の対応先を2026年度一覧・PDFの年度と地区名に照合しています。丁目・番地・枝番、国道196号の山側／海側、除外区域等を保持します。吉海の「全域（津島除く）」と「津島」は別の選択肢から、現行案内どおり同じ吉海カレンダーを参照します。
- [公式資料一覧](https://www.city.imabari.ehime.jp/recycle/siryo/)：2026年3月版の通常地域分別早見表855行を抽出。公式説明例12行を加え、通常地域の専用索引は867行です。全文ガイド、旧分割資料、現在の案内を確認し、旧版を無条件に優先しません。
- [関前の現在の出し方](https://www.city.imabari.ehime.jp/recycle/kateigomi/kateigomi_sekizen.html)と、2026年度カレンダーの裏面 `dasikata_sekizen01.pdf` / `02.pdf`：現在も今治市がリンクする2019年の関前専用早見表203行に、現行資料に基づく修正と説明例11行を加えた214行の**独立索引**を使用します。呉市一般の資料・検索索引は取り込みません。
- [通常地域の出し方](https://www.city.imabari.ehime.jp/recycle/kateigomi/kateigomi_imabari.html)、[現行の充電池案内](https://www.city.imabari.ehime.jp/recycle/info/lithium/)、[市で処理できないもの](https://www.city.imabari.ehime.jp/recycle/shoridekinai/)：取り外した家庭用小型充電池と、大型自転車用電池、電池が取り外せない機器を区別します。

分別プロフィールは通常地域、来島・馬島・小島、鵜島、関前の4種類です。前3種類は同じ867行の索引を共有し、収集日・搬出方法だけを切り替えます。関前の214行とは混ぜません。品目名と条件が一致する自市のCSV補足も既存仕様どおり使います。Knowledge BaseとLEXICAL_SEARCHはfalse、Nova Lite・Titan V2・上位8件・類似度0.15・確信度0.75の構成を維持しています。

関前では2019年表と異なる現行案内を優先します。具体的には単一プラスチック・50cm未満・汚れ除去済みの製品プラ、PETキャップ・ラベル、小型リチウム電池、割れたびん、廃油・ペンキ類等です。紙類は缶・びん・PETと別の日程、衣類は燃えるごみです。金属混合、50cm以上、汚れが落ちないもの、ゴム・シリコン、テープ類、灯油容器、厚さ5mm以上のまな板等のプラ資源対象外条件も保持します。CSVの `source_url` は原行の出典で、現行の変更根拠は `official_rules.json` と `examples.json` に記録しています。変更の開始日まで確認できないものは、2026年度に確認した内容として扱います。

## 日程・搬出時刻・粗大ごみ

通常42種類は印字された月・曜日・日付のマスを読み、凡例に対応する描画色と区分の文字を照合します。同日複数区分を保持します。資源の同日収集には有害・危険ごみも含むため、カレンダー・通知・iCalの共通表示名にも含めています。

- 通常地域：可燃・不燃は朝6:30まで。プラ・資源・有害・危険は地域で決めた時間で、地区別の時刻は未確認です。
- 来島・馬島・小島：毎週水曜の可燃・不燃（水曜祝日は翌木曜）、資源等は第2金曜。波止浜港8:40着の第3便の**各島の出航時刻まで**に指定の港へ。8:40を搬出期限として登録しません。2026年度の水曜祝日の4/29・5/6・9/23を翌木曜へ移します。
- 鵜島：可燃・不燃は金曜、年始1/1〜3は休止。資源等は2026/5/5・8/4・11/3・2027/2/2。朝8:30までに指定場所へ。
- 関前：岡村と大下・小大下は別カレンダー。朝8:30まで。紙類、粗大ごみ、有害・危険等の個別日付を保持します。岡村の2027/2/11は印字どおりプラのみで、通常の第2木曜ルールから他区分を補いません。

期限が不明でも確認済みの日付はカレンダーに表示します。当日朝通知は生成せず、前日通知・iCalに地域の時間又は船便の確認案内を付けます。当日の期限内を保証できないため、その日の次回収集を約束しない既存処理を利用します。

通常地域の粗大ごみは地区別申込期間の有料・予約制（通常1回10点、離島3島は5点）。受付センター0898-47-5300、平日8:30〜17:15、鵜島は宮窪支所0897-86-2500へ。予約日・料金・搬出場所を確認し処理券に受付番号を記入します。申込期間の帯や、要申込みの鵜島の粗大日を定期予定にしません。関前は専用の公式カレンダー指定日・関前開発総合センター横の指定場所・処理券（1枚300円、枚数は品目別）を使用し、通常地域の予約方法を流用しません。関前支所0897-88-2111へ確認できます。料金未確認を0円と表示しない既存の地域別UIを利用します。

## 独立照合と検証範囲

`imabari_pdf.py` は、辞典内のページ外の古い部品や、重なった区分文字をそのまま連結しません。実際の表のセル境界と最終描画面の背景色を使い、855行・203行を抽出します。名称・注記は各セルの文字から取得し、分類欄は別のOCR／画像照合も行います。原行と適用後の件数・内容ハッシュは `item_reviews.json` に固定しています。

42種類の15,330日付セルは、通常OCR14,693、OCRで学習した文字画像569、拡大OCR64、拡大画像の目視4で照合しました。分類欄1,058行はOCR629・文字画像391・目視38です。目視箇所は原PDFのハッシュ付きで `manual_image_reviews.json` に固定しています。全44カレンダーの年度・地区名、特別PDFの14個のルール記載も確認します。通常の文字レイヤーがある41 PDFでは、日付マスの8,413区分マーカーについて文字と描画色が一致しています。スキャンの岡村PDFは描画色を専用の凡例に照合し、日付はOCR／画像で確認します。

特別2 PDFは日付マスがなく、年度限定の曜日・祝日・個別日付指定から730日分を展開しています。**16,060個すべてが印字日付セルではありません。** 233選択地区の85,045日についてバックエンドとFlutterの一致も検査しますが、これはPDFとの独立検査とは別です。「24／31」の共有マスでは、それぞれの半分のマーカーを読み、24日の資源を31日に複製しません。年度外への繰返し生成はしません。

実Bedrockは初回44/48、追試1が7/8、追試2が8/8、最終版1が47/48、追試3が8/8、最終版2が48/48でした。不要な洗浄確認、取り外せない電池を含む家電と電池単体の混同、白色／色付きトレイ、矢印付き材質条件の見落としを修正しました。最新コードの全48例（今治40＋既存8自治体）の結果は `search_evaluation.json` と `search_cases.json` を参照してください。入力・公式の期待値・実回答・正誤・次回収集日を記録します。索引生成Titan1,081回・検索クエリTitan168回・Nova330回、評価延べ168ケース、保守的な費用記録は合計約US$0.7084です。これは実請求額ではなく、バイト数の予約枠・実績トークン等を使った見積りです。承認済みの推定US$1以内で完了し、他市の索引を再生成していません。

実APIは確率的で、代表例の成功が全品目・全表現の無誤判定を保証するものではありません。画像は公式図版の切り出しで検証しており、実カメラ写真の網羅評価ではありません。以後の変更は資源・有害・危険の共通表示名のみで、分類名・プロンプト・CSV・索引・日付・検索処理は最終評価時と同一です。

## 新規cloneからのセットアップ

リポジトリのルートで実行します。Python 3.12、検証時のPyMuPDF 2.0・Pillow 13.0.0・NumPy 2.5.4を使用しています。OCRの新規生成はmacOSのApple VisionとSwiftが必要で、有料APIは使用しません。

```bash
# 新規環境だけ作成。既存venvを上書きしない
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt \
  'pymupdf==2.0' 'Pillow==13.0.0' 'numpy==2.5.4' mangum

backend/.venv/bin/python scripts/imabari_data.py fetch
backend/.venv/bin/python scripts/imabari_data.py audit-images
backend/.venv/bin/python scripts/imabari_data.py build
backend/.venv/bin/python scripts/imabari_data.py verify --without-index
```

`inspect` は抽出差異を調べる開発用コマンドです。差異が出た場合、レビュー用JSONを機械的に上書きして成功扱いにせず、公式資料と画像を確認してください。

索引をチームメンバーから次の2か所へ配置し、Git内manifestのハッシュと照合します。共有先はまだ固定していません。再課金を避けるため、既存のNPZを共有する方法を優先します。macOSがない場合は、同じ原資料から作成した `generated/ocr/` 一式（画像、OCR JSON、manifest・refine-manifest）も共有して `build` から進めます。認証情報・検索生ログは共有しません。

```text
data/regions/imabari/knowledge/mainland/item_embeddings.npz
data/regions/imabari/knowledge/sekizen/item_embeddings.npz
```

```bash
# NPZ共有後。ここからも課金なし
backend/.venv/bin/python scripts/imabari_data.py verify
backend/.venv/bin/python scripts/generate_frontend_data.py --municipality-id 38202 --merge-existing
backend/.venv/bin/python -m pytest backend/tests/test_imabari_data.py \
  backend/tests/test_imabari_search_conditions.py backend/official_tests/verify_imabari_runtime.py -q
backend/.venv/bin/python scripts/verify_imabari_package.py
cd frontend
flutter pub get
flutter test tool/verify_imabari_data_test.dart tool/verify_imabari_ui_test.dart
```

`activate` は初回カタログ登録用です。今回のコミットには登録済みなので再セットアップで実行する必要はありません。Flutter生成は必ず `--municipality-id 38202 --merge-existing` を付け、他メンバーのカタログを維持してください。

自力で索引生成する場合は**別途費用承認**を得てから `build_regional_embeddings.py` を通常地域・関前それぞれに使います。`--source`・`--output`・`--profile` は上の対応を守り、checkpointも `generated/titan-mainland.jsonl` / `titan-sekizen.jsonl` と分けます。両索引の合計呼出し数・費用を管理してください。CSV・モデル・次元・ID順・ハッシュを確認した新manifestのレビューが必要です。他自治体の索引は生成しません。実評価用 `imabari_evaluate.py` も有料で、過去の承認を新しい環境での再実行許可として扱わないでください。

新規clone相当の隔離チェックアウトから75資料を再取得し、OCR・CSV・カレンダー・Flutterデータを再生成しました。2個のNPZは共有配置して再課金せず検証しています。`reproduction_verification.json` に原本からの再生成とバイト一致の記録を残しています。

## Git・配置・残る確認

Git対象は地区台帳、ルール、出典、レビュー、説明例、索引manifest、評価ケース／集計、取得・生成・検証スクリプト、Flutter台帳／カタログです。Git管理外は公式HTML/PDF、2 CSV・2 NPZ、実日付カレンダー、OCR画像／JSON、checkpoint、API生応答・課金記録です。既存データ管理方針を維持し、資料の利用・加工・公開・再配布条件は未確認として記録しています。

Lambdaには今治市の台帳、共通カレンダー、通常地域・関前それぞれのCSV・NPZ・manifestを既存のステージング処理で含めます。今治市単体はカタログ込み9ファイル、約3.96 MBで、移設先からLambdaエントリーポイントのhealth・地域別品目一覧・2索引の読込みを確認しました。PDF・OCR・checkpoint・APIログは含めません。全カタログのパッケージングは他自治体の不足データで停止します。ダミー補完や既存自治体の無効化はしていません。

通常テストと公式データ照合は分けています。全体テストに残る他自治体の不足データによる失敗、WebとスマートフォンのOS通知・GPS・共有操作の差、Linux/ARMの実行、AWSデプロイ、ブラウザから実APIへの手操作確認は別の確認事項です。今回デプロイ・公開・配布は実行していません。

2026-11-12の検証結果：今治市関連バックエンド36件成功、Flutter追加8件成功。バックエンド全体は597成功・43失敗で、元mainを隔離展開して同じ実データを配置した場合も561成功・同じ43件失敗でした。Flutter全体は250成功・11失敗。残る失敗は大洲・砥部・愛南・鬼北・松野・内子・松前・上島・四国中央・西予の不足データに関係する既存テストです。テストを削除・スキップしていません。静的解析は元mainと全62件が一致（errorなし、warning7・info55）、Webビルドは成功しました。既存のCupertinoフォント／Wasmのビルド警告は残っています。
