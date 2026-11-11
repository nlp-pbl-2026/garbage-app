# 西条市の2026年度データ

西条市（`38206`、版 `saijo-2026.1`）の39選択地区・25カレンダーを扱います。適用期間は2026-04-01～2027-03-31です。分別表1,273行に公式資料の説明例10行を加え、検索索引は1,283行・Titan Text Embeddings V2の1,024次元です。他自治体の索引・ルールは使いません。アプリ・AWSへの公開と配布は別作業です。

## 原資料と現行ルール

2026-11-11に取得した公式資料のURL・SHA-256は `data/regions/saijo/sources.json` に固定しています。HTMLは本文だけを保存・照合し、ナビゲーションやおすすめ記事の変動を除きます。本文やPDFが変われば再生成を停止し、再確認します。

- [2026年度地区別カレンダー](https://www.city.saijo.ehime.jp/soshiki/eisei/r8-calender.html)：西条13・東予6・丹原5・小松1の25 PDF。西条18・東予10・丹原9・小松2の39選択地区から参照します。徳田の「古田新出・田滝を除く」、丹原の「久妙寺を除く」、多賀の「三津屋本通りまで」等を表示に残します。
- [家庭ごみ分別ガイドブック](https://www.city.saijo.ehime.jp/soshiki/eisei/kateigomibunnbetuguidebook.html)：分割辞典の26ページ（印刷13～38ページ、全文PDFの14～39ページ）から全行を抽出。素材別・用途別の同名行を統合しません。全文・分割版の文字と描画の一致も検査します。
- [ごみの分け方・出し方](https://www.city.saijo.ehime.jp/soshiki/eisei/gominowakekata.html)、[新指定袋](https://www.city.saijo.ehime.jp/soshiki/eisei/singomifukuro.html)：2026年1月5日以降は新袋（もえる＝みどり、もえない＝オレンジ）のみ。旧袋の有効期限を現在へ引き継ぎません。
- [拠点回収](https://www.city.saijo.ehime.jp/soshiki/eisei/kyotenkaisyuubasyo.html)、[2026年2月広報の電池回収案内](https://www.city.saijo.ehime.jp/uploaded/attachment/82667.jpg)、[直接搬入](https://www.city.saijo.ehime.jp/soshiki/eisei/douzentyokuhan.html)：家庭用充電池・モバイルバッテリーはJBRC又は指定拠点窓口。電池を外せない機器は市へ相談します。車用等の大型電池、状態別の受付可否を推測しません。

飲食用缶は通常「もえないごみ」で拠点でも回収可。ガラスびん・スプレー缶は拠点対象外です。PET本体と、もえるごみになる取り外したキャップ・ラベルを区別します。スプレー缶は西条市の公式案内に従い使い切ってガス抜き・穴あけを案内し、他市の穴あけ不要ルールを使いません。

粗大ごみは[電話又は公式Web受付](https://www.sodai-saijo.jp/)の予約制戸別収集です。電話0897-66-7453、月～金9～12時・13～15時（祝日・12/29～1/3を除く）、Web24時間。1回10点まで、処理券1枚300円を必要枚数購入し、受付番号又は氏名を記入して貼付。予約日の朝8時までに指定場所へ出します。品目ごとの枚数・数量・条件は辞典の注記を保持し、未確認料金を無料としません。通常収集日・拠点受付・直接搬入・粗大予約日は別に扱います。

## カレンダーの検証と制限

曜日規則から未掲載の予定を追加せず、印字された日付とセルの文字・罫線・塗色を読み取ります。同日複数区分を保持します。相之谷は金曜に複数区分が重なるため、もえる・もえない・乾電池・古紙・びん・PET・スプレー缶を別の予定として保持します。全定期区分は朝8時までです。

[2026年の秋祭り休止案内](https://www.city.saijo.ehime.jp/soshiki/eisei/maturigomiyasumi.html)とPDFを照合し、10/15の西条・丹原、10/16の西条・丹原・小松、10/17の舟形・津越・長瀬・加茂には予定を生成しません。翌年度へ繰り返しません。

大保木・市之川・加茂のびん／PET／スプレー缶等は「随時収集」と印字され、具体的な日付がありません。この3地区・3区分だけを `unverified` とし、自治会・市への確認を検索結果・カレンダーで案内します。他の確認済み区分は利用可能です。日付のない区分の通知・iCal予定は作りません。地区選択に長い未確認説明を載せません。

地区対応は公式ページの25 PDFリンク・対象地区名と各PDFの見出しを照合します。吉井・多賀の短いPDF見出しにない「三津屋本通りまで」は公式索引の区域条件を保持します。

日付番号の欠落・誤記6セル（加茂5/20、神拝8/26、国安7/15・9/16、吉井・多賀8/24・31の共用セル、相之谷6/20）は、利用者の承認を得て月・曜日・前後の印字・凡例・描画位置から補正しました。市が訂正版を公開したという意味ではありません。相之谷11月・2月・3月の月外欄に残る文字・塗色からは予定を作りません。原本ハッシュ・印字・補正値・根拠は `date_label_reviews.json` に固定します。

独立検査はローカルApple Vision OCRと、OCRで読めた文字を教師にした画像テンプレート比較です。辞典分類1,273行（OCR1,221・画像比較52）、25 PDFの9,125日分・9,025物理セルの描画色、日付文字9,120片（OCR9,023・画像比較94・拡大目視3）を照合し、未解決を残しません。日付番号の補正・月外除外は別記録です。品目名・注意書きは全文／分割版間で一致を確認していますが、全注意書きの独立した人手による再転記ではありません。

剪定木の長さ2mちょうどは、同じ辞典の「粗大：2m以下」と「収集しない：長辺2m以上」が重なります。明示された長さがこの境界に該当し分類が重なる場合は、分類・日付を返さず市の窓口へ確認する判定保留とします。市による境界の確認が必要です。

住所だけで集積所の境界を確認できるデータは未整備です。GPSから地区を推測で確定せず、区域条件を確認して手動選択します。2027年度の日程は別途整備が必要です。

## 新規cloneでの再現

Python3.12、backend依存に加えてPyMuPDF2.0.0・numpy・Pillowを使います。OCR生成にはmacOS・Swift・Apple Visionが必要で、外部API料金は発生しません。

```bash
python3 -m venv backend/.venv  # 新規環境だけ
backend/.venv/bin/python -m pip install -r backend/requirements.txt 'pymupdf==2.0.0' Pillow
backend/.venv/bin/python scripts/saijo_data.py fetch
backend/.venv/bin/python scripts/saijo_data.py audit-images
backend/.venv/bin/python scripts/saijo_data.py build
backend/.venv/bin/python scripts/saijo_data.py verify --without-index
```

Gitには台帳、ルール、出典、レビュー、manifest、評価ケース、生成・検証スクリプト、Flutter台帳とカタログを含めます。公式HTML/PDF/JPG、CSV、NPZ、実日付カレンダー、OCR画像/JSON、API生応答・課金記録はGit管理外です。通常テストは小さな合成データを使い、上の公式データとの照合は別コマンドで実行します。

NPZはメンバーから `data/regions/saijo/knowledge/item_embeddings.npz` へ共有配置し、Git内 `index_manifest.json` のSHA-256と照合してください。共有先はまだ固定していません。macOSを利用できない場合は、同じ原本の `generated/ocr/` 一式と `generated/whole-split-audit.json` も共有して `build` から実行できます。認証情報・API生ログは共有バンドルに含めません。

```bash
# NPZ共有配置後。ここからは課金なし
backend/.venv/bin/python scripts/saijo_data.py verify
backend/.venv/bin/python scripts/generate_frontend_data.py --municipality-id 38206 --merge-existing
backend/.venv/bin/python -m pytest backend/tests/test_saijo_data.py backend/tests/test_saijo_search_conditions.py backend/official_tests/verify_saijo_runtime.py -q
cd frontend
flutter pub get
flutter test tool/verify_saijo_data_test.dart tool/verify_saijo_ui_test.dart
```

`activate` は検証・専用索引を確認した上で初めてカタログへ登録する際だけ使います。通常の再セットアップで他自治体のカタログを上書きしません。索引を自力生成する場合は別途費用承認を得て、次の専用コマンドを使います。既存自治体を対象にしません。

```bash
# 有料。事前承認が必要
backend/.venv/bin/python scripts/build_regional_embeddings.py \
  --source data/regions/saijo/knowledge/items.csv \
  --output data/regions/saijo/knowledge/item_embeddings.npz \
  --municipality 38206 --profile citywide \
  --checkpoint data/regions/saijo/generated/titan-checkpoint.jsonl \
  --max-calls 1400 --budget-usd 0.25 --workers 4
```

再生成時はCSV・ID順・次元・モデル・ハッシュを検証し、新manifestをレビューします。共有NPZなら再生成・再課金は不要です。資料の利用・加工・公開・再配布条件は引き続き未確認として記録しています。台帳・ルール・説明例も自治体資料の加工情報です。

ローカルAPIへ接続する場合は、データ配置後に次の2つを別のターミナルで起動します。検索操作には利用者自身のBedrock認証と利用料金が必要です。AWS公開APIは今回更新していないため、西条市を試す際は対応コードを動かしたローカルAPIへ接続します。

```bash
# ターミナル1
cd backend
USE_BEDROCK_KNOWLEDGE_BASE=false LEXICAL_SEARCH_ENABLED=false \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# ターミナル2（リポジトリのルートから）
cd frontend
flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

## 検索評価・実行環境

Nova Liteのクエリ変換、Titan V2意味検索と同一自治体CSVの明示品目補完、Nova Liteの分類・追加質問を維持します。KB=false・LEXICAL=false、上位8・類似度0.15・確信度0.75です。補助説明・料金・共通の出し方を無関係な品目のEmbeddingへ大量追加しません。

初回・追試・最終版の記録は `search_evaluation.json` に整理します。原応答、検索根拠、token使用量、予約費用・呼出し記録はGit管理外の `generated/live-eval-*` に残ります。実APIの再評価には別途承認が必要です。

Lambdaにはカタログ・registry・CSV・NPZ・manifest・カレンダーの実行時ファイルだけを同梱し、PDF・OCR・API生ログは含めません。他担当自治体のデータが欠けた環境では、全カタログのパッケージングと該当公式テストは失敗します。西条市単体の検証と区別し、ダミー補完・索引の無断再生成はしません。スマートフォンのGPS・OS通知・共有機能、実機・公開APIへの反映は今回のローカル検証と別です。

## 今回の検証結果

- バックエンド：西条市関連52件成功。全体561件成功・43件失敗。失敗は大洲・砥部・愛南・鬼北・松野・内子・松前・上島・四国中央・西予のGit管理外データ不足です。スキップ・ダミー補完はしていません。
- Flutter：西条市7件成功、通常＋公式データテスト全体242件成功・11件失敗（同じ他担当データ不足）。静的解析は既存と同じ62件（warning7・info55）、新規errorなし。Webビルド成功。OS通知・GPS・iCalの実機動作やブラウザの手動操作は今回別途未実施です。
- 実Bedrock：初回29/35、追試7/8、最終35/35。最終35例は西条市28例（画像＋文章、追加質問、未確認収集日を含む）と既存7自治体です。初回6失敗はキャップ／本体混同、段ボール表記、材質・比較サイズ確認、幹の太さ条件、洗浄済み表現でした。追試で残った太さ6cmは適用外根拠を除外して解消しました。
- 長さ2m境界保留を含む追加36例は35/36成功（西条市29/29成功）。伊予市PETだけは辞典名「ペットボトル類の本体」の表記差により本体根拠が候補から漏れ、保留になりました。既存データ・索引を変えず品目名照合の表記差を吸収し、追加承認された6例（伊予PET、西条PET本体・キャップ・剪定木、東温PET、久万高原PET）は6/6成功しました。最新の修正後に全36例の実APIを再実行したとは扱いません。最新コードによる記録済み応答の再生は36/36成功しています。
- 索引生成1,300呼出し（初回1,277＋差分23）、検索評価120ケース・Nova239＋クエリTitan120呼出し。合計保守的推定US$0.6062276。AWS請求額そのものではありません。
- 空の原資料／生成物領域へ51資料を再取得し、326画像を再描画・再OCR、CSV・registry・実日付JSONのバイト一致を確認。NPZは検証済み共有ファイルを配置し、無料で整合性検査しました。記録は `reproduction_verification.json` にあります。
- Lambda用6ファイルの西条市単体ステージング、パス上書きなしの移設後health・粗大品目API・索引読込み・境界保留が成功しました。全カタログは他担当の不足データにより停止します。AWS・Terraform操作、push・PR作成はしていません。
